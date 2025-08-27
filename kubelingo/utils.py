import os
import yaml
from colorama import Fore, Style
import sys # For print statements
try:
    import google.generativeai as genai
except ImportError:
    genai = None

# Assuming QUESTIONS_DIR is defined elsewhere or passed
# For now, I'll define it here, and then remove it from kubelingo.py
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, os.pardir))
_ROOT_QUESTIONS = os.path.join(_PROJECT_ROOT, "questions")
_PKG_QUESTIONS = os.path.join(_SCRIPT_DIR, "questions")
QUESTIONS_DIR = os.getenv(
    "KUBELINGO_QUESTIONS_DIR",
    _ROOT_QUESTIONS if os.path.isdir(_ROOT_QUESTIONS) else _PKG_QUESTIONS
)

import openai
import requests
from dotenv import load_dotenv, dotenv_values

def _get_llm_model(skip_prompt=False):
    """
    Initializes and returns the generative AI model based on configured provider.
    Returns a tuple: (llm_type_string, model_object) or (None, None)
    """
    load_dotenv() # Ensure .env is loaded
    config = dotenv_values()
    llm_provider = os.getenv("KUBELINGO_LLM_PROVIDER", "").lower()

    if llm_provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            if not skip_prompt:
                print(f"{Fore.RED}GEMINI_API_KEY not found in environment variables.{Style.RESET_ALL}")
            return None, None
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash-latest")
            # Test model availability
            model.generate_content("hello", safety_settings={'HARASSMENT': 'BLOCK_NONE'})
            return "gemini", model
        except Exception as e:
            if not skip_prompt:
                print(f"{Fore.RED}Error initializing Gemini model: {e}{Style.RESET_ALL}")
            return None, None
    elif llm_provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            if not skip_prompt:
                print(f"{Fore.RED}OPENAI_API_KEY not found in environment variables.{Style.RESET_ALL}")
            return None, None
        try:
            openai.api_key = api_key
            model = openai.OpenAI()
            # Test model availability
            model.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": "hi"}])
            return "openai", model
        except Exception as e:
            if not skip_prompt:
                print(f"{Fore.RED}Error initializing OpenAI model: {e}{Style.RESET_ALL}")
            return None, None
    elif llm_provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            if not skip_prompt:
                print(f"{Fore.RED}OPENROUTER_API_KEY not found in environment variables.{Style.RESET_ALL}")
            return None, None
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://github.com/your-username/kubelingo", # Replace with your actual GitHub repo URL
                "X-Title": "Kubelingo",
            }
            # OpenRouter doesn't have a direct client object like genai or openai
            # We return a dict with necessary info for requests.post
            model_info = {
                "headers": headers,
                "default_model": "deepseek/deepseek-chat", # Or another preferred OpenRouter model
            }
            # Test model availability with a dummy request
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json={
                    "model": model_info["default_model"],
                    "messages": [{"role": "user", "content": "hi"}],
                }
            )
            response.raise_for_status()
            return "openrouter", model_info
        except Exception as e:
            if not skip_prompt:
                print(f"{Fore.RED}Error initializing OpenRouter model: {e}{Style.RESET_ALL}")
            return None, None
    else:
        if not skip_prompt:
            print(f"{Fore.YELLOW}No LLM provider configured. Please set KUBELINGO_LLM_PROVIDER in your .env file.{Style.RESET_ALL}")
        return None, None


def get_normalized_question_text(question_dict):
    return question_dict.get('question', '').strip().lower()

def load_questions(topic, Fore, Style): # Removed genai as argument
    """Loads questions from a YAML file based on the topic."""
    file_path = os.path.join(QUESTIONS_DIR, f"{topic}.yaml")
    if not os.path.exists(file_path):
        print(f"Error: Question file not found at {file_path}")
        available_topics = [f.replace('.yaml', '') for f in os.listdir(QUESTIONS_DIR) if f.endswith('.yaml')]
        if available_topics:
            print("Available topics: " + ", ".join(available_topics))
        return None
    
    with open(file_path, 'r') as file:
        data = yaml.safe_load(file)
    
    if data and 'questions' in data:
        updated = False
        # Import assign_source locally to avoid circular dependency
        from kubelingo.question_generator import assign_source
        for q in data['questions']:
            if assign_source(q, topic, Fore, Style): # Removed genai
                updated = True
        
        if updated:
            with open(file_path, 'w') as file:
                yaml.dump(data, file, sort_keys=False)
    
    return data

def remove_question_from_corpus(question_to_remove, topic):
    """Removes a question from its source YAML file."""
    file_path = os.path.join(QUESTIONS_DIR, f"{topic}.yaml")
    if not os.path.exists(file_path):
        print(f"{Fore.RED}Error: Source file not found for topic {topic}. Cannot remove question.{Style.RESET_ALL}")
        return

    with open(file_path, 'r') as file:
        data = yaml.safe_load(file)

    if data and 'questions' in data:
        original_num_questions = len(data['questions'])
        normalized_q_to_remove = get_normalized_question_text(question_to_remove)
        
        # Filter out the question to remove
        data['questions'] = [
            q for q in data['questions']
            if get_normalized_question_text(q) != normalized_q_to_remove
        ]

        if len(data['questions']) < original_num_questions:
            with open(file_path, 'w') as file:
                yaml.dump(data, file, sort_keys=False)
            print(f"{Fore.GREEN}Question removed from {topic}.yaml.{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}Question not found in {topic}.yaml. No changes made.{Style.RESET_ALL}")
    else:
        print(f"{Fore.YELLOW}No questions found in {topic}.yaml. No changes made.{Style.RESET_ALL}")

import copy

def _normalize_manifest(obj):
    """
    Deep-copy a manifest object and remove non-essential fields (names) for equivalence comparison.
    """
    m = copy.deepcopy(obj)
    if isinstance(m, dict):
        # Remove top-level metadata name
        if 'metadata' in m and isinstance(m['metadata'], dict):
            m['metadata'].pop('name', None)
        # Remove container names
        spec = m.get('spec')
        if isinstance(spec, dict):
            containers = spec.get('containers')
            if isinstance(containers, list):
                for c in containers:
                    if isinstance(c, dict):
                        c.pop('name', None)
        return m
    if isinstance(m, list):
        return [_normalize_manifest(item) for item in m]
    return m

def manifests_equivalent(sol_obj, user_obj):
    """
    Compare two manifest objects for structural equivalence, ignoring names.
    """
    normalized_sol = _normalize_manifest(sol_obj)
    normalized_user = _normalize_manifest(user_obj)
    print(f"KUBELINGO DEBUG: normalized_sol: {normalized_sol}")
    print(f"KUBELINGO DEBUG: normalized_user: {normalized_user}")
    return normalized_sol == normalized_user
