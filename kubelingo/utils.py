import os
import yaml
from yaml import SafeDumper, Dumper

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
                return "---".join(formatted_parts)
    except yaml.YAMLError as e:
        return f"Error: Invalid YAML string provided. {e}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"


