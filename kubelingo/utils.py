import os
import yaml
from yaml import SafeDumper, Dumper
import subprocess # Import subprocess here

def ensure_user_data_dir():
    """Ensures the user_data directory exists."""
    os.makedirs(USER_DATA_DIR, exist_ok=True)

# Represent multiline strings as literal blocks in YAML dumps
def _str_presenter(dumper, data):
    # Use literal block style for strings containing newlines
    style = '|' if isinstance(data, str) and '\n' in data else None
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style=style)

SafeDumper.add_representer(str, _str_presenter)
Dumper.add_representer(str, _str_presenter)
try:
    from colorama import Fore, Style
except ImportError:
    class Fore:
        RED = YELLOW = GREEN = CYAN = ''
    class Style:
        BRIGHT = RESET_ALL = DIM = ''
    def colorama_init(*args, **kwargs):
        pass
import sys # For print statements
try:
    import google.generativeai as genai
except ImportError:
    genai = None

# Define _PROJECT_ROOT globally
def _get_git_root():
    try:
        return subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], stderr=subprocess.PIPE).strip().decode('utf-8')
    except subprocess.CalledProcessError:
        return None

_PROJECT_ROOT = _get_git_root()
if not _PROJECT_ROOT:
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    _PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, os.pardir, os.pardir)) # Fallback to two levels up if not in git repo

_ROOT_QUESTIONS = os.path.join(_PROJECT_ROOT, "questions")
_PKG_QUESTIONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "questions")
QUESTIONS_DIR = os.getenv(
    "KUBELINGO_QUESTIONS_DIR",
    _ROOT_QUESTIONS if os.path.isdir(_ROOT_QUESTIONS) else _PKG_QUESTIONS
)
USER_DATA_DIR = os.path.join(_PROJECT_ROOT, "user_data")
MISSED_QUESTIONS_FILE = os.path.join(USER_DATA_DIR, "missed_questions.yaml")
ISSUES_FILE = os.path.join(USER_DATA_DIR, "issues.yaml")
PERFORMANCE_FILE = os.path.join(USER_DATA_DIR, "performance.yaml")

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

def get_canonical_question_representation(question_dict):
    """Create a consistent representation including documentation source validation."""
    # Validate source URL first
    source_url = question_dict.get('source', '')
    if not source_url.startswith('https://kubernetes.io/docs/'):
        raise ValueError("Question source must be from official Kubernetes documentation")
        
    q_text = question_dict.get('question', '').strip().lower()
    suggestion = question_dict.get('suggestion', '')
    source = question_dict.get('source', '')

    # Handle suggestion being a dict/list (YAML) or string (command)
    if isinstance(suggestion, (dict, list)):
        suggestion_str = yaml.safe_dump(suggestion, default_flow_style=False, sort_keys=True, indent=0).strip().lower()
    elif isinstance(suggestion, str):
        suggestion_str = suggestion.strip().lower()
    else:
        suggestion_str = ''

    return f"{q_text}::{suggestion_str}::{source.strip().lower()}"

def load_questions(topic, Fore, Style): # Removed genai as argument
    """Loads questions from a YAML file based on the topic."""
    file_path = os.path.join(QUESTIONS_DIR, f"{topic}.yaml")
    if not os.path.exists(file_path):
        print(f"Error: Question file not found at {file_path}")
        available_topics = [f.replace('.yaml', '') for f in os.listdir(QUESTIONS_DIR) if os.path.isfile(os.path.join(QUESTIONS_DIR, f)) and f.endswith('.yaml')]
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
    # Debug: Write the question to a file
    with open(os.path.join(USER_DATA_DIR, 'debug_question.yaml'), 'w') as f:
        yaml.dump(question_to_remove, f)

    file_path = os.path.join(QUESTIONS_DIR, f"{topic}.yaml")
    if not os.path.exists(file_path):
        print(f"{Fore.RED}Error: Source file not found for topic {topic}. Cannot remove question.{Style.RESET_ALL}")
        return

    with open(file_path, 'r') as file:
        data = yaml.safe_load(file)

    if data and 'questions' in data:
        original_num_questions = len(data['questions'])
        canonical_q_to_remove = get_canonical_question_representation(question_to_remove)
        
        # Filter out the question to remove
        data['questions'] = [
            q for q in data['questions']
            if get_canonical_question_representation(q) != canonical_q_to_remove
        ]

        if len(data['questions']) < original_num_questions:
            with open(file_path, 'w') as file:
                yaml.dump(data, file, sort_keys=False)
            print(f"{Fore.GREEN}Question removed from {topic}.yaml.{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}Question was not found in its original topic file ({topic}.yaml). No changes made to the topic file.{Style.RESET_ALL}")
    else:
        print(f"{Fore.YELLOW}No questions found in {topic}.yaml. No changes made.{Style.RESET_ALL}")

def format_yaml_string(yaml_string):
    """
    Formats a YAML string, handling escaped newlines and ensuring proper indentation.
    """
    try:
        # Unescape newlines
        # Handle specific malformed document separators from user's example
        unescaped_string = yaml_string.replace('nn ---nn', '\n---\n')
        
        # Remove comment lines before loading
        lines = unescaped_string.splitlines()
        cleaned_lines = [line for line in lines if not line.strip().startswith('#')]
        cleaned_string = '\n'.join(cleaned_lines)

        # Load and then dump to reformat
        loaded_yamls = list(yaml.safe_load_all(cleaned_string))
        formatted_parts = []
        for doc in loaded_yamls:
            if doc is not None: # Handle empty documents
                formatted_parts.append(yaml.safe_dump(doc, indent=2, default_flow_style=False, sort_keys=False))
                return "---".join(formatted_parts) # Added newline after ---
    except yaml.YAMLError as e:
        return f"Error: Invalid YAML string provided. {e}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"


import shutil

def backup_performance_yaml(project_root=None, user_data_dir=None):
    """
    Back up the performance.yaml file from user_data_dir to the project's misc directory.
    If project_root or user_data_dir are not provided, use defaults from module globals.
    """
    # Determine defaults if not provided
    if project_root is None:
        project_root = _PROJECT_ROOT
    if user_data_dir is None:
        user_data_dir = USER_DATA_DIR
    source_path = os.path.join(user_data_dir, 'performance.yaml')
    destination_dir = os.path.join(project_root, 'misc')
    destination_path = os.path.join(destination_dir, 'performance.yaml')

    if not os.path.exists(source_path):
        # No performance data to back up; skip without error
        return

    os.makedirs(destination_dir, exist_ok=True)

    try:
        shutil.copyfile(source_path, destination_path)
        print(f"Successfully backed up {source_path} to {destination_path}")
    except Exception as e:
        print(f"Error backing up file: {e}")