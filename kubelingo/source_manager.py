"""
This module contains functions for generating new, unique, and high-quality
Kubernetes questions for the Kubelingo study tool.
"""

import os
import random
import yaml
import requests
import sys
try:
    from thefuzz import fuzz
except ImportError:
    fuzz = None
from colorama import Fore, Style
import webbrowser # Added for cmd_interactive_sources

try:
    from googlesearch import search
except ImportError:
    search = None

from kubelingo.utils import (_get_llm_model, QUESTIONS_DIR, USER_DATA_DIR, load_questions,
                             get_normalized_question_text, remove_question_from_corpus)
from kubelingo.validation import validate_manifest, validate_manifest_with_llm

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

def generate_more_questions(topic, base_question=None):
    """
    Orchestrates the entire process of generating a new, unique, and validated
    question for a given topic, with retry mechanism.

    Args:
        topic (str): The topic for which to generate a new question.

    Returns:
        dict: The new question dictionary if successful, otherwise None.
    """
    print(f"\n{Style.BRIGHT}{Fore.CYAN}--- Starting New Question Generation for Topic: {topic} ---{Style.RESET_ALL}", flush=True)

    # 1. NEW: Search for question material first
    print("  - Attempting to find existing material from the web...", flush=True)
    potential_sources = _search_for_question_material(topic)
    new_question = None
    validation_passed = False
    validation_summary = ""
    validation_details = ""

    if potential_sources:
        new_question = _create_question_from_sources(potential_sources, topic)

    if new_question:
        print(f"{Fore.GREEN}  - Successfully generated a question from a web source.{Style.RESET_ALL}", flush=True)
        # Validate the generated question
        print("  - Validating the generated question...", flush=True)
        existing_questions_data = load_questions(topic, Fore, Style)
        existing_questions = existing_questions_data.get('questions', []) if existing_questions_data else []
        validation_passed, validation_summary, validation_details = _validate_generated_question(new_question, existing_questions)
    else:
        print(f"{Fore.YELLOW}  - Could not generate a question from web sources, falling back to LLM generation.{Style.RESET_ALL}", flush=True)

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

#         print(f"\nError generating question: {e}")
#         return None
def cmd_add_sources(consolidated_file, questions_dir=QUESTIONS_DIR):
    """Add missing 'source' fields from consolidated YAML."""
    print(f"Loading consolidated questions from '{consolidated_file}'...")
    data = yaml.safe_load(open(consolidated_file)) or {}
    mapping = {}
    for item in data.get('questions', []):
        prompt = item.get('prompt') or item.get('question')
        src = get_source_from_consolidated(item)
        if prompt and src:
            mapping[prompt.strip()] = src
    print(f"Found {len(mapping)} source mappings.")
    for fname in os.listdir(questions_dir):
        if not fname.endswith('.yaml'):
            continue
        path = os.path.join(questions_dir, fname)
        topic = yaml.safe_load(open(path)) or {}
        qs = topic.get('questions', [])
        updated = 0
        for q in qs:
            if q.get('source'):
                continue
            text = q.get('question', '').strip()
            best_src, best_score = None, 0
            for prompt, src in mapping.items():
                r = fuzz.ratio(text, prompt)
                if r > best_score:
                    best_src, best_score = src, r
            if best_score > 95:
                q['source'] = best_src
                updated += 1
                print(f"  + Added source to '{text[:50]}...' -> {best_src}")
        if updated:
            yaml.dump(topic, open(path, 'w'), sort_keys=False)
            print(f"Updated {updated} entries in {fname}.")
    print("Done adding sources.")

def cmd_check_sources(questions_dir=QUESTIONS_DIR):
    """Report questions missing a 'source' field."""
    missing = 0
    for fname in os.listdir(questions_dir):
        if not fname.endswith('.yaml'):
            continue
        path = os.path.join(questions_dir, fname)
        data = yaml.safe_load(open(path)) or {}
        for i, q in enumerate(data.get('questions', []), start=1):
            if not q.get('source'):
                print(f"{fname}: question {i} missing 'source': {q.get('question','')[:80]}")
                missing += 1
    if missing == 0:
        print("All questions have a source.")
    else:
        print(f"{missing} questions missing sources.")

def cmd_interactive_sources(questions_dir=QUESTIONS_DIR, auto_approve=False):
    """
    Performs a series of validation checks on the generated question.
    Returns (success: bool, summary: str, details: str).
    """
    validation_summary = ""
    validation_details = ""
    validation_passed = True

    if not isinstance(new_question, dict):
        return False, "Generated output is not a valid question dictionary.", "The LLM did not return a dictionary."

# def generate_more_questions(topic, question):
#     """Generates more questions based on an existing one."""
#     llm_type, model = _get_llm_model()
#     if not model:
#         print("\nINFO: Set GEMINI_API_KEY or OPENAI_API_KEY environment variables to generate new questions.")
#         return None

#     print("\nGenerating a new question... this might take a moment.")
#     try:
#         question_type = random.choice(['command', 'manifest'])
        
#         # Get all existing questions for the topic to include in the prompt for uniqueness
#         all_existing_questions = load_questions(topic, Fore, Style)
#         existing_questions_list = all_existing_questions.get('questions', []) if all_existing_questions else []
        
#         existing_questions_yaml = ""
#         if existing_questions_list:
#             existing_questions_yaml = "\n        Existing Questions (DO NOT copy these semantically or literally):\n        ---"
#             for eq in existing_questions_list:
#                 existing_questions_yaml += f"        - question: {eq.get('question', '')}\n"
#                 if eq.get('solution'):
#                     existing_questions_yaml += f"          solution: {str(eq.get('solution', ''))[:50]}...\n" # Truncate solution for prompt
#                 existing_questions_yaml += "\n"
#             existing_questions_yaml += "        ---\n"



#         prompt = f'''
#         You are a Kubernetes expert creating questions for a CKAD study guide.
#         Based on the following example question about '{topic}', please generate one new, distinct but related question.
#         The new question MUST be unique and not a semantic or literal copy of any existing questions provided.

#         Example Question:
#         ---
# {yaml.safe_dump({'questions': [question]})}        ---

#         {existing_questions_yaml}
#         Your new question should be a {question_type}-based question.
#         - If it is a 'command' question, the suggestion should be a single or multi-line shell command (e.g., kubectl).
#         - If it is a 'manifest' question, the suggestion should be a complete YAML manifest and the question should be phrased to ask for a manifest.

#         The new question should be in the same topic area but test a slightly different aspect or use different parameters.
#         Provide the output in valid YAML format, as a single item in a 'questions' list.
#         The output must include a 'source' field with a valid URL pointing to the official Kubernetes documentation or a highly reputable source that justifies the answer.
#         The solution must be correct and working.
#         If a 'starter_manifest' is provided, it must use the literal block scalar style (e.g., 'starter_manifest: |').
#         Also, include a brief 'rationale' field explaining why this question is relevant for CKAD and what it tests.

#         Example for a manifest question:
#         questions:
#           - question: "Create a manifest for a Pod named 'new-pod'"
#             solution: |
#               apiVersion: v1
#               kind: Pod
#               metadata:
#                 name: new-pod
#             source: "https://kubernetes.io/docs/concepts/workloads/pods/"
#             rationale: "Tests basic Deployment creation and YAML syntax."

#         Example for a command question:
#         questions:
#           - question: "Create a pod named 'new-pod' imperatively..."
#             solution: "kubectl run new-pod --image=nginx"
#             source: "https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#run"
#             rationale: "Tests imperative command usage for Pod creation."
#         '''
#         if llm_type == "gemini":
#             response = model.generate_content(prompt)
#         elif llm_type == "openai":
#             response = model.chat.completions.create(
#                 model="gpt-3.5-turbo", # Or another suitable model
#                 messages=[
#                     {"role": "system", "content": "You are a Kubernetes expert creating questions for a CKAD study guide."},
#                     {"role": "user", "content": prompt}
#                 ]
#             )
#             response.text = response.choices[0].message.content # Normalize response for consistent parsing
#         elif llm_type == "openrouter":
#             resp = requests.post(
#                 "https://openrouter.ai/api/v1/chat/completions",
#                 headers=model["headers"],
#                 json={
#                     "model": model["default_model"],
#                     "messages": [
#                         {"role": "system", "content": "You are a Kubernetes expert creating questions for a CKAD study guide."},
#                         {"role": "user", "content": prompt}
#                     ]
#                 }
#             )
#             resp.raise_for_status()
#             response = type("obj", (object,), {'text': resp.json()['choices'][0]['message']['content']}) # Create a dummy object with .text attribute

#         # Clean the response to only get the YAML part
#         cleaned_response = response.text.strip()
#         if cleaned_response.startswith('```yaml'):
#             cleaned_response = cleaned_response[7:]
#         if cleaned_response.endswith('```'):
#             cleaned_response = cleaned_response[:-3]

#         try:
#             new_question_data = yaml.safe_load(cleaned_response)
#         except yaml.YAMLError:
#             print("\nAI failed to generate a valid question (invalid YAML). Please try again.")
#             return None
        
#         if new_question_data and 'questions' in new_question_data and new_question_data['questions']:
#             new_q = new_question_data['questions'][0]

#             # Uniqueness check
#             normalized_new_q_text = get_normalized_question_text(new_q)
#             for eq in existing_questions_list:
#                 if get_normalized_question_text(eq) == normalized_new_q_text:
#                     print(f"{Fore.YELLOW}\nGenerated question is a duplicate. Retrying...{Style.RESET_ALL}")
#                     return None # Indicate failure to generate a unique question

#             # Ensure 'source' field exists
#             if not new_q.get('source'):
#                 print(f"{Fore.YELLOW}\nGenerated question is missing a 'source' field. Attempting to find one...{Style.RESET_ALL}")
#                 if not assign_source(new_q, topic, Fore, Style):
#                     print(f"{Fore.RED}Failed to assign a source to the generated question.{Style.RESET_ALL}")
#                     return None
            
#             # Normalize generated question: clean whitespace in solution
#             if 'solution' in new_q and isinstance(new_q['solution'], str):
#                 new_q['solution'] = new_q['solution'].strip()

#             print("\nNew question generated!")
#             return new_q
#         else:
#             print("\nAI failed to generate a valid question. Please try again.")
#             return None
#     except Exception as e:

# # --- Source Management Commands ---
# def get_source_from_consolidated(item):
#     metadata = item.get('metadata', {}) or {}
#     for key in ('links', 'source', 'citation'):
#         if key in metadata and metadata[key]:
#             val = metadata[key]
#             return val[0] if isinstance(val, list) else val
#     return None


# # --- Question Generation ---

#     """
#     Generates more questions based on an existing one."""
#     llm_type, model = _get_llm_model()
#     if not model:
#         print("\nINFO: Set GEMINI_API_KEY or OPENAI_API_KEY environment variables to generate new questions.")
#         return None

#     print("\nGenerating a new question... this might take a moment.")
#     try:
#         question_type = random.choice(['command', 'manifest'])
#         prompt = f'''
#         You are a Kubernetes expert creating questions for a CKAD study guide.
#         Based on the following example question about '{topic}', please generate one new, distinct but related question.

#         Example Question:
#         ---
#         {yaml.safe_dump({'questions': [question]})}
#         ---

#         Your new question should be a {question_type}-based question.
#         - If it is a 'command' question, the suggestion should be a single or multi-line shell command (e.g., kubectl).
#         - If it is a 'manifest' question, the suggestion should be a complete YAML manifest and the question should be phrased to ask for a manifest.

#         The new question should be in the same topic area but test a slightly different aspect or use different parameters.
#         Provide the output in valid YAML format, as a single item in a 'questions' list.
#         The output must include a 'source' field with a valid URL pointing to the official Kubernetes documentation or a highly reputable source that justifies the answer.
#         The solution must be correct and working.
#         If a 'starter_manifest' is provided, it must use the literal block scalar style (e.g., 'starter_manifest: |').

#         Example for a manifest question:
#         questions:
#           - question: "Create a manifest for a Pod named 'new-pod'"
#             solution: |
#               apiVersion: v1
#               kind: Pod
#               ...
#             source: "https://kubernetes.io/docs/concepts/workloads/pods/"

#         Example for a command question:
#         questions:
#           - question: "Create a pod named 'new-pod' imperatively..."
#             solution: "kubectl run new-pod --image=nginx"
#             source: "https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#run"
#         '''
#         if llm_type == "gemini":
#             response = model.generate_content(prompt)
#         elif llm_type == "openai" or llm_type == "openrouter":
#             response = model.chat.completions.create(
#                 model="gpt-3.5-turbo", # Or another suitable model
#                 messages=[
#                     {"role": "system", "content": "You are a Kubernetes expert creating questions for a CKAD study guide."},
#                     {"role": "user", "content": prompt}
#                 ]
#             )
#             response.text = response.choices[0].message.content # Normalize response for consistent parsing

#         # Clean the response to only get the YAML part
#         cleaned_response = response.text.strip()
#         if cleaned_response.startswith('```yaml'):
#             cleaned_response = cleaned_response[7:]
#         if cleaned_response.endswith('```'):
#             cleaned_response = cleaned_response[:-3]

#         try:
#             new_question_data = yaml.safe_load(cleaned_response)
#         except yaml.YAMLError:
#             print("\nAI failed to generate a valid question. Please try again.")
#             return None
        
    # Verify documentation content was actually used
    doc_content = requests.get(source_url).text
    question_text = new_question.get('question', '')
    if not any(keyword in doc_content for keyword in question_text.split()[:5]):
        raise MissingFieldsError("Question does not match documentation content")
        
    # Check for required fields
    required_fields = ['question', 'suggestion', 'source', 'rationale']
    missing_fields = [field for field in required_fields if not new_question.get(field)]
    
    # Try to infer section from topic if missing
    if 'section' in missing_fields:
        # Split topic on underscores and capitalize first letters
        inferred_section = ' '.join([word.capitalize() for word in topic.split('_')])
        # Remove any "Core" prefix that's common in topic names
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
