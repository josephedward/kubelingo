import os
import sys
import requests
import getpass
import random
import readline
import time
import yaml
import argparse
try:
    import google.generativeai as genai
    from google.api_core import exceptions as google_exceptions
except ImportError:
    genai = None
    google_exceptions = None
try:
    import openai
    from openai import AuthenticationError
except ImportError:
    openai = None
    AuthenticationError = Exception
from thefuzz import fuzz
import tempfile
import subprocess
import difflib
import copy
from colorama import Fore, Style, init as colorama_init

def clear_screen():
    """Clears the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

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
    return _normalize_manifest(sol_obj) == _normalize_manifest(user_obj)


def colorize_ascii_art(ascii_art_string):
    """Applies a green and cyan pattern to the ASCII art string."""
    colors = [Fore.GREEN, Fore.CYAN] # Use only green and cyan
    
    lines = ascii_art_string.splitlines()
    colored_lines = []
    
    for i, line in enumerate(lines):
        color = colors[i % len(colors)] # Alternate colors per line
        colored_lines.append(f"{color}{line}{Style.RESET_ALL}")
    return "\n".join(colored_lines)
from pygments import highlight
from pygments.lexers import YamlLexer
from pygments.formatters import TerminalFormatter
from dotenv import load_dotenv, dotenv_values, set_key
import click
import sys
import logging
# Debug helper: enable by setting environment variable KUBELINGO_DEBUG=1 or true
DEBUG = os.getenv('KUBELINGO_DEBUG', 'False').lower() in ('1', 'true')
def dbg(msg):
    if DEBUG:
        print(f"[DEBUG] {msg}", file=sys.stderr)
import webbrowser
try:
    from googlesearch import search
except ImportError:
    search = None

# Determine questions directory: prefer project-root 'questions' when present, else package-relative
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, os.pardir))
# Directory alongside project root (for local development)
_ROOT_QUESTIONS = os.path.join(_PROJECT_ROOT, "questions")
# Package-relative questions (if bundled in installation)
_PKG_QUESTIONS = os.path.join(_SCRIPT_DIR, "questions")
# Allow override via environment variable
QUESTIONS_DIR = os.getenv(
    "KUBELINGO_QUESTIONS_DIR",
    _ROOT_QUESTIONS if os.path.isdir(_ROOT_QUESTIONS) else _PKG_QUESTIONS
)

ASCII_ART = r"""
                                      bbbbbbbb
KKKKKKKKK    KKKKKKK                  b::::::b                                lllllll   iiii
K:::::::K    K:::::K                  b::::::b                                l:::::l  i::::i
K:::::::K    K:::::K                  b::::::b                                l:::::l   iiii
K:::::::K   K::::::K                   b:::::b                                l:::::l
KK::::::K  K:::::KKKuuuuuu    uuuuuu   b:::::bbbbbbbbb        eeeeeeeeeeee     l::::l iiiiiii nnnn  nnnnnnnn       ggggggggg   ggggg   ooooooooooo
  K:::::K K:::::K   u::::u    u::::u   b::::::::::::::bb    ee::::::::::::ee   l::::l i:::::i n:::nn::::::::nn    g:::::::::ggg::::g oo:::::::::::oo
  K::::::K:::::K    u::::u    u::::u   b::::::::::::::::b  e::::::eeeee:::::ee l::::l  i::::i n::::::::::::::nn  g:::::::::::::::::go:::::::::::::::o
  K:::::::::::K     u::::u    u::::u   b:::::bbbbb:::::::be::::::e     e:::::e l::::l  i::::i nn:::::::::::::::ng::::::ggggg::::::ggo:::::ooooo:::::o
  K:::::::::::K     u::::u    u::::u   b:::::b    b::::::be:::::::eeeee::::::e l::::l  i::::i   n:::::nnnn:::::ng:::::g     g:::::g o::::o     o::::o
  K::::::K:::::K    u::::u    u::::u   b:::::b     b:::::be:::::::::::::::::e  l::::l  i::::i   n::::n    n::::ng:::::g     g:::::g o::::o     o::::o
  K:::::K K:::::K   u::::u    u::::u   b:::::b     b:::::be::::::eeeeeeeeeee   l::::l  i::::i   n::::n    n::::ng:::::g     g:::::g o::::o     o::::o
KK::::::K  K:::::KKKu:::::uuuu:::::u   b:::::b     b:::::be:::::::e            l::::l  i::::i   n::::n    n::::ng::::::g    g:::::g o:::::ooooo:::::o
K:::::::K   K::::::Ku:::::::::::::::uu b:::::bbbbbb::::::be::::::::e          l::::::li::::::i  n::::n    n::::ng:::::::ggggg:::::g o:::::ooooo:::::o
K:::::::K    K:::::K u:::::::::::::::u b::::::::::::::::b  e::::::::eeeeeeee  l::::::li::::::i  n::::n    n::::n g::::::::::::::::g o:::::::::::::::o
K:::::::K    K:::::K  uu::::::::uu:::u b:::::::::::::::b    ee:::::::::::::e  l::::::li::::::i  n::::n    n::::n  gg::::::::::::::g  oo:::::::::::oo
KKKKKKKKK    KKKKKKK    uuuuuuuu  uuuu bbbbbbbbbbbbbbbb       eeeeeeeeeeeeee  lllllllliiiiiiii  nnnnnn    nnnnnn    gggggggg::::::g    ooooooooooo
                                                                                                                            g:::::g
                                                                                                                gggggg      g:::::g
                                                                                                                g:::::gg   gg:::::g
                                                                                                                 g::::::ggg:::::::g
                                                                                                                  gg:::::::::::::g
                                                                                                                    ggg::::::ggg
                                                                                                                       gggggg                    """

USER_DATA_DIR = "user_data"

def colorize_yaml(yaml_string):
    """Syntax highlights a YAML string."""
    return highlight(yaml_string, YamlLexer(), TerminalFormatter())

def show_diff(text1, text2, fromfile='your_submission', tofile='solution'):
    """Prints a colorized diff of two texts."""
    diff = difflib.unified_diff(
        text1.splitlines(keepends=True),
        text2.splitlines(keepends=True),
        fromfile=fromfile,
        tofile=tofile,
    )
    print(f"\n{Style.BRIGHT}{Fore.YELLOW}--- Diff ---{Style.RESET_ALL}")
    for line in diff:
        line = line.rstrip()
        if line.startswith('+') and not line.startswith('+++'):
            print(f'{Fore.GREEN}{line}{Style.RESET_ALL}')
        elif line.startswith('-') and not line.startswith('---'):
            print(f'{Fore.RED}{line}{Style.RESET_ALL}')
        elif line.startswith('@@'):
            print(f'{Fore.CYAN}{line}{Style.RESET_ALL}')
        else:
            print(line)

MISSED_QUESTIONS_FILE = os.path.join(USER_DATA_DIR, "missed_questions.yaml")
ISSUES_FILE = os.path.join(USER_DATA_DIR, "issues.yaml")
PERFORMANCE_FILE = os.path.join(USER_DATA_DIR, "performance.yaml")
MISC_DIR = "misc"
PERFORMANCE_BACKUP_FILE = os.path.join(MISC_DIR, "performance.yaml")

def ensure_user_data_dir():
    """Ensures the user_data directory exists."""
    os.makedirs(USER_DATA_DIR, exist_ok=True)

def ensure_misc_dir():
    """Ensures the misc directory exists."""
    os.makedirs(MISC_DIR, exist_ok=True)

def backup_performance_file():
    """Backs up the performance.yaml file to misc/performance.yaml."""
    ensure_misc_dir()
    if os.path.exists(PERFORMANCE_FILE):
        try:
            with open(PERFORMANCE_FILE, 'rb') as src, open(PERFORMANCE_BACKUP_FILE, 'wb') as dst:
                dst.write(src.read())
        except Exception as e:
            print(f"Error backing up performance file: {e}")

def load_performance_data():
    """Loads performance data from the user data directory."""
    ensure_user_data_dir()
    if not os.path.exists(PERFORMANCE_FILE):
        # If file doesn't exist, initialize with empty dict and save
        with open(PERFORMANCE_FILE, 'w') as f_init:
            yaml.dump({}, f_init)
        return {}
    try:
        with open(PERFORMANCE_FILE, 'r') as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError:
        print(f"{Fore.YELLOW}Warning: Performance data file '{PERFORMANCE_FILE}' is corrupted or invalid. Using empty data.{Style.RESET_ALL}")
        return {}
    # Ensure the loaded data is a mapping; otherwise ignore and preserve file
    if not isinstance(data, dict):
        print(f"{Fore.YELLOW}Warning: Performance data file '{PERFORMANCE_FILE}' has unexpected format. Using empty data.{Style.RESET_ALL}")
        return {}
    # Return the loaded data, or empty dict if none
    return data or {}

def save_performance_data(data):
    """Saves performance data."""
    ensure_user_data_dir()
    try:
        with open(PERFORMANCE_FILE, 'w') as f:
            yaml.dump(data, f)
    except Exception as e:
        print(f"{Fore.RED}Error saving performance data to '{PERFORMANCE_FILE}': {e}{Style.RESET_ALL}")

def save_questions_to_topic_file(topic, questions_data):
    """Saves questions data to the specified topic YAML file."""
    ensure_user_data_dir() # This ensures user_data, but questions are in QUESTIONS_DIR
    topic_file = os.path.join(QUESTIONS_DIR, f"{topic}.yaml")
    with open(topic_file, 'w') as f:
        yaml.dump({'questions': questions_data}, f, sort_keys=False)

def save_question_to_list(list_file, question, topic):
    """Saves a question to a specified list file."""
    ensure_user_data_dir()
    questions = []
    if os.path.exists(list_file):
        with open(list_file, 'r') as f:
            try:
                questions = yaml.safe_load(f) or []
            except yaml.YAMLError:
                questions = []

    # Avoid duplicates
    normalized_new_question = get_normalized_question_text(question)
    if not any(get_normalized_question_text(q_in_list) == normalized_new_question for q_in_list in questions):
        question_to_save = question.copy()
        question_to_save['original_topic'] = topic
        questions.append(question_to_save)
        with open(list_file, 'w') as f:
            yaml.dump(questions, f)

def remove_question_from_list(list_file, question):
    """Removes a question from a specified list file."""
    ensure_user_data_dir()
    questions = []
    if os.path.exists(list_file):
        with open(list_file, 'r') as f:
            try:
                questions = yaml.safe_load(f) or []
            except yaml.YAMLError:
                questions = []

    normalized_question_to_remove = get_normalized_question_text(question)
    updated_questions = [q for q in questions if get_normalized_question_text(q) != normalized_question_to_remove]

    with open(list_file, 'w') as f:
        yaml.dump(updated_questions, f)

def update_question_source_in_yaml(topic, updated_question):
    """Updates the source of a specific question in its topic YAML file."""
    ensure_user_data_dir()
    topic_file = os.path.join(QUESTIONS_DIR, f"{topic}.yaml")
    
    if not os.path.exists(topic_file):
        print(f"Error: Topic file not found at {topic_file}. Cannot update source.")
        return

    with open(topic_file, 'r+') as f:
        data = yaml.safe_load(f) or {'questions': []}
        
        found = False
        for i, question_in_list in enumerate(data['questions']):
            if get_normalized_question_text(question_in_list) == get_normalized_question_text(updated_question):
                data['questions'][i]['source'] = updated_question['source']
                found = True
                break
        
        if found:
            f.seek(0)
            yaml.dump(data, f)
            f.truncate()
            print(f"Source for question '{updated_question['question']}' updated in {topic}.yaml.")
        else:
            print(f"Warning: Question '{updated_question['question']}' not found in {topic}.yaml. Source not updated.")

def create_issue(question_dict, topic):
    """Prompts user for an issue and saves it to a file."""
    ensure_user_data_dir()
    # Dynamically determine issues file based on current user data directory
    issues_file = os.path.join(USER_DATA_DIR, "issues.yaml")
    print("\nPlease describe the issue with the question.")
    issue_desc = input("Description: ")
    if issue_desc.strip():
        # Add the entire question to the issue
        question_dict['issue'] = issue_desc.strip()
        question_dict['timestamp'] = time.asctime()
        # Include topic in issue record
        question_dict['topic'] = topic

        issues = []
        if os.path.exists(issues_file):
            with open(issues_file, 'r') as f:
                try:
                    issues = yaml.safe_load(f) or []
                except yaml.YAMLError:
                    issues = []
        
        issues.append(question_dict)

        with open(issues_file, 'w') as f:
            yaml.dump(issues, f)
        
        # Remove the question from the topic file in QUESTIONS_DIR
        topic_file = os.path.join(QUESTIONS_DIR, f"{topic}.yaml")
        try:
            from pathlib import Path
            if Path(topic_file).exists():
                with open(topic_file, 'r') as f:
                    data = yaml.safe_load(f) or {'questions': []}
                if 'questions' in data:
                    data['questions'] = [q for q in data['questions'] if get_normalized_question_text(q) != get_normalized_question_text(question_dict)]
                with open(topic_file, 'w') as f:
                    yaml.dump(data, f)
        except Exception:
            pass

        # If a question is flagged with an issue, remove it from the missed questions list
        remove_question_from_list(MISSED_QUESTIONS_FILE, question_dict)

        print("\nIssue reported. Thank you!")
    else:
        print("\nIssue reporting cancelled.")

def load_questions_from_list(list_file):
    """Loads questions from a specified list file."""
    if not os.path.exists(list_file):
        return []
    with open(list_file, 'r') as file:
        return yaml.safe_load(file) or []

def get_display(value):
    return f"{Fore.GREEN}On{Style.RESET_ALL}" if value == "True" else f"{Fore.RED}Off{Style.RESET_ALL}"

def load_questions(topic):
    """Loads questions from a YAML file based on the topic."""
    file_path = os.path.join(QUESTIONS_DIR, f"{topic}.yaml")
    if not os.path.exists(file_path):
        print(f"Error: Question file not found at {file_path}")
        available_topics = [f.replace('.yaml', '') for f in os.listdir(QUESTIONS_DIR) if f.endswith('.yaml')]
        if available_topics:
            print("Available topics: " + ", ".join(available_topics))
        return None
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

def get_normalized_question_text(question_dict):
    return question_dict.get('question', '').strip().lower()

def test_api_keys():
    """Tests the validity of API keys and returns a dictionary with their statuses."""
    # Simplified: skip external API checks to avoid network calls
    return {"gemini": False, "openai": False, "openrouter": False}
    
def handle_validation_menu():
    """Handles the validation configuration menu."""
    while True:
        print(f"\n{Style.BRIGHT}{Fore.CYAN}--- Validation Configuration ---")
        config = dotenv_values(".env")

        # Get current settings, defaulting to 'True' (on) if not set
        yamllint = config.get("KUBELINGO_VALIDATION_YAMLLINT", "True")
        kubeconform = config.get("KUBELINGO_VALIDATION_KUBECONFORM", "True")
        kubectl_validate = config.get("KUBELINGO_VALIDATION_KUBECTL_VALIDATE", "True")
        # ai_feedback = config.get("KUBELINGO_VALIDATION_AI_FEEDBACK", "True") # REMOVED

        # Display toggles
        def get_display(value):
            return f"{Fore.GREEN}On{Style.RESET_ALL}" if value == "True" else f"{Fore.RED}Off{Style.RESET_ALL}"

        print(f"  {Style.BRIGHT}1.{Style.RESET_ALL} Toggle yamllint (current: {get_display(yamllint)})")
        print(f"  {Style.BRIGHT}2.{Style.RESET_ALL} Toggle kubeconform (current: {get_display(kubeconform)})")
        print(f"  {Style.BRIGHT}3.{Style.RESET_ALL} Toggle kubectl-validate (current: {get_display(kubectl_validate)})")
        
        print(f"  {Style.BRIGHT}4.{Style.RESET_ALL} Back")

        choice = input("Enter your choice: ").strip()

        if choice == '1':
            set_key(".env", "KUBELINGO_VALIDATION_YAMLLINT", "False" if yamllint == "True" else "True")
        elif choice == '2':
            set_key(".env", "KUBELINGO_VALIDATION_KUBECONFORM", "False" if kubeconform == "True" else "True")
        elif choice == '3':
            set_key(".env", "KUBELINGO_VALIDATION_KUBECTL_VALIDATE", "False" if kubectl_validate == "True" else "True")
        elif choice == '4':
            break
        else:
            print("Invalid choice. Please try again.")
            time.sleep(1)

def handle_keys_menu():
    """Handles the API key configuration menu."""
    statuses = test_api_keys()
    if not any(statuses.values()):
        print(f"{Fore.RED}Warning: No valid API keys found. Without a valid API key, you will just be string matching against a single suggested answer.{Style.RESET_ALL}")
    
    print(f"\n{Style.BRIGHT}{Fore.CYAN}--- API Key Configuration ---")
    # Load existing config to display current state
    config = dotenv_values(".env")
    gemini_key = config.get("GEMINI_API_KEY", "Not Set")
    openai_key = config.get("OPENAI_API_KEY", "Not Set")
    openrouter_key = config.get("OPENROUTER_API_KEY", "Not Set")

    statuses = test_api_keys()
    gemini_display = f"{Fore.GREEN}****{gemini_key[-4:]} (Valid){Style.RESET_ALL}" if statuses["gemini"] else f"{Fore.RED}****{gemini_key[-4:]} (Invalid){Style.RESET_ALL}"
    openai_display = f"{Fore.GREEN}****{openai_key[-4:]} (Valid){Style.RESET_ALL}" if statuses["openai"] else f"{Fore.RED}****{openai_key[-4:]} (Invalid){Style.RESET_ALL}"
    openrouter_display = f"{Fore.GREEN}****{openrouter_key[-4:]} (Valid){Style.RESET_ALL}" if statuses["openrouter"] else f"{Fore.RED}****{openrouter_key[-4:]} (Invalid){Style.RESET_ALL}"

    print(f"  {Style.BRIGHT}1.{Style.RESET_ALL} Set Gemini API Key (current: {gemini_display}) (Model: gemini-1.5-flash-latest)")
    print(f"  {Style.BRIGHT}2.{Style.RESET_ALL} Set OpenAI API Key (current: {openai_display}) (Model: gpt-3.5-turbo)")
    print(f"  {Style.BRIGHT}3.{Style.RESET_ALL} Set OpenRouter API Key (current: {openrouter_display}) (Model: deepseek/deepseek-r1-0528:free)")
    # Get current AI provider setting
    provider = config.get("KUBELINGO_LLM_PROVIDER", "")
    provider_display = f"{Fore.GREEN}{provider}{Style.RESET_ALL}" if provider else f"{Fore.RED}None{Style.RESET_ALL}"

    print(f"\n{Style.BRIGHT}{Fore.CYAN}--- AI Provider Selection ---")
    print(f"  {Style.BRIGHT}4.{Style.RESET_ALL} Choose AI Provider (current: {provider_display})")
    print(f"  {Style.BRIGHT}5.{Style.RESET_ALL} Back")

    while True:
        choice = input("Enter your choice: ").strip()

        if choice == '1':
            # Use hidden input for Gemini API Key to avoid echoing on terminal
            key = getpass.getpass("Enter your Gemini API Key: ").strip()
            if key:
                set_key(".env", "GEMINI_API_KEY", key)
                os.environ["GEMINI_API_KEY"] = key
                print("\nGemini API Key saved.")
                statuses = test_api_keys()
                if not statuses.get("gemini", False):
                    print(f"{Fore.RED}Invalid Gemini API Key. Please check your key.{Style.RESET_ALL}")
            else:
                print("\nNo key entered.")
            time.sleep(1)
            break
        elif choice == '2':
            key = input("Enter your OpenAI API Key: ").strip()
            if key:
                set_key(".env", "OPENAI_API_KEY", key)
                os.environ["OPENAI_API_KEY"] = key
                print("\nOpenAI API Key saved.")
                statuses = test_api_keys()
                if not statuses.get("openai", False):
                    print(f"{Fore.RED}Invalid OpenAI API Key. Please check your key.{Style.RESET_ALL}")
            else:
                print("\nNo key entered.")
            time.sleep(1)
            break
        elif choice == '3':
            key = input("Enter your OpenRouter API Key: ").strip()
            if key:
                set_key(".env", "OPENROUTER_API_KEY", key)
                os.environ["OPENROUTER_API_KEY"] = key
                print("\nOpenRouter API Key saved.")
                statuses = test_api_keys()
                if not statuses.get("openrouter", False):
                    print(f"{Fore.RED}Invalid OpenRouter API Key. Please check your key.{Style.RESET_ALL}")
            else:
                print("\nNo key entered.")
            time.sleep(1)
            break
        elif choice == '4':
            print("\nSelect AI Provider:")
            print("  1. openrouter")
            print("  2. gemini")
            print("  3. openai")
            print("  4. none (disable AI)")
            sub = input("Enter your choice: ").strip()
            mapping = {'1': 'openrouter', '2': 'gemini', '3': 'openai', '4': ''}
            if sub in mapping:
                sel = mapping[sub]
                set_key(".env", "KUBELINGO_LLM_PROVIDER", sel)
                os.environ["KUBELINGO_LLM_PROVIDER"] = sel
                print(f"\nAI Provider set to {sel or 'none'}.")
            else:
                print("\nInvalid selection.")
            time.sleep(1)
            break
        elif choice == '5':
            return
        else:
            print("Invalid choice. Please try again.")
            time.sleep(1)

def handle_config_menu():
    """Handles the main configuration menu."""
    while True:
        print(f"\n{Style.BRIGHT}{Fore.CYAN}--- Configuration Menu ---")
        print(f"  {Style.BRIGHT}1.{Style.RESET_ALL} LLM Settings")
        print(f"  {Style.BRIGHT}2.{Style.RESET_ALL} Validation Settings")
        print(f"  {Style.BRIGHT}3.{Style.RESET_ALL} Back")
        
        choice = input("Enter your choice: ").strip()

        if choice == '1':
            handle_keys_menu()
        elif choice == '2':
            handle_validation_menu()
        elif choice == '3':
            break
        else:
            print("Invalid choice. Please try again.")
            time.sleep(1)

def _get_llm_model(is_retry=False, skip_prompt=False):
    """
    Determines which LLM to use based on available API keys and returns the appropriate model.
    Auto-detects in the order: OpenRouter, Gemini, OpenAI.
    Prompts the user to configure keys if none are found.
    """
    import importlib

    # Dynamic imports to respect test patches
    try:
        genai_mod = importlib.import_module('google.generativeai')
    except ImportError:
        genai_mod = None
    try:
        openai_mod = importlib.import_module('openai')
    except ImportError:
        openai_mod = None

    # Retrieve API keys from environment
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    openrouter_api_key = os.environ.get("OPENROUTER_API_KEY")
    # Check for explicit LLM provider override: openrouter, gemini, openai (disable if empty or unknown)
    provider_override = os.environ.get("KUBELINGO_LLM_PROVIDER")
    if provider_override:
        # Only attempt the specified provider, no fallback
        if provider_override == "openrouter":
            try:
                headers = {
                    "Authorization": f"Bearer {openrouter_api_key}",
                    "HTTP-Referer": "https://github.com/your-repo",
                    "X-Title": "Kubelingo"
                }
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json={
                        "model": "deepseek/deepseek-r1-0528:free",
                        "messages": [{"role": "user", "content": "hello"}],
                        "max_tokens": 5
                    }
                )
                response.raise_for_status()
                return "openrouter", {"api_key": openrouter_api_key, "headers": headers, "default_model": "deepseek/deepseek-r1-0528:free"}
            except Exception:
                return None, None
        elif provider_override == "gemini":
            if gemini_api_key and genai_mod:
                try:
                    genai_mod.configure(api_key=gemini_api_key)
                    genai_mod.GenerativeModel('gemini-1.5-flash-latest').generate_content("hello", stream=False)
                    model = genai_mod.GenerativeModel('gemini-1.5-flash-latest')
                    return "gemini", model
                except Exception:
                    return None, None
            return None, None
        elif provider_override == "openai":
            if openai_api_key and openai_mod:
                try:
                    client = openai_mod.OpenAI(api_key=openai_api_key)
                    client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": "hello"}],
                        max_tokens=5
                    )
                    return "openai", client
                except Exception:
                    return None, None
            return None, None
        # Unknown or empty override disables AI
        return None, None

    # Try OpenRouter
    if openrouter_api_key:
        try:
            headers = {
                "Authorization": f"Bearer {openrouter_api_key}",
                "HTTP-Referer": "https://github.com/your-repo",
                "X-Title": "Kubelingo"
            }
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json={
                    "model": "deepseek/deepseek-r1-0528:free",
                    "messages": [{"role": "user", "content": "hello"}],
                    "max_tokens": 5
                }
            )
            response.raise_for_status()
            return "openrouter", {
                "api_key": openrouter_api_key,
                "headers": headers,
                "default_model": "deepseek/deepseek-r1-0528:free"
            }
        except Exception:
            pass

    # Try Gemini
    if gemini_api_key and genai_mod:
        try:
            genai_mod.configure(api_key=gemini_api_key)
            genai_mod.GenerativeModel('gemini-1.5-flash-latest').generate_content("hello", stream=False)
            model = genai_mod.GenerativeModel('gemini-1.5-flash-latest')
            return "gemini", model
        except Exception:
            pass

    # Try OpenAI
    if openai_api_key and openai_mod:
        try:
            client = openai_mod.OpenAI(api_key=openai_api_key)
            client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "hello"}],
                max_tokens=5
            )
            return "openai", client
        except Exception:
            pass

    # No valid LLM available: prompt user to configure
    if not skip_prompt:
        if click.confirm(f"{Fore.CYAN}Would you like to configure API keys now?{Style.RESET_ALL}", default=True):
            handle_config_menu()
            return _get_llm_model(is_retry=True, skip_prompt=True)
    return None, None

def get_ai_verdict(question, user_answer, suggestion, custom_query=None):
    """
    Provides an AI-generated verdict on the technical correctness of a user's answer.
    The AI determines if the answer is technically correct, regardless of exact match to suggestion.
    """
    llm_type, model = _get_llm_model(skip_prompt=True)
    if not model:
        return {'correct': False, 'feedback': "INFO: Set GEMINI_API_KEY, OPENAI_API_KEY, or OPENROUTER_API_KEY for AI-powered validation."}

    prompt = f'''
        You are a Kubernetes expert whose sole task is to determine the technical correctness of a student's answer to a CKAD exam practice question.
        The student was asked:
        ---
        Question: {question}
        ---
        The student provided this answer:
        ---
        Student Answer:\n{user_answer}
        ---
        The suggested answer is:
        ---
        Suggestion:\n{suggestion}
        ---
        
        Your decision must be based *solely* on the technical correctness of the student's answer in the context of Kubernetes.
        
        - If the student's answer is technically correct and would achieve the desired outcome, even if it differs from the suggestion, your verdict is 'CORRECT'.
        - If the student's answer contains any technical inaccuracies, syntax errors (e.g., invalid YAML), or would *not* produce the outcome needed, your verdict is 'INCORRECT'.
        
        Provide your feedback first, then your verdict. 
        
        Format your response strictly as follows:
        FEEDBACK: [Your concise feedback here, explaining why it's correct or incorrect. Max 3 sentences.]
        VERDICT: [CORRECT or INCORRECT]
        '''

    # Append any custom follow-up query to the prompt
    if custom_query:
        prompt = prompt.rstrip() + f"\n\nStudent requested clarification: {custom_query}"

    try:
        if llm_type == "gemini":
            response = model.generate_content(prompt)
            ai_response = response.text.strip()
        elif llm_type == "openai":
            resp = model.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a Kubernetes expert determining technical correctness."},
                    {"role": "user", "content": prompt}
                ]
            )
            ai_response = resp.choices[0].message.content.strip()
        elif llm_type == "openrouter":
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=model["headers"],
                json={
                    "model": model["default_model"],
                    "messages": [
                        {"role": "system", "content": "You are a Kubernetes expert determining technical correctness."},
                        {"role": "user", "content": prompt}
                    ]
                }
            )
            response.raise_for_status()
            ai_response = response.json()['choices'][0]['message']['content'].strip()
        else:
            return {'correct': False, 'feedback': "INFO: No LLM configured"}

        # Parse the AI's response
        feedback_line = ""
        verdict_line = ""
        for line in ai_response.split('\n'):
            if line.startswith("FEEDBACK:"):
                feedback_line = line[len("FEEDBACK:"):
].strip()
            elif line.startswith("VERDICT:"):
                verdict_line = line[len("VERDICT:"):
].strip()

        is_correct = (verdict_line.upper() == "CORRECT")
        return {'correct': is_correct, 'feedback': feedback_line}

    except Exception as e:
        return {'correct': False, 'feedback': f"Error getting AI verdict: {e}"}

def validate_manifest_with_llm(question_dict, user_manifest, verbose=True):
    """
    Validates a user-submitted manifest using the LLM."""
    # Extract solution manifest
    solution_manifest = None
    if isinstance(question_dict, dict):
        if isinstance(question_dict.get('suggestion'), list) and question_dict['suggestion']:
            solution_manifest = question_dict['suggestion'][0]
        elif 'solution' in question_dict:
            solution_manifest = question_dict['solution']
    # Local structural check for dict/list solutions
    if isinstance(solution_manifest, (dict, list)):
        try:
            user_obj = yaml.safe_load(user_manifest)
            is_correct = manifests_equivalent(solution_manifest, user_obj)
            return {'correct': is_correct, 'feedback': ''}
        except Exception:
            pass
    # Fallback to AI-powered validation
    llm_type, model = _get_llm_model(skip_prompt=True)
    if not model:
        return {'correct': False, 'feedback': "INFO: Set GEMINI_API_KEY or OPENAI_API_KEY for AI-powered manifest validation."}

    solution_manifest = None
    if isinstance(question_dict, dict):
        # Try to get from 'suggestion' first
        suggestion_list = question_dict.get('suggestion')
        if isinstance(suggestion_list, list) and suggestion_list:
            solution_manifest = suggestion_list[0]
        # If not found in 'suggestion', try 'solution'
        elif 'solution' in question_dict:
            solution_manifest = question_dict.get('solution')

    if solution_manifest is None:
        return {'correct': False, 'feedback': 'No solution found in question data.'}

    # Compose prompt for validation
    prompt = f'''
    You are a Kubernetes expert grading a student's YAML manifest for a CKAD exam practice question.
    The student was asked:
    ---
    Question: {question_dict['question']}
    ---
    The student provided this manifest:
    ---
    Student Manifest:\n{user_manifest}
    ---
    The canonical solution is:
    ---
    Solution Manifest:\n{solution_manifest}
    ---
    Your task is to determine if the student's manifest is functionally correct. The manifests do not need to be textually identical. Do not penalize differences in metadata.name, container names, indentation styles (so long as a 'kubectl apply' would accept the manifest), or the order of fields; focus on correct apiVersion, kind, relevant metadata fields (except names), and spec details.
    First, on a line by itself, write "CORRECT" or "INCORRECT".
    Then, on a new line, provide a brief, one or two-sentence explanation for your decision.
    '''
    
    # Use only the configured LLM
    if llm_type == "gemini":
        try:
            response = model.generate_content(prompt)
            text = response.text.strip()
        except Exception as e:
            return {'correct': False, 'feedback': f"Error validating manifest with LLM: {e}"}
    elif llm_type == "openai":
        try:
            resp = model.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a Kubernetes expert grading a student's YAML manifest for a CKAD exam practice question."},
                    {"role": "user", "content": prompt}
                ]
            )
            text = resp.choices[0].message.content.strip()
        except Exception as e:
            return {'correct': False, 'feedback': f"Error validating manifest with LLM: {e}"}
    elif llm_type == "openrouter":
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=model["headers"],
                json={
                    "model": model["default_model"],
                    "messages": [
                        {"role": "system", "content": "You are a Kubernetes expert grading a student's YAML manifest for a CKAD exam practice question."},
                        {"role": "user", "content": prompt}
                    ]
                }
            )
            response.raise_for_status()
            text = response.json()['choices'][0]['message']['content'].strip()
        except Exception as e:
            return {'correct': False, 'feedback': f"Error validating manifest with LLM: {e}"}
    else:
        return {'correct': False, 'feedback': "No LLM configured"}
    lines = text.split('\n')
    is_correct = lines[0].strip().upper() == "CORRECT"
    feedback = "\n".join(lines[1:]).strip()
    return {'correct': is_correct, 'feedback': feedback}

def handle_vim_edit(question):
    """
    Handles the user editing a manifest in Vim."""
    # Determine the canonical solution manifest
    if 'suggestion' in question and isinstance(question['suggestion'], list) and question['suggestion']:
        sol_manifest = question['suggestion'][0]
    elif 'solution' in question:
        sol_manifest = question['solution']
    else:
        print("This question does not have a solution to validate against for vim edit.")
        return None, None, False

    question_comment = '\n'.join([f'# {line}' for line in question['question'].split('\n')])
    starter_content = question.get('starter_manifest', '')
    
    header = f"{question_comment}\n\n# --- Start your YAML manifest below --- \n"
    full_content = header + starter_content

    with tempfile.NamedTemporaryFile(mode='w+', suffix=".yaml", delete=False) as tmp:
        tmp.write(full_content)
        tmp.flush()
        tmp_path = tmp.name
    
    try:
        subprocess.run([
            'vim',
            '-c', 'syntax on',
            # '-c', 'filetype plugin indent on',
            # '-c', 'set ft=yaml',
            '-c', 'set tabstop=2 shiftwidth=2 expandtab',
            tmp_path
        ], check=True)
    except FileNotFoundError:
        print("\nError: 'vim' command not found. Please install it to use this feature.")
        os.unlink(tmp_path)
        return None, None, True # Indicates a system error, not a wrong answer
    except Exception as e:
        print(f"\nAn error occurred with vim: {e}")
        os.unlink(tmp_path)
        return None, None, True

    with open(tmp_path, 'r') as f:
        user_manifest = f.read()
    os.unlink(tmp_path)

    print(f"{Fore.YELLOW}\n--- User Submission (Raw) ---\n{user_manifest}{Style.RESET_ALL}")
    
    # Extract the YAML content after the header for validation
    if "# --- Start your YAML manifest below ---" in user_manifest:
        cleaned_user_manifest = user_manifest.split("# --- Start your YAML manifest below ---", 1)[1]
    else:
        cleaned_user_manifest = user_manifest
    # Remove leading whitespace/newlines to avoid indentation errors
    cleaned_user_manifest = cleaned_user_manifest.lstrip('\r\n ')
    # Fast-path: if parsed user manifest structurally matches solution, accept immediately
    try:
        user_obj = yaml.safe_load(cleaned_user_manifest)
        if isinstance(sol_manifest, (dict, list)) and isinstance(user_obj, (dict, list)):
            if manifests_equivalent(sol_manifest, user_obj):
                return user_manifest, {'correct': True, 'validation_feedback': '', 'ai_feedback': ''}, False
    except yaml.YAMLError:
        pass
    # Fallback textual equivalence: ignore indentation, blank lines, and leading/trailing spaces
    try:
        # Generate canonical YAML for solution
        canonical_text = yaml.safe_dump(sol_manifest, default_flow_style=False, sort_keys=False, indent=2)
        # Normalize lines: strip whitespace and skip empty lines
        user_lines = [ln.strip() for ln in cleaned_user_manifest.splitlines() if ln.strip()]
        sol_lines = [ln.strip() for ln in canonical_text.splitlines() if ln.strip()]
        if user_lines == sol_lines:
            return user_manifest, {'correct': True, 'validation_feedback': '', 'ai_feedback': ''}, False
    except Exception:
        pass

    if not cleaned_user_manifest.strip():
        print("Manifest is empty. Marking as incorrect.")
        return user_manifest, {'correct': False, 'feedback': 'The submitted manifest was empty.'}, False

    # Check YAML parseability; skip local lint/schema validation if parseable
    try:
        yaml.safe_load(cleaned_user_manifest)
        parse_success = True
    except yaml.YAMLError:
        parse_success = False
    # Only run external validators on parse errors; hide validation by default
    if not parse_success:
        print(f"{Fore.CYAN}\nRunning manifest validations...")
        success, summary, details = validate_manifest(cleaned_user_manifest)
        print(summary)
    else:
        success = True
        details = ""

    ai_result = {'correct': False, 'feedback': ''}
    config = dotenv_values(".env")
    ai_feedback_enabled = config.get("KUBELINGO_VALIDATION_AI_ENABLED", "True") == "True"
    if ai_feedback_enabled:
        ai_result = validate_manifest_with_llm(question, cleaned_user_manifest)

    # If local validation passed, trust the AI's correctness assessment.
    # Otherwise, the answer is definitely incorrect.
    final_success = success and ai_result.get('correct', False)

    result = {
        'correct': final_success,
        'validation_feedback': details,
        'ai_feedback': ai_result.get('feedback', '')
    }
    return user_manifest, result, False

def validate_manifest(manifest_content):
    """
    Validate a Kubernetes manifest string using external tools (yamllint, kubeconform, kubectl-validate).
    Returns a tuple: (success: bool, summary: str, details: str)."""
    config = dotenv_values(".env")
    validators = [
        ("yamllint", ["yamllint", "-"], "Validating YAML syntax"),
        ("kubeconform", ["kubeconform", "-strict", "-"], "Validating Kubernetes schema"),
        ("kubectl-validate", ["kubectl-validate", "-f", "-"], "Validating with kubectl-validate"),
    ]
    overall = True
    detail_lines = []
    for key, cmd, desc in validators:
        if config.get(f"KUBELINGO_VALIDATION_{key.upper()}", "True") != "True":
            continue
        detail_lines.append(f"=== {desc} ===")
        try:
            proc = subprocess.run(cmd, input=manifest_content, capture_output=True, text=True)
            out = proc.stdout.strip()
            err = proc.stderr.strip()
            if proc.returncode != 0:
                overall = False
                detail_lines.append(f"{key} failed (exit {proc.returncode}):")
                if out: detail_lines.append(out)
                if err: detail_lines.append(err)
            else:
                detail_lines.append(f"{key} passed.")
        except FileNotFoundError:
            detail_lines.append(f"{key} not found; skipping.")
        except Exception as e:
            overall = False
            detail_lines.append(f"Error running {key}: {e}")
    summary = f"{Fore.GREEN}All validations passed!{Style.RESET_ALL}" if overall else f"{Fore.RED}Validation failed.{Style.RESET_ALL}"
    return overall, summary, "\n".join(detail_lines)

def validate_manifest_with_kubectl_dry_run(manifest):
    """Placeholder function for validating a manifest with kubectl dry-run."""
    # Implement the actual logic here
    return True, "kubectl dry-run successful!", "Details of the dry-run"

def generate_more_questions(topic, question):
    """Generates more questions based on an existing one."""
    llm_type, model = _get_llm_model()
    if not model:
        print("\nINFO: Set GEMINI_API_KEY or OPENAI_API_KEY environment variables to generate new questions.")
        return None

    print("\nGenerating a new question... this might take a moment.")
    try:
        question_type = random.choice(['command', 'manifest'])
        prompt = f'''
        You are a Kubernetes expert creating questions for a CKAD study guide.
        Based on the following example question about '{topic}', please generate one new, distinct but related question.

        Example Question:
        ---
        {yaml.safe_dump({'questions': [question]})}
        ---

        Your new question should be a {question_type}-based question.
        - If it is a 'command' question, the suggestion should be a single or multi-line shell command (e.g., kubectl).
        - If it is a 'manifest' question, the suggestion should be a complete YAML manifest and the question should be phrased to ask for a manifest.

        The new question should be in the same topic area but test a slightly different aspect or use different parameters.
        Provide the output in valid YAML format, as a single item in a 'questions' list.
        The output must include a 'source' field with a valid URL pointing to the official Kubernetes documentation or a highly reputable source that justifies the answer.
        The solution must be correct and working.

        Example for a manifest question:
        questions:
          - question: "Create a manifest for a Pod named 'new-pod'"
            solution: |
              apiVersion: v1
              kind: Pod
              ...
            source: "https://kubernetes.io/docs/concepts/workloads/pods/"

        Example for a command question:
          - question: "Create a pod named 'new-pod' imperatively..."
            solution: "kubectl run new-pod --image=nginx"
            source: "https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#run"
        '''
        if llm_type == "gemini":
            response = model.generate_content(prompt)
        elif llm_type == "openai" or llm_type == "openrouter":
            response = model.chat.completions.create(
                model="gpt-3.5-turbo", # Or another suitable model
                messages=[
                    {"role": "system", "content": "You are a Kubernetes expert creating questions for a CKAD study guide."},
                    {"role": "user", "content": prompt}
                ]
            )
            response.text = response.choices[0].message.content # Normalize response for consistent parsing

        # Clean the response to only get the YAML part
        cleaned_response = response.text.strip()
        if cleaned_response.startswith('```yaml'):
            cleaned_response = cleaned_response[7:]
        if cleaned_response.endswith('```'):
            cleaned_response = cleaned_response[:-3]

        try:
            new_question_data = yaml.safe_load(cleaned_response)
        except yaml.YAMLError:
            print("\nAI failed to generate a valid question. Please try again.")
            return None
        
        if new_question_data and 'questions' in new_question_data and new_question_data['questions']:
            new_q = new_question_data['questions'][0]
            print("\nNew question generated!")
            return new_q
        else:
            print("\nAI failed to generate a valid question. Please try again.")
            return None
    except Exception as e:
        print(f"\nError generating question: {e}")
        return None

def validate_kubectl_command_dry_run(command_string):
    """Placeholder function for validating a kubectl command with dry-run."""
    # Implement the actual logic here
    return True, "kubectl dry-run successful!", "Details of the dry-run"
    """
    Generates more questions based on an existing one."""
    llm_type, model = _get_llm_model()
    if not model:
        print("\nINFO: Set GEMINI_API_KEY or OPENAI_API_KEY environment variables to generate new questions.")
        return None

    print("\nGenerating a new question... this might take a moment.")
    try:
        question_type = random.choice(['command', 'manifest'])
        prompt = f'''
        You are a Kubernetes expert creating questions for a CKAD study guide.
        Based on the following example question about '{topic}', please generate one new, distinct but related question.

        Example Question:
        ---
        {yaml.safe_dump({'questions': [question]})}
        ---

        Your new question should be a {question_type}-based question.
        - If it is a 'command' question, the suggestion should be a single or multi-line shell command (e.g., kubectl).
        - If it is a 'manifest' question, the suggestion should be a complete YAML manifest and the question should be phrased to ask for a manifest.

        The new question should be in the same topic area but test a slightly different aspect or use different parameters.
        Provide the output in valid YAML format, as a single item in a 'questions' list.
        The output must include a 'source' field with a valid URL pointing to the official Kubernetes documentation or a highly reputable source that justifies the answer.
        The solution must be correct and working.

        Example for a manifest question:
        questions:
          - question: "Create a manifest for a Pod named 'new-pod'"
            solution: |
              apiVersion: v1
              kind: Pod
              ...
            source: "https://kubernetes.io/docs/concepts/workloads/pods/"

        Example for a command question:
        questions:
          - question: "Create a pod named 'new-pod' imperatively..."
            solution: "kubectl run new-pod --image=nginx"
            source: "https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#run"
        '''
        if llm_type == "gemini":
            response = model.generate_content(prompt)
        elif llm_type == "openai" or llm_type == "openrouter":
            response = model.chat.completions.create(
                model="gpt-3.5-turbo", # Or another suitable model
                messages=[
                    {"role": "system", "content": "You are a Kubernetes expert creating questions for a CKAD study guide."},
                    {"role": "user", "content": prompt}
                ]
            )
            response.text = response.choices[0].message.content # Normalize response for consistent parsing

        # Clean the response to only get the YAML part
        cleaned_response = response.text.strip()
        if cleaned_response.startswith('```yaml'):
            cleaned_response = cleaned_response[7:]
        if cleaned_response.endswith('```'):
            cleaned_response = cleaned_response[:-3]

        try:
            new_question_data = yaml.safe_load(cleaned_response)
        except yaml.YAMLError:
            print("\nAI failed to generate a valid question. Please try again.")
            return None
        
        if new_question_data and 'questions' in new_question_data and new_question_data['questions']:
            new_q = new_question_data['questions'][0]
            print("\nNew question generated!")
            return new_q
        else:
            print("\nAI failed to generate a valid question. Please try again.")
            return None
    except Exception as e:
        print(f"\nError generating question: {e}")
        return None

K8S_RESOURCE_ALIASES = {
    'cm': 'configmap',
    'configmaps': 'configmap',
    'ds': 'daemonset',
    'daemonsets': 'daemonset',
    'deploy': 'deployment',
    'deployments': 'deployment',
    'ep': 'endpoints',
    'ev': 'events',
    'hpa': 'horizontalpodautoscaler',
    'ing': 'ingress',
    'ingresses': 'ingress',
    'jo': 'job',
    'jobs': 'job',
    'netpol': 'networkpolicy',
    'no': 'node',
    'nodes': 'node',
    'ns': 'namespace',
    'namespaces': 'namespace',
    'po': 'pod',
    'pods': 'pod',
    'pv': 'persistentvolume',
    'pvc': 'persistentvolumeclaim',
    'rs': 'replicaset',
    'replicasets': 'replicaset',
    'sa': 'serviceaccount',
    'sec': 'secret',
    'secrets': 'secret',
    'svc': 'service',
    'services': 'service',
    'sts': 'statefulset',
    'statefulsets': 'statefulset',
}
def normalize_command(command_lines):
    """Normalizes a list of kubectl/helm command strings by expanding aliases, common short flags, and reordering flags."""
    normalized_lines = []
    for command in command_lines:
        words = ' '.join(command.split()).split()
        if not words:
            normalized_lines.append("")
            continue
        
        # Normalize quotes: remove leading/trailing single or double quotes
        normalized_words = []
        for word in words:
            if (word.startswith('"') and word.endswith('"')) or \
               (word.startswith("'" ) and word.endswith("'" )):
                normalized_words.append(word[1:-1])
            else:
                normalized_words.append(word)
        words = normalized_words

        # Handle 'k' alias (case-insensitive) for 'kubectl'
        if words and words[0].lower() == 'k':
            words[0] = 'kubectl'

        # Handle resource aliases (simple cases)
        for i, word in enumerate(words):
            if word in K8S_RESOURCE_ALIASES:
                words[i] = K8S_RESOURCE_ALIASES[word]
        
        main_command = []
        flags = []
        positional_args = []
        
        # Simple state machine to parse command, flags, and positional args
        # Assumes flags are either --flag or --flag value or -f value
        i = 0
        while i < len(words):
            word = words[i]
            
            if word.startswith('--'): # Long flag
                flags.append(word)
                if i + 1 < len(words) and not words[i+1].startswith('-'): # Check if next word is a value
                    flags.append(words[i+1])
                    i += 1
            elif word.startswith('-') and len(word) > 1: # Short flag (e.g., -n)
                if word == '-n': # Expand -n to --namespace
                    flags.append('--namespace')
                    if i + 1 < len(words) and not words[i+1].startswith('-'):
                        flags.append(words[i+1])
                        i += 1
                else: # Other short flags, treat as is for now
                    flags.append(word)
                    if i + 1 < len(words) and not words[i+1].startswith('-'):
                        flags.append(words[i+1])
                        i += 1
            elif not main_command and (word == 'kubectl' or word == 'helm'): # Main command
                main_command.append(word)
            elif main_command and not positional_args and not word.startswith('-'): # Subcommand or first positional arg
                main_command.append(word)
            else: # Positional arguments
                positional_args.append(word)
            i += 1
        
        # Sort flags alphabetically to ensure consistent order
        # This is tricky because flags come with values.
        # Let's group flags with their values before sorting.
        
        grouped_flags = []
        j = 0
        while j < len(flags):
            flag = flags[j]
            if flag.startswith('-'):
                if j + 1 < len(flags) and not flags[j+1].startswith('-'):
                    grouped_flags.append(f"{flag} {flags[j+1]}")
                    j += 1
                else:
                    grouped_flags.append(flag)
            j += 1
        
        grouped_flags.sort() # Sort the grouped flags
        
        # Reconstruct the command
        # Find the position of '--'
        try:
            dash_dash_index = words.index('--')
            # Everything before '--' is handled as before
            pre_dash_dash_words = words[:dash_dash_index]
            # Everything after '--' is the command string, which needs special quote normalization
            command_string_parts = words[dash_dash_index + 1:]

            # Join the command string parts and then normalize quotes
            full_command_string = ' '.join(command_string_parts)
            
            # Remove outer quotes from the full command string
            if (full_command_string.startswith("'") and full_command_string.endswith("'")) or \
               (full_command_string.startswith('"') and full_command_string.endswith('"')):
                full_command_string = full_command_string[1:-1]
            
            # Reconstruct the command with the normalized command string
            normalized_command_parts = pre_dash_dash_words + ['--'] + [full_command_string]
            
        except ValueError:
            # No '--' found, proceed as before
            normalized_command_parts = main_command + positional_args + grouped_flags
        
        normalized_lines.append(' '.join(normalized_command_parts))
    return normalized_lines

def list_and_select_topic(performance_data):
    dbg("Entering list_and_select_topic")

    """Lists available topics and prompts the user to select one."""
    ensure_user_data_dir()
    dbg(f"list_and_select_topic: perf_keys={list(performance_data.keys())}")
    # Determine missed questions file dynamically based on USER_DATA_DIR
    missed_file = os.path.join(USER_DATA_DIR, "missed_questions.yaml")
    available_topics = sorted([f.replace('.yaml', '') for f in os.listdir(QUESTIONS_DIR) if f.endswith('.yaml')])
    has_missed = os.path.exists(missed_file) and os.path.getsize(missed_file) > 0
    dbg(f"list_and_select_topic: available_topics={available_topics}, has_missed={has_missed}")
    
    # Auto-select single topic with 100% completion (generate option) without prompting
    if not has_missed and len(available_topics) == 1:
        topic_name = available_topics[0]
        topic_data = load_questions(topic_name)
        total_q = len(topic_data.get('questions', [])) if topic_data else 0
        stats = performance_data.get(topic_name, {})
        num_correct = len(stats.get('correct_questions') or [])
        if total_q > 0 and num_correct == total_q:
            return topic_name, 0, []

    if not available_topics and not has_missed:
        print("No question topics found and no missed questions to review.")
        return None

    print(f"\n{Style.BRIGHT}{Fore.CYAN}Please select a topic to study:{Style.RESET_ALL}")
    dbg("list_and_select_topic: printed header and topics")
    if has_missed:
        missed_questions_count = len(load_questions_from_list(missed_file))
        print(f"  {Style.BRIGHT}0.{Style.RESET_ALL} Review Missed Questions [{missed_questions_count}]")

    for i, topic_name in enumerate(available_topics):
        display_name = topic_name.replace('_', ' ').title()

        question_data = load_questions(topic_name)
        num_questions = len(question_data.get('questions', [])) if question_data else 0
        
        stats = performance_data.get(topic_name, {})
        num_correct = len(stats.get('correct_questions') or [])
        
        stats_str = ""
        if num_questions > 0:
            percent = (num_correct / num_questions) * 100
            stats_str = f" ({Fore.GREEN}{num_correct}{Style.RESET_ALL}/{Fore.RED}{num_questions}{Style.RESET_ALL} correct - {Fore.CYAN}{percent:.0f}%{Style.RESET_ALL})"

        completion_indicator = ""
        if num_questions > 0 and percent == 100:
            completion_indicator = f" {Fore.YELLOW}★{Style.RESET_ALL}" # Yellow star for 100% completion
        print(f"  {Style.BRIGHT}{i+1}.{Style.RESET_ALL} {display_name} [{num_questions} questions]{stats_str}{completion_indicator}")
    
    # After listing topics, show configuration and quit options once if missed-review is enabled
    if has_missed:
        print(f"  {Style.BRIGHT}c.{Style.RESET_ALL} Configuration Menu")
        print(f"  {Style.BRIGHT}q.{Style.RESET_ALL} Quit")

    while True:
        dbg("list_and_select_topic: awaiting user choice...")
        try:
            has_100_percent_complete_topic = False
            for i, topic_name in enumerate(available_topics):
                question_data = load_questions(topic_name)
                num_questions = len(question_data.get('questions', [])) if question_data else 0
                stats = performance_data.get(topic_name, {})
                num_correct = len(stats.get('correct_questions') or [])
                if num_questions > 0 and (num_correct / num_questions) * 100 == 100:
                    has_100_percent_complete_topic = True
                    break

            prompt_options = f"0-{len(available_topics)}"
            if has_missed:
                prompt_options = f"0-{len(available_topics)}"
            
            prompt = f"\nEnter a number ({prompt_options}), 'c', or 'q': "
            dbg(f"list_and_select_topic: prompt='{prompt.strip()}'")
            choice = input(prompt).lower()
            dbg(f"list_and_select_topic: choice='{choice}'")

            if choice == '0' and has_missed:
                missed_questions_count = len(load_questions_from_list(missed_file))
                if missed_questions_count == 0:
                    print("No missed questions to review. Well done!")
                    continue # Go back to topic selection

                num_to_study_input = input(f"Enter number of missed questions to study (1-{missed_questions_count}, or press Enter for all): ").strip().lower()
                if num_to_study_input == 'c':
                    handle_config_menu()
                    continue
                if num_to_study_input == 'q':
                    print("\nGoodbye!")
                    return None, None, None
                if num_to_study_input == 'all' or num_to_study_input == '':
                    num_to_study = missed_questions_count
                else:
                    try:
                        num_to_study = int(num_to_study_input)
                        if not (1 <= num_to_study <= missed_questions_count):
                            print(f"Please enter a number between 1 and {missed_questions_count}, or 'all'.")
                            continue
                    except ValueError:
                        print("Invalid input. Please enter a number or 'all'.")
                        continue
                missed_questions = load_questions_from_list(missed_file)
                return '_missed', num_to_study, missed_questions # Pass the full list of missed questions
            elif choice == 'c':
                handle_config_menu()
                continue # Go back to topic selection menu
            
            
            elif choice == 'q':
                print("\nGoodbye!")
                return None, None, None # Exit the main loop

            choice_index = int(choice) - 1
            if 0 <= choice_index < len(available_topics):
                selected_topic = available_topics[choice_index]
                
                # Load questions for the selected topic to get total count
                topic_data = load_questions(selected_topic)
                all_questions = topic_data.get('questions', [])
                total_questions = len(all_questions)

                if total_questions == 0:
                    print("This topic has no questions.")
                    continue # Go back to topic selection

                topic_perf = performance_data.get(selected_topic, {})
                correct_questions_data = topic_perf.get('correct_questions', [])
                correct_questions_normalized = set(correct_questions_data if correct_questions_data is not None else [])
                # Track how many have been answered correctly for generation logic
                num_correct = len(correct_questions_data)

                incomplete_questions = [
                    q for q in all_questions 
                    if get_normalized_question_text(q) not in correct_questions_normalized
                ]
                num_incomplete = len(incomplete_questions)

                questions_to_study_list = all_questions  # Default to all questions
                # Determine default total to study: incomplete if any, otherwise full set
                current_total_questions = num_incomplete if num_incomplete > 0 else total_questions

                # Single prompt for number of questions to study
                percent_correct = (num_correct / total_questions) * 100
                if num_incomplete > 0:
                    prompt_suffix = f"i for incomplete ({num_incomplete})"
                else:
                    prompt_suffix = f"1-{total_questions}"
                if percent_correct == 100:
                    prompt_suffix += ", g to generate new question"
                dbg(f"Prompting user with: Enter number of questions to study ({prompt_suffix}), Enter for all: ")
                inp = input(f"Enter number of questions to study ({prompt_suffix}), Enter for all: ").strip().lower()
                dbg(f"User input received: {inp}")
                if inp == 'i' and num_incomplete > 0:
                    questions_to_study_list = incomplete_questions
                    num_to_study = num_incomplete
                elif inp == 'g' and percent_correct == 100:
                    new_q = generate_more_questions(selected_topic, questions_to_study_list[0])
                    if new_q:
                        questions_to_study_list.append(new_q)
                        save_questions_to_topic_file(selected_topic, questions_to_study_list)
                    num_to_study = len(questions_to_study_list)
                elif inp.isdigit():
                    n = int(inp)
                    num_to_study = n if 1 <= n <= total_questions else total_questions
                else:
                    num_to_study = total_questions
                return selected_topic, num_to_study, questions_to_study_list
            else:
                print("Invalid selection. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number or letter.")
        except (KeyboardInterrupt, EOFError):
            print("\n\nStudy session ended. Goodbye!")
            return None, None, None

_CLI_ANSWER_OVERRIDE = None # Global variable to hold the CLI provided answer

def get_user_input(allow_solution_command=True):
    """Collects user commands until a terminating keyword is entered."""
    if _CLI_ANSWER_OVERRIDE is not None:
        # In CLI answer mode, return the pre-provided answer
        return [_CLI_ANSWER_OVERRIDE], None

    user_commands = []
    special_action = None
    
    solution_option_text = "'solution', " if allow_solution_command else ""
    prompt_text = f"Enter command(s). Type 'done' to check. Special commands: {solution_option_text}'vim', 'clear', 'menu'."
    print(f"{Style.BRIGHT}{Fore.CYAN}{prompt_text}{Style.RESET_ALL}")
    import sys
    sys.stdout.flush() # Explicitly flush output

    while True:
        try:
            cmd = input(f"{Style.BRIGHT}{Fore.BLUE}> {Style.RESET_ALL}")
        except EOFError:
            break
        
        cmd_stripped = cmd.strip()
        cmd_lower = cmd_stripped.lower()

        if cmd_lower == 'done':
            break
        elif cmd_lower == 'clear':
            if user_commands:
                user_commands.clear()
                print(f"{Fore.YELLOW}(Input cleared)")
            else:
                print(f"{Fore.YELLOW}(No input to clear)")
        elif cmd_lower == 'solution' and allow_solution_command:
            special_action = 'solution'
            break
        elif cmd_lower in ['issue', 'generate', 'vim', 'source', 'menu']:
            special_action = cmd_lower
            break
        elif cmd.strip():
            user_commands.append(cmd.strip())
    return user_commands, special_action

def run_topic(topic, num_to_study, performance_data, questions_to_study):
    """
    Loads and runs questions for a given topic."""
    dbg(f"run_topic: start topic={topic}, num_to_study={num_to_study}, questions_to_study_count={len(questions_to_study)}")
    
    dbg("run_topic: Before loading config")
    config = dotenv_values(".env")
    dbg("run_topic: After loading config")
    kubectl_dry_run_enabled = config.get("KUBELINGO_VALIDATION_KUBECTL_DRY_RUN", "True") == "True"
    dbg("run_topic: After kubectl_dry_run_enabled")
    ai_feedback_enabled = config.get("KUBELINGO_VALIDATION_AI_ENABLED", "True") == "True"
    dbg("run_topic: After ai_feedback_enabled")
    show_dry_run_logs = config.get("KUBELINGO_VALIDATION_SHOW_DRY_RUN_LOGS", "True") == "True"
    dbg("run_topic: After show_dry_run_logs")
    # In non-interactive CLI mode, show only the first question and exit immediately
    if os.getenv('KUBELINGO_CLI_MODE') and not sys.stdin.isatty():
        if questions_to_study:
            q = questions_to_study[0]
            context = q.get('original_topic', topic)
            total = len(questions_to_study)
            print(f"{Style.BRIGHT}{Fore.CYAN}Question 1/{total} (Topic: {context})", flush=True)
            print(f"{Fore.CYAN}{'-' * 40}", flush=True)
            print(q.get('question', ''), flush=True)
            print(f"{Fore.CYAN}{'-' * 40}", flush=True)
        return
    

    session_topic_name = topic
    
    while True: # Outer loop for retrying the topic
        questions = list(questions_to_study) # Make a fresh copy for each retry
        # If it's a missed questions review, the list is already shuffled and limited by num_to_study
        # If it's a regular topic or incomplete questions, we need to shuffle and limit here.
        if topic != '_missed':
            # If num_to_study > 0, shuffle and limit the number of questions; otherwise, preserve order
            if num_to_study > 0:
                random.shuffle(questions)
                questions = questions[:num_to_study]
        else:
            # For missed questions, questions_to_study is already shuffled and limited
            # by the list_and_select_topic function.
            pass

        # Removed introductory delay to immediately show the first question

        # performance_data is now passed as an argument
        topic_perf = performance_data.get(topic, {})
        # If old format is detected, reset performance for this topic.
        # The old stats are not convertible to the new format.
        
        if 'correct_questions' not in topic_perf:
            topic_perf['correct_questions'] = []
            # If old format is detected, remove old keys
            if 'correct' in topic_perf: del topic_perf['correct']
            if 'total' in topic_perf: del topic_perf['total']
        
        performance_data[topic] = topic_perf # Ensure performance_data is updated

        question_index = 0
        session_correct = 0
        session_total = 0
        dbg(f"run_topic: Number of questions to iterate: {len(questions)}")
        while question_index < len(questions):
            q = questions[question_index]
            dbg(f"run_topic: Current question (q): {q}")
            # Determine canonical solution manifest for diff/display
            if 'solution' in q:
                sol_manifest = q['solution']
            elif 'suggestion' in q and isinstance(q['suggestion'], list) and q['suggestion']:
                sol_manifest = q['suggestion'][0]
            else:
                sol_manifest = None
            is_correct = False  # Reset for each question attempt
            user_answer_graded = False  # Flag to indicate if an answer was submitted and graded
            suggestion_shown_for_current_question = False  # New flag for this question attempt

            # For saving to lists, use original topic if reviewing, otherwise current topic
            question_topic_context = q.get('original_topic', topic)
            # Separate selection feedback from question display
            dbg("Before printing question")
            print(flush=True)

            # Display the current question and prompt once
            print(f"{Style.BRIGHT}{Fore.CYAN}Question {question_index + 1}/{len(questions)} (Topic: {question_topic_context})", flush=True)
            print(f"{Fore.CYAN}{'-' * 40}", flush=True)
            print(q['question'], flush=True)
            print(f"{Fore.CYAN}{'-' * 40}", flush=True)
            dbg("Before get_user_input")
            user_commands, special_action = get_user_input(allow_solution_command=not suggestion_shown_for_current_question)
            dbg(f"After get_user_input: user_commands={user_commands}, special_action={special_action}")
            if not user_commands and special_action is None:
                continue

            # Handle 'menu' command first, as it exits the topic
            if special_action == 'menu':
                print("Returning to main menu...")
                return # Exit run_topic function

            # --- Process special actions that don't involve grading ---
            if special_action == 'issue':
                create_issue(q, question_topic_context)
                input("Press Enter to continue...")
                continue # Re-display the same question prompt
            if special_action == 'source':
                # Open existing source URL or inform absence
                if q.get('source'):
                    print(f"Opening source in your browser: {q['source']}")
                    webbrowser.open(q['source'])
                else:
                    print("No source available for this question.")
                input("Press Enter to continue...")
                continue # Re-display the same question prompt
            if special_action == 'generate':
                new_q = generate_more_questions(topic, q)
                if new_q:
                    questions.insert(question_index + 1, new_q)
                    # Save the updated questions list to the topic file
                    # Only save if it's not a missed questions review session
                    if topic != '_missed':
                        save_questions_to_topic_file(question_topic_context, [q for q in questions if q.get('original_topic', topic) == question_topic_context])
                        print(f"Added new question to '{os.path.join(QUESTIONS_DIR, f'{question_topic_context}.yaml')}'.")
                    else:
                        print("A new question has been added to this session (not saved to file in review mode).")
                input("Press Enter to continue...")
                continue # Re-display the same question prompt (or the new one if it's next)

            # --- Process actions that involve grading or showing solution ---
            solution_text = "" # Initialize solution_text for scope
            if special_action == 'solution':
                is_correct = False # Viewing solution means not correct by own answer
                user_answer_graded = True
                suggestion_shown_for_current_question = True
                print(f"{Style.BRIGHT}{Fore.YELLOW}\nSuggestion:")
                solution_text = q.get('suggestion', [q.get('solution', 'N/A')])[0]
                if isinstance(solution_text, (dict, list)):
                    dumped = yaml.safe_dump(solution_text, default_flow_style=False, sort_keys=False, indent=2)
                    print(colorize_yaml(dumped))
                elif '\n' in solution_text:
                    print(colorize_yaml(solution_text))
                else:
                    print(f"{Fore.YELLOW}{solution_text}")
                if q.get('source'):
                    print(f"\n{Style.BRIGHT}{Fore.BLUE}Source: {q['source']}{Style.RESET_ALL}")
                # Handled by outer loop logic

            elif special_action == 'vim':
                user_manifest, result, sys_error = handle_vim_edit(q)
                if result is None: # Added check for None result
                    continue # Re-display the question prompt
                # If result is not a dict, treat as a message and display
                if not isinstance(result, dict):
                    print(str(result)) # Convert to string before printing
                    user_answer_graded = True
                    break
                if not sys_error:
                    if result.get('validation_feedback'):
                        print(f"{Style.BRIGHT}{Fore.YELLOW}\n--- Validation Details ---")
                        print(result['validation_feedback'])
                    
                    if result.get('ai_feedback'):
                        print(f"{Style.BRIGHT}{Fore.MAGENTA}\n--- AI Feedback ---")
                        print(result['ai_feedback'])

                    is_correct = result['correct']
                    if not is_correct:
                        # Use canonical solution manifest
                        if isinstance(sol_manifest, (dict, list)):
                            sol_text = yaml.safe_dump(sol_manifest, default_flow_style=False, sort_keys=False, indent=2)
                        else:
                            sol_text = sol_manifest or ''
                        show_diff(user_manifest, sol_text)
                        print(f"{Fore.RED}\nThat wasn't quite right. Here is the suggestion:")
                        print(colorize_yaml(sol_text))
                    else:
                        print(f"{Fore.GREEN}\nCorrect! Well done.")
            if q.get('source'):
                print(f"\n{Style.BRIGHT}{Fore.BLUE}Source: {q['source']}{Style.RESET_ALL}")
                user_answer_graded = True
                break # Exit inner loop, go to post-answer menu

            elif 'manifest' in q.get('question', '').lower():
                # Automatically use vim for manifest questions
                user_manifest, result, sys_error = handle_vim_edit(q)
                if result is None: # Added check for None result
                    continue # Re-display the question prompt
                # If result is not a dict, treat as a message and display
                if not isinstance(result, dict):
                    print(str(result)) # Convert to string before printing
                    user_answer_graded = True
                    break
                if not sys_error:
                    if result.get('validation_feedback'):
                        print(f"{Style.BRIGHT}{Fore.YELLOW}\n--- Validation Details ---")
                        print(result['validation_feedback'])
                    
                    if result.get('ai_feedback'):
                        print(f"{Style.BRIGHT}{Fore.MAGENTA}\n--- AI Feedback ---")
                        print(result['ai_feedback'])

                    is_correct = result['correct']
                    if not is_correct:
                        show_diff(user_manifest, q['solution'])
                        print(f"{Fore.RED}\nThat wasn't quite right. Here is the suggestion:")
                        print(colorize_yaml(q['solution']))
                    else:
                        print(f"{Fore.GREEN}\nCorrect! Well done.")
                    if q.get('source'):
                        print(f"\n{Style.BRIGHT}{Fore.BLUE}Source: {q['source']}{Style.RESET_ALL}")
                user_answer_graded = True
                break # Exit inner loop, go to post-answer menu
            elif user_commands:
                user_answer_graded = True
                user_answer_str = "\n".join(user_commands)
                
                # Normalize both user answer and suggestion for comparison
                normalized_user_answer = normalize_command(user_commands)
                
                # The suggestion can be a single string or a list of strings
                suggestions = q.get('suggestion')
                if not suggestions: # If 'suggestion' key is missing or empty
                    suggestions = [q.get('solution')]
                
                # Check if there's actually a suggestion to compare against
                if not suggestions or suggestions == [None]:
                    is_correct = False
                    print(f"{Fore.RED}No suggestion available for comparison.")
                    # Optionally, provide AI feedback if enabled, indicating no suggestion
                    if ai_feedback_enabled:
                        print(f"{Style.BRIGHT}{Fore.MAGENTA}\n--- AI Feedback ---")
                        ai_result = get_ai_verdict(q['question'], user_answer_str, "No suggestion provided")
                        feedback = ai_result['feedback']
                        print(feedback)
                    break # Exit inner loop to go to post-answer menu

                is_correct = False
                matched_suggestion = ""
                for sol in suggestions:
                    # Suggestions can be multiline commands
                    sol_str = str(sol)
                    sol_lines = sol_str.strip().split('\n')

                    normalized_sol = normalize_command(sol_lines)
                    
                    # Simple string comparison after normalization
                    if ' '.join(normalized_user_answer) == ' '.join(normalized_sol):
                        is_correct = True
                        matched_suggestion = sol
                        break

                if is_correct:
                    pass
                else:
                    # Showing diff and suggestion for incorrect answers
                    # Show diff if there's a single suggestion for clarity
                    if len(suggestions) == 1 and suggestions[0] is not None:
                        show_diff(user_answer_str, str(suggestions[0]))

                    print(f"{Style.BRIGHT}{Fore.YELLOW}\nSuggestion:")
                    solution_text = suggestions[0] # Show the first suggestion
                    if isinstance(solution_text, (dict, list)):
                        dumped = yaml.safe_dump(solution_text, default_flow_style=False, sort_keys=False, indent=2)
                        print(colorize_yaml(dumped))
                    elif '\n' in solution_text:
                        print(colorize_yaml(solution_text))
                    else:
                        print(f"{Fore.YELLOW}{solution_text}")

                if q.get('source'):
                    print(f"\n{Style.BRIGHT}{Fore.BLUE}Source: {q['source']}{Style.RESET_ALL}")

                if ai_feedback_enabled and not is_correct:
                    print(f"{Style.BRIGHT}{Fore.MAGENTA}\n--- AI Feedback ---")
                    ai_result = get_ai_verdict(q['question'], user_answer_str, suggestions[0])
                    feedback = ai_result['feedback']
                    is_correct = ai_result['correct']
                    print(feedback)

                # Final binary decision
                if is_correct:
                    print(f"\n{Fore.GREEN}Correct")
                else:
                    print(f"\n{Fore.RED}Incorrect")

                break # Exit inner loop, go to post-answer menu
            else: # User typed 'done' without commands, or empty input
                print("Please enter a command or a special action.")
                continue # Re-display the same question prompt

        # End of inner while question_index < len(questions) loop
        question_index += 1 # Increment question_index after processing

        # Post-answer menu (after a question has been answered or skipped)
        if user_answer_graded:
            # Save performance data after each graded question
            save_performance_data(performance_data)

        # If all questions in the current session are done, break the outer loop
        if question_index >= len(questions):
            break # Exit outer loop, all questions done

        # Post-answer menu loop
        while True:
            print(f"\n{Style.BRIGHT}{Fore.CYAN}--- Question {question_index}/{len(questions)} ---" + Style.RESET_ALL)
            print(f"{Style.BRIGHT}{Fore.CYAN}1. Next Question{Style.RESET_ALL}")
            print(f"{Style.BRIGHT}{Fore.CYAN}2. Review Missed Questions{Style.RESET_ALL}")
            print(f"{Style.BRIGHT}{Fore.CYAN}3. Return to Topic Menu{Style.RESET_ALL}")
            print(f"{Style.BRIGHT}{Fore.CYAN}4. Quit{Style.RESET_ALL}")
            choice = input(f"{Style.BRIGHT}{Fore.YELLOW}Enter your choice: {Style.RESET_ALL}").strip().lower()

            if choice == '1':
                break # Exit post-answer menu, go to next question
            elif choice == '2':
                # This will restart the outer loop with missed questions
                topic = '_missed'
                num_to_study = 0 # Study all missed questions
                break # Exit post-answer menu, restart outer loop
            elif choice == '3':
                return # Exit run_topic function, go to main menu
            elif choice == '4':
                sys.exit(0) # Exit application
            else:
                print(f"{Fore.RED}Invalid choice. Please try again.{Style.RESET_ALL}")



        # --- Post-answer interaction ---
        # This block is reached after a question has been answered/skipped/solution viewed.
        # The user can now choose to navigate or report an issue.
        
        # Update performance data only if an answer was graded (not just viewing source/issue)
        if user_answer_graded:
            session_total += 1
            if is_correct:
                session_correct += 1
                normalized_question_text = get_normalized_question_text(q)
                if normalized_question_text not in topic_perf['correct_questions']:
                    topic_perf['correct_questions'].append(normalized_question_text)
                # Also remove from missed questions if it was there
                remove_question_from_list(MISSED_QUESTIONS_FILE, q)
                if topic != '_missed':
                    save_performance_data(performance_data)
            else:
                # If the question was previously answered correctly, remove it.
                normalized_question_text = get_normalized_question_text(q)
                if normalized_question_text in topic_perf['correct_questions']:
                    topic_perf['correct_questions'].remove(normalized_question_text)
                save_question_to_list(MISSED_QUESTIONS_FILE, q, question_topic_context)
                if topic != '_missed':
                    save_performance_data(performance_data)

        if topic != '_missed':
                performance_data[topic] = topic_perf

        # Post-answer menu loop
        while True:
            print(f"\n{Style.BRIGHT}{Fore.CYAN}--- Question Completed ---")
            print("Options: [n]ext, [b]ack, [i]ssue, [s]ource, [r]etry, [c]onfigure, [q]uit")
            post_action = input(f"{Style.BRIGHT}{Fore.BLUE}> {Style.RESET_ALL}").lower().strip()

            if post_action == 'n':
                question_index += 1
                break # Exit post-answer loop, advance to next question
            elif post_action == 'b':
                if question_index > 0:
                    question_index -= 1
                    break # Exit post-answer loop, go back to previous question
                else:
                    print("Already at the first question.")
            elif post_action == 'i':
                create_issue(q, question_topic_context) # Issue for the *current* question
                # Stay in this loop, allow other options
            elif post_action == 'c':
                handle_config_menu()
                continue # Re-display the same question prompt after config
            elif post_action == 's':
                # Open existing source or search/assign new one
                if not q.get('source'):
                    # Interactive search to assign or explore sources
                    if search is None:
                        print("'googlesearch-python' is not installed. Cannot search for sources.")
                        input("Press Enter to continue...")
                        continue
                    question_text = q.get('question', '').strip()
                    print(f"\nSearching for source for: {question_text}")
                    try:
                        results = list(search(f"kubernetes {question_text}", num_results=5))
                    except Exception as e:
                        print(f"Search error: {e}")
                        input("Press Enter to continue...")
                        continue
                    if not results:
                        print("No search results found.")
                        input("Press Enter to continue...")
                        continue
                    # Determine default as first kubernetes.io link if present
                    default_idx = next((i for i, u in enumerate(results) if 'kubernetes.io' in u), 0)
                    print("Search results:")
                    for i_enum, url in enumerate(results, 1):
                        marker = ' (default)' if (i_enum-1) == default_idx else ''
                        print(f"  {i_enum}. {url}{marker}")
                    # Prompt user for action
                    while True:
                        raw_sel = input("  Choose default [1] or enter number, [o]pen all, [s]kip: ")
                        if raw_sel is None:
                            print("Error: Input received None. This should not happen.")
                            continue
                        sel = raw_sel.strip().lower()
                        if sel == '':
                            chosen = results[default_idx]
                            print(f"Assigned default source: {chosen}")
                        elif sel == 's':
                            print("Skipping source assignment.")
                            chosen = None
                        elif sel.startswith('o'):
                            parts = sel.split()
                            if len(parts) == 2 and parts[1].isdigit():
                                idx = int(parts[1]) - 1
                                if 0 <= idx < len(results):
                                    webbrowser.open(results[idx])
                                    continue
                            print("Invalid open command.")
                            continue
                        elif sel.isdigit() and 1 <= int(sel) <= len(results):
                            chosen = results[int(sel)-1]
                            print(f"Assigned source: {chosen}")
                        else:
                            print("Invalid choice.")
                            continue
                        # Apply assignment if any
                        if chosen:
                            q['source'] = chosen
                            if topic != '_missed':
                                file_path = os.path.join(QUESTIONS_DIR, f"{topic}.yaml")
                                topic_data = load_questions(topic)
                                if topic_data and 'questions' in topic_data:
                                    for orig_q in topic_data['questions']:
                                        if get_normalized_question_text(orig_q) == get_normalized_question_text(q):
                                            orig_q['source'] = chosen
                                            break
                                with open(file_path, 'w') as f:
                                    yaml.dump(topic_data, f, sort_keys=False)
                                print(f"Saved source to {file_path}")
                        input("Press Enter to continue...")
                        break
                else:
                    # Open existing source URL
                    try:
                        print(f"Opening source in your browser: {q['source']}")
                        webbrowser.open(q['source'])
                    except Exception as e:
                        print(f"Could not open browser: {e}")
                    input("Press Enter to continue...")
                continue  # Re-display the same question prompt
            elif post_action == 'r':
                # Stay on the same question, clear user input, and re-prompt
                user_commands.clear()
                suggestion_shown_for_current_question = False # Reset for retry
                print("\nRetrying the current question...")
                break # Exit post-answer loop, re-enter inner loop for current question
            elif post_action == 'l':
                # Optional LLM feedback with custom query
                custom_query = input("Enter custom query for AI feedback (or press Enter for general clarification): ").strip()
                if custom_query: # Only generate and display feedback if a custom query is provided
                    print(f"{Style.BRIGHT}{Fore.MAGENTA}\n--- AI Feedback ---")
                    # Determine the student's answer for feedback
                    try:
                        ua = user_answer_str
                    except NameError:
                        ua = globals().get('user_manifest', '')
                    # Determine the canonical solution
                    try:
                        sol = solution_text
                    except NameError:
                        sols = q.get('suggestion') or []
                        sol = sols[0] if sols else q.get('solution', '')
                    ai_result = get_ai_verdict(q['question'], ua, sol, custom_query=custom_query or None)
                    feedback = ai_result['feedback']
                    print(feedback)
                else:
                    print("No custom query provided. AI feedback not generated.")
                input("Press Enter to continue...")
                continue
            elif post_action == 'q':
                # Persist performance data and exit the run_topic function
                if topic != '_missed':
                    save_performance_data(performance_data)
                return  # Exit run_topic immediately
            else:
                print("Invalid option. Please choose 'n', 'b', 'i', 'g', 's', 'r', 'l', or 'q'.")

    

    
    # After completing all questions, offer post-completion options
    # Session completed: persistence
    while True:
        print(f"{Style.BRIGHT}{Fore.GREEN}Great job! You've completed all questions for this topic.{Style.RESET_ALL}")
        if topic != '_missed':
            save_performance_data(performance_data)
        print(f"\n{Style.BRIGHT}{Fore.CYAN}--- Topic Completed ---{Style.RESET_ALL}")
        # Determine if generate is available (100% complete)
        topic_data = load_questions(topic)
        total_q = len(topic_data.get('questions', [])) if topic_data else 0
        stats = performance_data.get(topic, {})
        num_correct = len(stats.get('correct_questions') or [])
        gen_opt = ''
        if total_q > 0 and num_correct == total_q:
            gen_opt = ", [g]enerate more questions"
        print(f"Options: [r]etry topic{gen_opt}, [q]uit to main menu")
        choice = input(f"{Style.BRIGHT}{Fore.BLUE}> {Style.RESET_ALL}").strip().lower()
        if choice == 'r':
            # Clear correct answers for fresh retry
            if topic != '_missed' and stats is not None:
                stats['correct_questions'] = []
                save_performance_data(performance_data)
            # Reload questions and restart
            questions_all = topic_data.get('questions', []) if topic_data else []
            return run_topic(topic, len(questions_all), performance_data, list(questions_all))
        elif choice == 'g' and gen_opt:
            # Generate a new question based on a random existing one
            base_q = None
            if topic_data and topic_data.get('questions'):
                base_q = random.choice(topic_data['questions'])
            new_q = generate_more_questions(topic, base_q)
            if new_q:
                # Append and save
                topic_data['questions'].append(new_q)
                file_path = os.path.join(QUESTIONS_DIR, f"{topic}.yaml")
                with open(file_path, 'w') as f:
                    yaml.dump(topic_data, f, sort_keys=False)
                print(f"Added new question to '{file_path}'.")
            else:
                print("No new question generated.")
            # Stay in loop to allow retry or generate again
            continue
        elif choice == 'q':
            print("Returning to main menu...")
            return
        else:
            print("Invalid option. Please choose 'r', 'g', or 'q'.")

    # kubectl command dry-run logic has been removed; command questions rely on normalization and AI feedback only

# --- Source Management Commands ---
def get_source_from_consolidated(item):
    metadata = item.get('metadata', {}) or {}
    for key in ('links', 'source', 'citation'):
        if key in metadata and metadata[key]:
            val = metadata[key]
            return val[0] if isinstance(val, list) else val
    return None

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

@click.command()
@click.option('--add-sources', 'add_sources', is_flag=True, default=False,
              help='Add missing sources from a consolidated YAML file.')
@click.option('--consolidated', 'consolidated', type=click.Path(), default=None,
              help='Path to consolidated YAML with sources (required with --add-sources).')
@click.option('--check-sources', 'check_sources', is_flag=True, default=False,
              help='Check all question files for missing sources.')
@click.option('--interactive-sources', 'interactive_sources', is_flag=True, default=False,
              help='Interactively search and assign sources to questions.')
@click.option('--auto-approve', 'auto_approve', is_flag=True, default=False,
              help='Auto-approve the first search result (use with --interactive-sources).')
@click.pass_context
def cli(ctx, add_sources, consolidated, check_sources, interactive_sources, auto_approve):
    """Kubelingo CLI tool for CKAD exam study or source management."""
    # Load environment variables from .env file
    load_dotenv()
    # Handle source management modes
    if add_sources:
        if not consolidated:
            click.echo("Error: --consolidated PATH is required with --add-sources.")
            sys.exit(1)
        cmd_add_sources(consolidated, questions_dir=QUESTIONS_DIR)
        return
    if check_sources:
        cmd_check_sources(questions_dir=QUESTIONS_DIR)
        return
    if interactive_sources:
        cmd_interactive_sources(questions_dir=QUESTIONS_DIR, auto_approve=auto_approve)
        return
    colorama_init(autoreset=True)
    print(colorize_ascii_art(ASCII_ART))
    statuses = test_api_keys()
    if not any(statuses.values()):
        print(f"{Fore.RED}Warning: No valid API keys found. Without a valid API key, you will just be string matching against a single suggested answer.{Style.RESET_ALL}")
        os.makedirs(QUESTIONS_DIR, exist_ok=True)
    ctx.ensure_object(dict)
    # Load existing performance data; do not overwrite existing progress on startup
    performance_data = load_performance_data()
    ctx.obj['PERFORMANCE_DATA'] = performance_data
    
    while True:
        dbg("cli: calling list_and_select_topic")
        topic_info = list_and_select_topic(performance_data)
        dbg(f"cli: list_and_select_topic returned {topic_info}")
        if topic_info is None or topic_info[0] is None:
            save_performance_data(performance_data)
            backup_performance_file()
            break
        
        selected_topic, num_to_study, questions_to_study = topic_info
        
        backup_performance_file()
        run_topic(selected_topic, num_to_study, performance_data, questions_to_study)
        save_performance_data(performance_data)
        backup_performance_file()
        # In non-interactive mode (e.g., piped input), exit after one run to avoid hanging.
        if not sys.stdin.isatty():
            break
        # Pause briefly before redisplaying the menu in interactive mode.
        time.sleep(2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kubelingo CLI tool for CKAD exam study.")
    parser.add_argument('--cli-answer', type=str, help='Provide an answer directly for a single question in non-interactive mode.')
    parser.add_argument('--cli-question-topic', type=str, help='Specify the topic for --cli-answer mode.')
    parser.add_argument('--cli-question-index', type=int, help='Specify the 0-based index of the question within the topic for --cli-answer mode.')
    args = parser.parse_args()

    # Mark CLI mode for run_topic to detect piped input
    os.environ['KUBELINGO_CLI_MODE'] = '1'

    if args.cli_answer and args.cli_question_topic is not None and args.cli_question_index is not None:
        # Non-interactive mode for answering a single question
        performance_data = load_performance_data()
        topic_data = load_questions(args.cli_question_topic)
        if topic_data and 'questions' in topic_data:
            questions_to_study = [topic_data['questions'][args.cli_question_index]]
            # Temporarily override get_user_input for this specific run
            _CLI_ANSWER_OVERRIDE = args.cli_answer # Set the global override variable
            
            print(f"Processing question from topic '{args.cli_question_topic}' at index {args.cli_question_index} with answer: '{args.cli_answer}'")
            run_topic(args.cli_question_topic, 1, performance_data, questions_to_study)
            save_performance_data(performance_data)
            backup_performance_file()
            sys.exit(0) # Exit after processing the single question
        else:
            print(f"Error: Topic '{args.cli_question_topic}' not found or has no questions.", file=sys.stderr)
            sys.exit(1)
    else:
        # Original interactive CLI mode
        cli(obj={})
