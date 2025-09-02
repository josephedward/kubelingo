# This module will contain functions for generating new questions.

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

from kubelingo.utils import _get_llm_model, QUESTIONS_DIR, load_questions, get_normalized_question_text

def assign_source(question_dict, topic, Fore, Style):
    """
    Searches for and assigns a source URL to a question if it's missing.
    Returns True if a source was assigned, False otherwise.
    """
    if 'source' not in question_dict or not question_dict['source']:
        if search: # Check if googlesearch is available
            search_query = f"kubernetes {question_dict['question'].splitlines()[0].strip()}" # Use first line of question as query
            try:
                # Get the first search result URL
                search_results = list(search(search_query, num_results=1))
                if search_results:
                    question_dict['source'] = search_results[0]
                    return True
            except Exception as e:
                # Handle potential errors during search (e.g., network issues)
                llm_type, model = _get_llm_model(skip_prompt=True)
                if model is None: # Check if AI is disabled
                    print(f"{Fore.YELLOW}Note: Could not find source for a question (AI disabled or search error: {e}).{Style.RESET_ALL}")
        else:
            llm_type, model = _get_llm_model(skip_prompt=True)
            if model is None: # Check if AI is disabled
                print(f"{Fore.YELLOW}Note: Could not find source for a question (googlesearch not installed and AI disabled).{Style.RESET_ALL}")
    return False

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
    Interactively search and assign sources to questions."""
    for fname in os.listdir(questions_dir):
        if not fname.endswith('.yaml'):
            continue
        path = os.path.join(questions_dir, fname)
        data = yaml.safe_load(open(path)) or {}
        qs = data.get('questions', [])
        modified = False
        for idx, q in enumerate(qs, start=1):
            if q.get('source'):
                continue
            text = q.get('question','').strip()
            print(f"\nFile: {fname} | Question {idx}: {text}")
            if auto_approve:
                if not search:
                    print("  googlesearch not available.")
                    continue
                try:
                    results = list(search(f"kubernetes {text}", num_results=1))
                except Exception as e:
                    print(f"  Search error: {e}")
                    continue
                if results:
                    q['source'] = results[0]
                    print(f"  Auto-set source: {results[0]}")
                    modified = True
                continue
            if not search:
                print("  Install googlesearch-python to enable search.")
                return
            print("  Searching for sources...")
            try:
                results = list(search(f"kubernetes {text}", num_results=5))
            except Exception as e:
                print(f"  Search error: {e}")
                continue
            if not results:
                print("  No results found.")
                continue
            for i, url in enumerate(results, 1):
                print(f"    {i}. {url}")
            choice = input("  Choose default [1] or enter number, [o]pen all, [s]kip: ").strip().lower()
            if choice == 'o':
                for url in results:
                    webbrowser.open(url)
                choice = '1'
            if choice.isdigit() and 1 <= int(choice) <= len(results):
                sel = results[int(choice)-1]
                q['source'] = sel
                print(f"  Selected source: {sel}")
                modified = True
        if modified:
            yaml.dump(data, open(path, 'w'), sort_keys=False)
            print(f"Saved updates to {fname}.")
    print("Interactive source session complete.")


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
        
#         if new_question_data and 'questions' in new_question_data and new_question_data['questions']:
#             new_q = new_question_data['questions'][0]
#             print("\nNew question generated!")
#             return new_q
#         else:
#             print("\nAI failed to generate a valid question. Please try again.")
#             return None
#     except Exception as e:
#         print(f"\nError generating question: {e}")
#         return None
