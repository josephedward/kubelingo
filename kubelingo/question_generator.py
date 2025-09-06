"""
This module contains functions for generating new, unique, and high-quality
Kubernetes questions for the Kubelingo study tool.
"""

import os
import random
import yaml
import requests
from bs4 import BeautifulSoup
from thefuzz import fuzz
try:
    from colorama import Fore, Style
except ImportError:
    class Fore:
        RED = YELLOW = GREEN = CYAN = ''
    class Style:
        BRIGHT = RESET_ALL = DIM = ''
import webbrowser
import sys # Added import for sys

MAX_RETRIES = 3

try:
    from googlesearch import search
except ImportError:
    search = None

from kubelingo.utils import (_get_llm_model, QUESTIONS_DIR, USER_DATA_DIR, load_questions,
                             get_normalized_question_text, remove_question_from_corpus)
from kubelingo.validation import validate_manifest, validate_manifest_with_llm
 
# Helper: extract first YAML/code snippet from HTML
def _extract_yaml_snippet_from_html(html):
    """Return the first <pre> or <code> block that looks like a Kubernetes YAML manifest."""
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup.find_all(['pre', 'code']):
        text = tag.get_text()
        if text and (text.strip().startswith('apiVersion:') or 'kind:' in text or 'metadata:' in text):
            return text.strip()
    return None
# Helper to sanitize generated question dicts
def _ensure_question_fields(q, topic):
    """
    Ensure a question dict has required keys: suggestion, solution, source, rationale.
    Fill any missing fields with safe defaults.
    """
    if 'suggestion' not in q or q.get('suggestion') is None:
        q['suggestion'] = q.get('solution', '')
    if 'solution' not in q or q.get('solution') is None:
        q['solution'] = q.get('suggestion', '')
    if 'source' not in q or q.get('source') is None:
        q['source'] = ''
    if 'rationale' not in q or q.get('rationale') is None:
        section = ' '.join([w.capitalize() for w in topic.split('_')])
        q['rationale'] = f"Practice question for {section}."
    return q

# --- Exceptions ---
class GenerationError(Exception):
    """Base exception for question generation failures."""
    pass

class DuplicateQuestionError(GenerationError):
    """Raised when the generated question is a duplicate of an existing one."""
    pass

class MissingFieldsError(GenerationError):
    """Raised when the generated question is missing required fields."""
    pass

class LLMGenerationError(GenerationError):
    """Raised when the LLM fails to generate a valid question."""
    pass


# --- Main Generation Orchestrator ---

def generate_more_questions(topic, base_question=None, force_llm=False):
    """
    Orchestrates the entire process of generating a new, unique, and validated
    question for a given topic, with retry mechanism.

    Args:
        topic (str): The topic for which to generate a new question.

    Returns:
        dict: The new question dictionary if successful, otherwise None.
    """
    print(f"\n{Style.BRIGHT}{Fore.CYAN}--- Starting New Question Generation for Topic: {topic} ---{Style.RESET_ALL}", flush=True)

    # 1. Optionally search for web/documentation sources before LLM
    if force_llm:
        print("  - Forcing LLM-only question generation; skipping web/documentation search...", flush=True)
        potential_sources = None
    else:
        print("  - Attempting to find existing material from the web...", flush=True)
        potential_sources = _search_for_question_material(topic)
    new_question = None
    validation_passed = False
    validation_summary = ""
    validation_details = ""

    # First try to generate a question from curated or web sources
    if potential_sources:
        new_question = _create_question_from_sources(potential_sources, topic)
        # If we directly extracted a snippet, strip the helper flag and return immediately
        if isinstance(new_question, dict) and new_question.get('_snippet_extracted'):
            new_question.pop('_snippet_extracted', None)
            return new_question
    # If we got a candidate, validate it; otherwise we'll fall back to LLM
    if new_question:
        print(f"{Fore.GREEN}  - Successfully generated a question from a web source.{Style.RESET_ALL}", flush=True)
        print("  - Validating the generated question...", flush=True)
        existing_questions_data = load_questions(topic, Fore, Style)
        existing_questions = existing_questions_data.get('questions', []) if existing_questions_data else []
        try:
            validation_passed, validation_summary, validation_details = _validate_generated_question(
                new_question, existing_questions, topic
            )
        except (MissingFieldsError, DuplicateQuestionError, LLMGenerationError) as e:
            print(f"{Fore.YELLOW}  - Web-sourced question failed validation: {e}. Falling back to LLM generation.{Style.RESET_ALL}", flush=True)
            new_question = None
        else:
            if not validation_passed:
                print(f"{Fore.YELLOW}  - Web-sourced question did not pass validation: {validation_summary}. Falling back to LLM generation.{Style.RESET_ALL}", flush=True)
                new_question = None
    if not new_question:
        print(f"{Fore.YELLOW}  - Could not generate a valid question from web sources, falling back to LLM generation.{Style.RESET_ALL}", flush=True)

        # If no question from web source, proceed with existing generation logic
        # 1. Determine existing questions for context
        print("  - Preparing context for question generation...", flush=True)
        if base_question:
            existing_questions = [base_question]
        else:
            existing_questions_data = load_questions(topic, Fore, Style)
            existing_questions = existing_questions_data.get('questions', []) if existing_questions_data else []
            if not existing_questions:
                print(f"{Fore.YELLOW}  - Warning: No existing questions found for topic '{topic}'. Cannot generate a related question.{Style.RESET_ALL}", flush=True)
                return None

        feedback_message = None
        for retry_count in range(MAX_RETRIES):
            print(f"\n{Style.BRIGHT}--- Attempt {retry_count + 1}/{MAX_RETRIES} ---", flush=True)
            try:
                # 2. Build a robust prompt for the LLM
                print("  - Building a detailed prompt for the AI...", flush=True)
                prompt = _build_generation_prompt(topic, existing_questions, feedback_message)

                # 3. Call the LLM to generate a new question
                print(f"  - Calling AI to generate a new question (this may take a moment)...", flush=True)
                new_question_raw = _call_llm_for_generation(prompt)
                new_question = new_question_raw

                # Allow 'solution' key as alias for 'suggestion' when validating
                if 'suggestion' not in new_question and 'solution' in new_question:
                    new_question['suggestion'] = new_question['solution']

                # 4. Attempt to assign a source if missing (so validation can check it)
                if not new_question.get('source'):
                    print("  - AI did not provide a source. Attempting to find one automatically...", flush=True)
                    assign_source(new_question, topic)

                # 5. Validate the generated question
                print("  - Validating the generated question...", flush=True)
                validation_passed, validation_summary, validation_details = _validate_generated_question(new_question, existing_questions, topic)

                print(f"DEBUG: validation_passed = {validation_passed}", flush=True)
                if validation_passed:
                    print(f"{Fore.GREEN}  - Validation successful for this attempt.{Style.RESET_ALL}", flush=True)
                    break # Exit retry loop
                else:
                    print(f"{Fore.YELLOW}  - Validation failed for this attempt. Preparing for retry...{Style.RESET_ALL}", flush=True)
                    feedback_message = f"Previous attempt failed validation. Details:\n{validation_summary}\n{validation_details}\nPlease generate a new question that addresses these issues."

            except (GenerationError, DuplicateQuestionError, MissingFieldsError, LLMGenerationError) as e:
                print(f"{Fore.RED}  - Generation attempt failed. Reason: {e}. Preparing for retry...{Style.RESET_ALL}", flush=True)
                feedback_message = f"Previous attempt resulted in an error: {e}. Please generate a new question."
                validation_summary = str(e) # Update validation_summary with the specific error
                validation_passed = False # Mark validation as failed
                # new_question is NOT reset to None here, so it can be inspected
            except Exception as e:
                print(f"{Fore.RED}  - An unexpected error occurred during generation attempt: {e}. Preparing for retry...{Style.RESET_ALL}", flush=True)
                feedback_message = f"Previous attempt resulted in an unexpected error: {e}. Please generate a new question."
                validation_summary = str(e) # Update validation_summary with the specific error
                validation_passed = False # Mark validation as failed
                # new_question is NOT reset to None here, so it can be inspected

    # After retry loop, if no question was generated at all, abort
    if new_question is None:
        print(f"{Fore.RED}\n--- Question Generation Failed After {MAX_RETRIES} Attempts ---\n{Style.RESET_ALL}", flush=True)
        if validation_summary:
            print(f"{Fore.RED}Reason: {validation_summary}{Style.RESET_ALL}", flush=True)
            if validation_details:
                print(f"{Fore.RED}Last Validation Details:\n{validation_details}{Style.RESET_ALL}", flush=True)
        print("DEBUG: Final return: new_question is None after retry loop.", flush=True)
        return None

    def _print_question_yaml(question_dict):
        """Helper to print a question dictionary as a YAML string."""
        print(yaml.safe_dump(question_dict, indent=2, default_flow_style=False, sort_keys=False))

    print(f"\n{Style.BRIGHT}{Fore.BLUE}--- Generated Question for Review ---{Style.RESET_ALL}", flush=True)
    _print_question_yaml(new_question)

    # Display validation results
    print(f"\n{Style.BRIGHT}{Fore.CYAN}--- Validation Summary ---{Style.RESET_ALL}", flush=True)
    print(validation_summary, flush=True)
    if validation_details:
        print(f"{Style.DIM}Details:\n{validation_details}{Style.RESET_ALL}", flush=True)

    # Previously, questions missing a suggestion were auto-rejected; now allow user to accept incomplete questions

    # Ask for user decision, adjusting the prompt based on validation status
    prompt_text = f"{Style.BRIGHT}{Fore.YELLOW}Accept this question? (y/n): {Style.RESET_ALL}"
    if not validation_passed:
        prompt_text = f"{Style.BRIGHT}{Fore.YELLOW}Accept this question DESPITE validation failures? (y/n): {Style.RESET_ALL}"

    user_decision = input(prompt_text).strip().lower()
    if user_decision != 'y':
        print(f"{Fore.RED}Question rejected by user. Aborting generation.{Style.RESET_ALL}", flush=True)
        print("DEBUG: Final return: new_question rejected by user.")
        return None
    else:
        # If accepted, finalize and ensure required fields
        # Final formatting and cleanup
        if 'solution' in new_question and isinstance(new_question['solution'], str):
            new_question['solution'] = new_question['solution'].strip()
        if 'suggestion' in new_question and isinstance(new_question['suggestion'], str):
            new_question['suggestion'] = new_question['suggestion'].strip()
        # Ensure all required fields are present before finalizing
        new_question = _ensure_question_fields(new_question, topic)
        print(f"{Fore.GREEN}\n--- New Question Generated Successfully!---\n{Style.RESET_ALL}", flush=True)
        _print_question_yaml(new_question)
        print("DEBUG: Final return: new_question accepted by user.")
        return new_question


# --- Helper Functions for Generation Flow ---

def _search_for_question_material(topic):
    """
    Searches Kubernetes official API for relevant documentation content
    """
    print(f"  - Querying Kubernetes API for {topic} documentation...", flush=True)
    
    # Use Kubernetes official content API
    api_url = f"https://kubernetes.io/api/v1/content/en/docs/search/?q={topic}"
    search_results = []
    
    try:
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            results = response.json()
            # Get top 5 most relevant results from API
            search_results = [
                f"https://kubernetes.io{item['path']}"
                for item in results.get('results', [])[:5]
                if item.get('path')
            ]
    except Exception as e:
        print(f"{Fore.YELLOW}  - API request failed: {e}{Style.RESET_ALL}", flush=True)
    except Exception as e:
        print(f"{Fore.YELLOW}  - API request failed: {e}{Style.RESET_ALL}", flush=True)

    if search_results:
        print(f"  {Fore.GREEN}- Found {len(search_results)} curated sources.{Style.RESET_ALL}")
        return search_results
    else:
        print(f"{Fore.YELLOW}  - No curated sources found for topic.{Style.RESET_ALL}", flush=True)
        # Fallback to general web search if curated sources are not enough or not found
        if search:
            print(f"  - Falling back to general web search for topic: {topic}...", flush=True)
            try:
                # Perform a general web search for the topic
                general_search_query = f"kubernetes {topic} example"
                # Limit to 5 results, and filter for reputable sources
                web_search_results = []
                for url in search(general_search_query, num_results=5):
                    web_search_results.append(url)

                # Deduplicate and limit again, just in case
                web_search_results = list(dict.fromkeys(web_search_results))[:5]

                if web_search_results:
                    print(f"  {Fore.GREEN}- Found {len(web_search_results)} general web sources.{Style.RESET_ALL}\n")
                    return web_search_results
                else:
                    print(f"{Fore.YELLOW}  - No general web sources found for topic.{Style.RESET_ALL}\n", flush=True)
            except Exception as e:
                print(f"{Fore.YELLOW}  - Error during general web search: {e}{Style.RESET_ALL}\n", flush=True)
        return None


def _create_question_from_sources(sources, topic):
    """
    Creates questions from API-sourced documentation URLs
    """
    print(f"  - Processing {len(sources)} API results...", flush=True)
    for url in sources:
        print(f"    - Fetching structured content from: {url}", flush=True)
        try:
            html_resp = requests.get(url, timeout=10)
            html_resp.raise_for_status()
            snippet = _extract_yaml_snippet_from_html(html_resp.text)
            if snippet:
                return {
                    'question': f"Provide the Kubernetes YAML manifest example from the documentation at {url}",
                    'suggestion': snippet,
                    'source': url,
                    'rationale': f"Demonstrates the example manifest for topic '{topic}' as shown in the official docs."
                }
        except Exception as e:
            print(f"{Fore.YELLOW}    - Failed to extract snippet from HTML for {url}: {e}{Style.RESET_ALL}", flush=True)
    # No snippet found in any source
    return None


def _build_prompt_from_source(topic, content, source_url):
    """
    Builds a prompt to generate a question from a given source content.
    """
    prompt = f'''You are a Kubernetes documentation analyst. Create an exam question DIRECTLY FROM this documentation content.
You MUST follow these rules:
1. Question MUST be answerable using ONLY the provided documentation content
2. Answer MUST be a direct quote or paraphrase from the documentation
3. Include the exact section header where the answer can be found
4. Format YAML using documentation examples verbatim

Documentation Content Rules:
- Preserve technical details exactly
- Use official terminology from the docs
- Include kubectl commands exactly as shown

Topic: {topic}
Source URL: {source_url}
Source Content:
---
{content}
---

Generate ONE new question that meets the following criteria:
1.  **Grounded in Source**: The question and answer MUST be directly based on the provided Source Content.
2.  **CKAD Relevance**: It must test a skill relevant to the CKAD exam for the given topic.
3.  **Type**: It can be a command-line question (using `kubectl`, `helm`, etc.) or a YAML manifest creation question.
4.  **Completeness**: The question must contain all necessary information for the user to solve it. The `suggestion` should be a valid and correct answer.
    If the `suggestion` is a Kubernetes YAML manifest, it MUST be a complete and valid Kubernetes object, including `apiVersion`, `kind`, `metadata`, and `spec` (if applicable).
5.  **Source**: Use the provided Source URL for the `source` field.
6.  **Rationale**: Include a brief `rationale` field explaining what skill the question tests and why it's relevant for the CKAD, based on the source material.

Provide the output in a single, valid YAML block. The structure must be:
```yaml
question: "Your new, unique question text here."
suggestion: |
  # The solution, extracted and formatted from the source content.
source: "{source_url}"
rationale: "Explanation of the question's purpose for CKAD study."
```

Now, generate the new question.
'''
    return prompt
def _build_generation_prompt(topic, existing_questions, feedback_message=None):

    """Constructs the LLM prompt using few-shot examples and existing section content."""
    # Select a few random examples from existing questions
    examples = random.sample(existing_questions, min(len(existing_questions), 3))

    prompt = f"""You are a Kubernetes expert tasked with creating a new, unique practice question for a Certified Kubernetes Application Developer (CKAD) study guide.

The topic for the new question is: '{topic}'

Here are some examples of existing questions in this topic. Do NOT create a direct copy or a simple variation of these. The new question must be substantively different.
---
{yaml.safe_dump(examples, allow_unicode=True, default_flow_style=False, sort_keys=False)}
---

Here is a list of just the question text from ALL existing questions in this topic. You MUST NOT generate a question that is semantically or literally similar to any of these:
---
- {"- ".join([q.get('question', '') for q in existing_questions])}
---

Your task is to generate ONE new question that meets the following criteria:
1.  **Uniqueness**: It must be a new concept or a significantly different scenario from the examples provided.
2.  **CKAD Relevance**: It must test a skill relevant to the CKAD exam for the given topic.
3.  **Type**: It can be a command-line question (using `kubectl`, `helm`, etc.) or a YAML manifest creation question.
4.  **Completeness**: The question must contain all necessary information for the user to solve it. The `suggestion` should be a valid and correct answer.
    If the `suggestion` is a Kubernetes YAML manifest, it MUST be a complete and valid Kubernetes object, including `apiVersion`, `kind`, `metadata`, and `spec` (if applicable).
5.  **Source**: You MUST provide a `source` field with a valid URL to the official Kubernetes documentation or a highly reputable blog/article that justifies the answer.
6.  **Rationale**: Include a brief `rationale` field explaining what skill the question tests and why it's relevant for the CKAD.

Provide the output in a single, valid YAML block. The structure must be:
```yaml
question: "Your new, unique question text here."
suggestion: |
  # IMPORTANT: If the solution is a Kubernetes YAML manifest, provide it as a multi-line block using the YAML literal style (with '|').
  # It MUST represent a single Kubernetes object or a single list of Kubernetes objects, and MUST NOT contain '---' separators.
  # DO NOT use escaped newlines (e.g., '\n') or put the entire YAML on a single line.
  # Example of a multi-line YAML manifest for 'suggestion':
  apiVersion: v1
  kind: Pod
  metadata:
    name: my-pod
  spec:
    containers:
    - name: my-container
      image: my-image
  # If the solution is a command, provide it as a single string (e.g., 'kubectl get pods').
source: "URL to official documentation."
rationale: "Explanation of the question's purpose for CKAD study."
section: "The specific section of the Kubernetes documentation the question is based on, e.g., 'Workloads', 'Networking', 'Storage'."
```

Now, generate the new question.
"""
    if feedback_message:
        prompt += f"\n\nIMPORTANT FEEDBACK FROM PREVIOUS ATTEMPT:\n{feedback_message}\n\nPlease generate a revised question that addresses this feedback."
    return prompt


def _call_llm_for_generation(prompt):
    """Calls the configured LLM and parses the YAML response."""
    llm_type, model = _get_llm_model()
    if not model:
        raise LLMGenerationError("No LLM model is configured or available.")

    raw_response = ""
    cleaned_response = ""
    raw_response = ""
    cleaned_response = ""
    try:
        if llm_type == "gemini":
            response = model.generate_content(prompt)
            raw_response = response.text
        elif llm_type == "openai":
            resp = model.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a Kubernetes expert creating CKAD practice questions."},
                    {"role": "user", "content": prompt}
                ]
            )
            raw_response = resp.choices[0].message.content
        elif llm_type == "openrouter":
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=model["headers"],
                json={"model": model["default_model"], "messages": [{"role": "user", "content": prompt}]}
            )
            resp.raise_for_status()
            raw_response = resp.json()["choices"][0]["message"]["content"]
        else:
            raise LLMGenerationError(f"Unsupported LLM type: {llm_type}")

        # Clean the response to extract only the YAML part
        cleaned_response = raw_response.strip()
        if '```yaml' in cleaned_response:
            cleaned_response = cleaned_response.split('```yaml', 1)[1]
        if '```' in cleaned_response:
            cleaned_response = cleaned_response.split('```', 1)[0]

        parsed_content = yaml.safe_load(cleaned_response)

        if isinstance(parsed_content, dict) and 'question' in parsed_content:
            return parsed_content
        elif isinstance(parsed_content, dict) and 'questions' in parsed_content:
            q_list = parsed_content.get('questions')
            if isinstance(q_list, list) and q_list:
                if isinstance(q_list[0], dict) and 'question' in q_list[0]:
                    return q_list[0]
                else:
                    raise LLMGenerationError("First item in 'questions' list is not a valid question dictionary.")
            else:
                raise LLMGenerationError("LLM did not generate any valid questions (empty or non-list 'questions' key).")
        elif isinstance(parsed_content, list) and parsed_content and isinstance(parsed_content[0], dict) and 'question' in parsed_content[0]:
            return parsed_content[0]
        else:
            raise LLMGenerationError("LLM output was not a valid question dictionary or a list of questions.")

    except (yaml.YAMLError, IndexError) as e:
        print(f"{Fore.RED}YAML Parsing Error: {e}{Style.RESET_ALL}", file=sys.stderr)
        print(f"{Fore.RED}Raw LLM Response:\n{raw_response}{Style.RESET_ALL}", file=sys.stderr)
        print(f"{Fore.RED}Cleaned LLM Response (attempted YAML):\n{cleaned_response}{Style.RESET_ALL}", file=sys.stderr)
        raise LLMGenerationError(f"Failed to parse LLM output as YAML. Error: {e}")
    except Exception as e:
        raise LLMGenerationError(f"An error occurred while communicating with the LLM: {e}")


def _validate_generated_question(new_question, existing_questions, topic):
    """
    Performs a series of validation checks on the generated question.
    Returns (success: bool, summary: str, details: str).
    """
    validation_summary = ""
    validation_details = ""
    validation_passed = True

    if not isinstance(new_question, dict):
        return False, "Generated output is not a valid question dictionary.", "The LLM did not return a dictionary."

    # Validate documentation source (temporarily disabled as per user request)
    # source_url = new_question.get('source', '')
    # if not (source_url.startswith('https://kubernetes.io/docs/') or source_url.startswith('https://helm.sh/docs/')):
    #     raise MissingFieldsError(f"Invalid documentation source: {source_url} - Must be from kubernetes.io/docs or helm.sh/docs")
        
    # Verify documentation content was actually used (temporarily disabled as per user request)
    # try:
    #     doc_content = requests.get(source_url, timeout=5).text
    #     question_text = new_question.get('question', '')
    #     if not any(keyword in doc_content for keyword in question_text.split()[:5]):
    #         raise MissingFieldsError("Question does not match documentation content")
    # except Exception as e:
    #     print(f"Warning: Could not fetch or process source content for validation: {e}")
    #     pass

    # Check for required fields, including section
    required_fields = ['question', 'suggestion', 'source', 'rationale', 'section']
    missing_fields = [field for field in required_fields if not new_question.get(field)]
    # Infer section from topic if missing
    if 'section' in missing_fields:
        inferred_section = ' '.join([word.capitalize() for word in topic.split('_')])
        inferred_section = inferred_section.replace('Core ', '')
        new_question['section'] = inferred_section
        missing_fields.remove('section')
        print(f"{Fore.YELLOW}  - Inferred section from topic: {inferred_section}{Style.RESET_ALL}")

    if missing_fields:
        raise MissingFieldsError(f"Generated question is missing required fields: {', '.join(missing_fields)}")

    # Check for uniqueness
    normalized_new_q = get_normalized_question_text(new_question)
    for existing_q in existing_questions:
        if get_normalized_question_text(existing_q) == normalized_new_q:
            return False, "Generated question is a duplicate of an existing one.", "The generated question is too similar to an existing question."

    # Determine if the suggestion is a YAML manifest or a command string
    suggestion = new_question.get('suggestion', '')
    is_yaml_manifest = False
    suggestion_str_for_validation = ""

    if isinstance(suggestion, (dict, list)):
        # If suggestion is already a parsed YAML object, dump it to string
        suggestion_str_for_validation = yaml.safe_dump(suggestion, default_flow_style=False, sort_keys=False, indent=4, explicit_start=True)
        is_yaml_manifest = True
    elif isinstance(suggestion, str):
        suggestion_str_for_validation = suggestion
        # Try to parse the string as YAML to confirm if it's a manifest
        try:
            parsed_suggestion = yaml.safe_load(suggestion)
            if isinstance(parsed_suggestion, (dict, list)):
                is_yaml_manifest = True
                # If successfully parsed from a string, re-dump it to ensure proper formatting
                suggestion_str_for_validation = yaml.safe_dump(parsed_suggestion, default_flow_style=False, sort_keys=False, indent=4, explicit_start=True)
        except yaml.YAMLError:
            pass # Not a valid YAML string
    
    if is_yaml_manifest:
        # print("  - Validating generated YAML manifest...", flush=True) # Suppress during retries
        is_valid, summary, details = validate_manifest(suggestion_str_for_validation)
        validation_summary = summary
        validation_details = details
        validation_passed = is_valid
        # if not is_valid: # Suppress during retries
        #     print(f"{Fore.RED}  - Manifest validation failed.{Style.RESET_ALL}", flush=True)
        # else:
        #     print(f"  {Fore.GREEN}- Manifest validation successful.{Style.RESET_ALL}", flush=True)
    else:
        # If it's not a YAML manifest, assume it's a command and validate with LLM
        # print("  - Validating generated command with LLM...", flush=True) # Suppress during retries
        dummy_question_dict = {
            'question': new_question.get('question', 'Generated command question'),
            'suggestion': suggestion_str_for_validation # Pass the command string as suggestion
        }
        ai_result = validate_manifest_with_llm(dummy_question_dict, suggestion_str_for_validation)
        validation_summary = f"LLM Validation: {'Correct' if ai_result['correct'] else 'Incorrect'}"
        validation_details = ai_result['feedback']
        validation_passed = ai_result['correct']
        # if not ai_result['correct']: # Suppress during retries
        #     print(f"{Fore.RED}  - Command validation failed by LLM.{Style.RESET_ALL}", flush=True)
        # else:
        #     print(f"  {Fore.GREEN}- Command validation successful.{Style.RESET_ALL}", flush=True)

    # print(f"  {Fore.GREEN}- Basic validation successful (Required fields present, not a duplicate).{Style.RESET_ALL}", flush=True) # Suppress during retries
    return validation_passed, validation_summary, validation_details


# --- Source Management ---

def assign_source(question_dict, topic, Fore=Fore, Style=Style):
    """
    Searches for and assigns a source URL to a question if it's missing.
    Uses googlesearch if available.
    """
    if 'source' in question_dict and question_dict['source']:
        return False # Source already exists

    if not search:
        # googlesearch library not installed or AI disabled
        # Print a warning when googlesearch is unavailable
        print(f"{Fore.YELLOW}  - Warning: 'googlesearch' library not installed. Cannot automatically find a source.{Style.RESET_ALL}\n")
        return False

    search_query = f"kubernetes {question_dict['question'].splitlines()[0].strip()}"
    try:
        # Attempt to search for a source URL
        # Attempt to search for a source URL
        search_results = list(search(search_query, num_results=1))
        if search_results:
            source_url = search_results[0]
            question_dict['source'] = source_url
            print(f"  {Fore.GREEN}- Found and assigned source: {source_url}{Style.RESET_ALL}")
            return True
        else:
            print(f"{Fore.YELLOW}  - Warning: Could not find a source for the generated question.{Style.RESET_ALL}")
            return False
    except Exception as e:
        # On any error, bail out with a single informative message
        print(f"Note: Could not find source for a question (AI disabled or search error: {e}).")
        return False


# --- Audit and Maintenance ---

def audit_question_files(output_file=os.path.join(USER_DATA_DIR, 'non_standard_questions.log')):
    """
    Audits all question files for conformance to the standard format.
    Logs non-standard questions to the specified output file.
    """
    non_standard_questions = []
    standard_fields = {'question', 'suggestion', 'source'}

    print(f"\n{Style.BRIGHT}--- Auditing All Question Files ---{Style.RESET_ALL}", flush=True)
    for filename in os.listdir(QUESTIONS_DIR):
        if filename.endswith('.yaml'):
            topic = filename.replace('.yaml', '')
            filepath = os.path.join(QUESTIONS_DIR, filename)
            try:
                with open(filepath, 'r') as f:
                    data = yaml.safe_load(f)
                if not data or 'questions' not in data:
                    continue

                for i, q in enumerate(data['questions']):
                    q_fields = set(q.keys())
                    if not standard_fields.issubset(q_fields):
                        non_standard_questions.append({
                            'topic': topic,
                            'question_index': i,
                            'question_text': q.get('question', 'N/A'),
                            'missing_fields': list(standard_fields - q_fields)
                        })
            except Exception as e:
                print(f"{Fore.RED}  - Error processing file {filename}: {e}{Style.RESET_ALL}")

    if non_standard_questions:
        print(f"{Fore.YELLOW}Found {len(non_standard_questions)} non-standard questions.{Style.RESET_ALL}")
        log_content = ""
        for item in non_standard_questions:
            log_entry = (
                f"Topic: {item['topic']}\n"
                f"Index: {item['question_index']}\n"
                f"Question: {item['question_text']}\n"
                f"Missing/Non-standard Fields: {item['missing_fields']}\n"
                f"--------------------\n"
            )
            log_content += log_entry
        
        os.makedirs(USER_DATA_DIR, exist_ok=True)
        with open(output_file, 'w') as f:
            f.write(log_content)
        print(f"Details logged to: {output_file}")
    else:
        print(f"{Fore.GREEN}All questions conform to the standard format.{Style.RESET_ALL}")

    return non_standard_questions