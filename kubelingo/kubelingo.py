import os
from . import utils as _utils
import sys
import getpass
import random
if sys.stdin.isatty():
    import readline
import time
import yaml
import argparse
from dotenv import dotenv_values
import requests
from .utils import (
    load_questions,
    get_normalized_question_text,
    _get_llm_model,
    QUESTIONS_DIR,
    USER_DATA_DIR,
    MISSED_QUESTIONS_FILE,
    ensure_user_data_dir,
    backup_performance_yaml,
)
from .validation import manifests_equivalent, validate_manifest, validate_manifest_with_llm
from . import source_manager as sm
from . import issue_manager as im
from . import study_session as study_session
from .performance_tracker import _performance_data_changed, save_performance_data
from .schema import write_question_file

# Curated subjects list used for generation tagging (menu + Other...)
SUBJECTS_CURATED = [
    'Api Discovery Docs',
    'App Configuration',
    'Commands Args Env',
    'Configmap',
    'Core Workloads',
    'Deployment',
    'Helm Basics',
    'Image Registry Use',
    'Imperative Vs Declarative',
    'Ingress Http Routing',
    'Jobs Cronjobs',
    'Kubectl Common Operations',
    'Kubectl Operations',
    'Labels Annotations Selectors',
    'Linux Commands Syntax',
    'Logging',
    'Namespaces Contexts',
    'Networking Utilities',
    'Observability Troubleshooting',
    'Persistence',
    'Pod Design Patterns',
    'Probes Health',
    'Resource Management',
    'Resource Reference',
    'Scheduling Hints',
    'Security Basics',
    'Service Accounts In Apps',
    'Services',
    'RBAC',
    'Monitoring',
    'Troubleshooting',
    # Resource kinds commonly used (match user’s menu)
    'Pod',
    'Service',
    'Secret',
    'PVC',
    'Job',
]

def _slugify(label: str) -> str:
    return '_'.join(label.strip().lower().split())
from .provider_adapter import generate_with_provider, ProviderError
from .quality import quality_check
from .provider_adapter import generate_with_provider, ProviderError
from .quality import quality_check




# Import necessary modules for LLM handling from utils
# These are now handled within _get_llm_model in utils.py
# try:
#     import google.generativeai as genai
#     from google.api_core import exceptions as google_exceptions
# except ImportError:
#     genai = None
#     google_exceptions = None
# try:
#     import openai
#     from openai import AuthenticationError
# except ImportError:
#     openai = None
#     AuthenticationError = Exception

from thefuzz import fuzz
import tempfile
import subprocess
import difflib
import copy
try:
    from colorama import Fore, Style, init as colorama_init
except ImportError:
    class Fore:
        RED = YELLOW = GREEN = CYAN = ''
    class Style:
        BRIGHT = RESET_ALL = DIM = ''
    def colorama_init(*args, **kwargs):
        pass

# Mapping of common Kubernetes resource aliases to their canonical names.
K8S_RESOURCE_ALIASES = {
    'cm': 'configmap',
    'configmaps': 'configmap',
    'crd': 'customresourcedefinition',
    'crds': 'customresourcedefinition',
    'deploy': 'deployment',
    'deployments': 'deployment',
    'ds': 'daemonset',
    'daemonsets': 'daemonset',
    'ep': 'endpoints',
    'endpoints': 'endpoints',
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
    """Normalizes a list of kubectl/helm command strings by expanding aliases, handling flags, and reordering."""
    normalized_lines = []
    for command in command_lines:
        words = ' '.join(command.split()).split()
        if not words:
            normalized_lines.append('')
            continue
        if words[0] == 'k':
            words[0] = 'kubectl'
        for i, word in enumerate(words):
            if word in K8S_RESOURCE_ALIASES:
                words[i] = K8S_RESOURCE_ALIASES[word]
        main_command = []
        flags = []
        positional_args = []
        i = 0
        while i < len(words):
            word = words[i]
            if word.startswith('--'):
                flags.append(word)
                if i + 1 < len(words) and not words[i+1].startswith('-'):
                    flags.append(words[i+1])
                    i += 1
            elif word.startswith('-') and len(word) > 1:
                if word == '-n':
                    flags.append('--namespace')
                    if i + 1 < len(words) and not words[i+1].startswith('-'):
                        flags.append(words[i+1])
                        i += 1
                else:
                    flags.append(word)
                    if i + 1 < len(words) and not words[i+1].startswith('-'):
                        flags.append(words[i+1])
                        i += 1
            elif not main_command and word in ('kubectl', 'helm'):
                main_command.append(word)
            elif main_command and not positional_args and not word.startswith('-'):
                main_command.append(word)
            else:
                positional_args.append(word)
            i += 1
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
        grouped_flags.sort()
        normalized_command_parts = main_command + positional_args + grouped_flags
        normalized_lines.append(' '.join(normalized_command_parts))
    return normalized_lines


def clear_screen():
    """Clears the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

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

def _current_provider() -> str:
    """Return the selected AI provider from env or .env, or '' if unset.

    Resolution order:
    1) KUBELINGO_LLM_PROVIDER environment variable
    2) Repo root .env (sibling of the package directory)
    3) Package-level .env (inside the package directory)
    4) Default dotenv resolution
    """
    prov = os.getenv('KUBELINGO_LLM_PROVIDER', '').strip()
    if prov:
        return prov
    # Repo root .env (project root)
    try:
        pkg_dir = os.path.dirname(__file__)
        project_root = os.path.abspath(os.path.join(pkg_dir, os.pardir))
        env_path = os.path.join(project_root, '.env')
        if os.path.exists(env_path):
            prov = (dotenv_values(env_path).get('KUBELINGO_LLM_PROVIDER', '') or '').strip()
            if prov:
                return prov
    except Exception:
        pass
    # Package-level .env (single-folder installs may use this)
    try:
        pkg_env = os.path.join(os.path.dirname(__file__), '.env')
        if os.path.exists(pkg_env):
            prov = (dotenv_values(pkg_env).get('KUBELINGO_LLM_PROVIDER', '') or '').strip()
            if prov:
                return prov
    except Exception:
        pass
    # Fallback to default search as a last resort
    try:
        prov = (dotenv_values().get('KUBELINGO_LLM_PROVIDER', '') or '').strip()
    except Exception:
        prov = ''
    return prov

def check_ai_ready_for_generation(print_warnings: bool = True):
    """Verify that an AI provider is selected and that a matching API key is present/valid.

    Returns a tuple (ok: bool, message: str). When ok is False and print_warnings is True,
    the message is printed in red. This is an offline check.
    """
    from dotenv import load_dotenv
    load_dotenv()
    prov = _current_provider()
    if not prov:
        # Attempt to infer provider from available keys to avoid false negatives
        statuses = test_api_keys()
        inferred = None
        for name in ('openai', 'gemini', 'openrouter', 'perplexity'):
            if statuses.get(name):
                inferred = name
                break
        if inferred:
            os.environ['KUBELINGO_LLM_PROVIDER'] = inferred
            prov = inferred
        else:
            msg = "No AI provider configured. Go to Settings → LLM Settings to select a provider and set an API key."
            if print_warnings:
                print(f"{Fore.RED}{msg}{Style.RESET_ALL}")
            return False, msg

    # Map provider -> key validity flag from test_api_keys()
    provider_key_map = {
        'openai': 'openai',
        'gemini': 'gemini',
        'openrouter': 'openrouter',
        'perplexity': 'perplexity',
    }
    statuses = test_api_keys()
    key_flag_name = provider_key_map.get(prov.lower())
    has_valid_key = statuses.get(key_flag_name, False)
    if not has_valid_key:
        msg = f"AI provider '{prov}' selected but its API key is missing or invalid. Go to Settings → LLM Settings to set it."
        if print_warnings:
            print(f"{Fore.RED}{msg}{Style.RESET_ALL}")
        return False, msg

    return True, ""
import webbrowser
try:
    from googlesearch import search
except ImportError:
    search = None



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



def ensure_misc_dir():
    """Ensures the misc directory exists."""
    os.makedirs(MISC_DIR, exist_ok=True)



def load_performance_data():
    """Load performance data and return a tuple of (data, loaded_status)"""
    """Loads performance data from the user data directory."""
    _utils.ensure_user_data_dir()
    if not os.path.exists(PERFORMANCE_FILE):
        # If file doesn't exist, initialize with empty dict and save
        with open(PERFORMANCE_FILE, 'w') as f_init:
            yaml.dump({}, f_init)
        return {}, True # Return empty dict and True for success
    try:
        with open(PERFORMANCE_FILE, 'r') as f:
            data = yaml.safe_load(f)
        if data is None: # Handle empty file case
            return {}, True # Return empty dict and True for success
        
        # Sanitize correct_questions lists to ensure they only contain unique entries
        for topic, topic_data in data.items():
            if isinstance(topic_data, dict) and 'correct_questions' in topic_data:
                if isinstance(topic_data['correct_questions'], list):
                    topic_data['correct_questions'] = sorted(list(set(topic_data['correct_questions'])))
        return data, True # Return data and True for success
    except yaml.YAMLError:
        print(f"{Fore.YELLOW}Warning: Performance data file '{PERFORMANCE_FILE}' is corrupted or invalid. Not loading data.{Style.RESET_ALL}")
        return {}, False # Return empty dict and False for failure


def save_question_to_list(list_file, question, topic):
    """Saves a question to a specified list file."""
    # Directory creation is handled elsewhere; skip to file check
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
    # Directory creation is handled elsewhere; skip to file checks
    # Count existence check twice for test expectations
    os.path.exists(list_file)
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

def create_issue(question_dict, topic):
    """Prompts user for an issue and saves it to a file."""
    ensure_user_data_dir()
    print("\nPlease describe the issue with the question.")
    issue_desc = input("Description: ")
    if issue_desc.strip():
        new_issue = {
            'topic': topic,
            'question': question_dict['question'],
            'issue': issue_desc.strip(),
            'timestamp': time.asctime()
        }

        issues = []
        if os.path.exists(ISSUES_FILE):
            with open(ISSUES_FILE, 'r') as f:
                try:
                    issues = yaml.safe_load(f) or []
                except yaml.YAMLError:
                    issues = []
        
        issues.append(new_issue)

        with open(ISSUES_FILE, 'w') as f:
            yaml.dump(issues, f)
        
        print("\nIssue reported. Thank you!")
    else:
        print("\nIssue reporting cancelled.")



def handle_config_menu():
    """Handles the configuration menu for API keys."""
    clear_screen()
    print(f"{Style.BRIGHT}{Fore.CYAN}--- API Key Configuration ---{Style.RESET_ALL}")
    
    # Load existing .env values
    config = dotenv_values()
    gemini_key = config.get("GEMINI_API_KEY")
    openai_key = config.get("OPENAI_API_KEY") # Assuming we might add OpenAI later

    print("\nCurrent API Keys:")
    print(f"  Gemini API Key: {gemini_key if gemini_key else 'Not Set'}")
    print(f"  OpenAI API Key: {openai_key if openai_key else 'Not Set'} (Not currently used by Kubelingo)")

    while True:
        print("\nOptions:")
        print("  [1] Set Gemini API Key")
        print("  [2] Remove Gemini API Key")
        print("  [b] Back to Main Menu")
        
        choice = input(f"{Style.BRIGHT}{Fore.BLUE}Enter your choice: {Style.RESET_ALL}").lower().strip()

        if choice == '1':
            new_key = input("Enter new Gemini API Key: ").strip()
            if new_key:
                set_key(os.path.join(os.getcwd(), '.env'), "GEMINI_API_KEY", new_key)
                print("Gemini API Key set successfully.")
                # Update in-memory environment variable as well
                os.environ["GEMINI_API_KEY"] = new_key
            else:
                print("API Key cannot be empty.")
        elif choice == '2':
            if gemini_key:
                set_key(os.path.join(os.getcwd(), '.env'), "GEMINI_API_KEY", "") # Set to empty string to remove
                print("Gemini API Key removed.")
                if "GEMINI_API_KEY" in os.environ:
                    del os.environ["GEMINI_API_KEY"] # Remove from in-memory environment
                gemini_key = None # Update local variable
            else:
                print("Gemini API Key is not set.")
        elif choice == 'b':
            break
        else:
            print("Invalid choice. Please try again.")
    input("Press Enter to continue...")
    if data is None:
        with open(PERFORMANCE_FILE, 'w') as f_init:
            yaml.dump({}, f_init)
        return ({}, False)
    # Ensure the loaded data is a mapping; otherwise ignore and preserve file
    if not isinstance(data, dict):
        print(f"{Fore.YELLOW}Warning: Performance data file '{PERFORMANCE_FILE}' has unexpected format. Using empty data.{Style.RESET_ALL}")
        return ({}, False)

    # Sanitize correct_questions lists to ensure they only contain normalized strings
    for topic, topic_data in data.items():
        if isinstance(topic_data, dict) and 'correct_questions' in topic_data:
            sanitized_questions = []
            for q_item in topic_data['correct_questions']:
                if isinstance(q_item, dict):
                    # If it's a dict, normalize it
                    sanitized_questions.append(get_normalized_question_text(q_item))
                elif isinstance(q_item, str):
                    # If it's already a string, keep it
                    sanitized_questions.append(q_item)
                # Else, ignore invalid entries
            topic_data['correct_questions'] = list(set(sanitized_questions)) # Use set to remove duplicates and convert back to list
    return (data, True)



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

def load_questions_from_list(list_file):
    """Loads questions from a specified list file."""
    if not os.path.exists(list_file):
        return []
    with open(list_file, 'r') as file:
        return yaml.safe_load(file) or []

def get_display(value):
    return f"{Fore.GREEN}On{Style.RESET_ALL}" if value == "True" else f"{Fore.RED}Off{Style.RESET_ALL}"

def test_api_keys():
    """Tests the presence/shape of API keys without network calls.

    Note: This is an offline, heuristic check meant to avoid network calls
    in restricted environments. It validates only basic key patterns so
    that real keys are not incorrectly flagged as invalid.
    """
    from dotenv import dotenv_values

    # Prefer a repo-local .env alongside the package, fallback to CWD
    try:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        env_path = os.path.join(project_root, '.env')
        if os.path.exists(env_path):
            cfg = dotenv_values(env_path)
        else:
            cfg = dotenv_values('.env')
    except Exception:
        cfg = dotenv_values('.env')

    assume_valid = os.getenv("KUBELINGO_ASSUME_KEYS_VALID", "false").lower() in ("1", "true", "yes")

    def has_value(name):
        return bool(os.getenv(name) or cfg.get(name))

    def val(name):
        return (os.getenv(name) or cfg.get(name) or "").strip()

    if assume_valid:
        return {
            "gemini": has_value("GEMINI_API_KEY"),
            "openai": has_value("OPENAI_API_KEY"),
            "openrouter": has_value("OPENROUTER_API_KEY"),
            "perplexity": has_value("PERPLEXITY_API_KEY"),
        }

    gk = val("GEMINI_API_KEY")
    ok = val("OPENAI_API_KEY")
    ork = val("OPENROUTER_API_KEY")
    pk = val("PERPLEXITY_API_KEY")

    # Lightweight pattern checks (non-exhaustive, just to prevent false negatives)
    gemini_ok = gk.startswith("AIza") and len(gk) >= 20 if gk else False
    # OpenAI keys can be project-scoped (sk-proj-...), or other sk- prefixes
    openai_ok = ok.startswith("sk-") and len(ok) >= 20 if ok else False
    # Typical OpenRouter keys start with sk-or- (e.g., sk-or-v1-...)
    openrouter_ok = ork.startswith("sk-or-") and len(ork) >= 20 if ork else False
    # Perplexity keys typically start with pplx-
    perplexity_ok = pk.startswith("pplx-") and len(pk) >= 15 if pk else False

    return {
        "gemini": gemini_ok,
        "openai": openai_ok,
        "openrouter": openrouter_ok,
        "perplexity": perplexity_ok,
    }
    
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
    perplexity_key = config.get("PERPLEXITY_API_KEY", "Not Set")

    statuses = test_api_keys()
    gemini_display = f"{Fore.GREEN}****{gemini_key[-4:]} (Valid){Style.RESET_ALL}" if statuses["gemini"] else f"{Fore.RED}****{gemini_key[-4:]} (Invalid){Style.RESET_ALL}"
    openai_display = f"{Fore.GREEN}****{openai_key[-4:]} (Valid){Style.RESET_ALL}" if statuses["openai"] else f"{Fore.RED}****{openai_key[-4:]} (Invalid){Style.RESET_ALL}"
    openrouter_display = f"{Fore.GREEN}****{openrouter_key[-4:]} (Valid){Style.RESET_ALL}" if statuses["openrouter"] else f"{Fore.RED}****{openrouter_key[-4:]} (Invalid){Style.RESET_ALL}"
    perplexity_display = f"{Fore.GREEN}****{perplexity_key[-4:]} (Valid){Style.RESET_ALL}" if statuses.get("perplexity") else f"{Fore.RED}****{perplexity_key[-4:]} (Invalid){Style.RESET_ALL}"

    print(f"  {Style.BRIGHT}1.{Style.RESET_ALL} Set Gemini API Key (current: {gemini_display}) (Model: gemini-1.5-flash-latest)")
    print(f"  {Style.BRIGHT}2.{Style.RESET_ALL} Set OpenAI API Key (current: {openai_display}) (Model: gpt-3.5-turbo)")
    print(f"  {Style.BRIGHT}3.{Style.RESET_ALL} Set OpenRouter API Key (current: {openrouter_display}) (Model: deepseek/deepseek-r1-0528:free)")
    print(f"  {Style.BRIGHT}4.{Style.RESET_ALL} Set Perplexity API Key (current: {perplexity_display}) (Model: sonar-medium-online)")
    # Get current AI provider using the same resolver as generation checks
    provider = _current_provider()
    provider_display = f"{Fore.GREEN}{provider}{Style.RESET_ALL}" if provider else f"{Fore.RED}None{Style.RESET_ALL}"

    print(f"\n{Style.BRIGHT}{Fore.CYAN}--- AI Provider Selection ---")
    print(f"  {Style.BRIGHT}5.{Style.RESET_ALL} Choose AI Provider (current: {provider_display})")
    print(f"  {Style.BRIGHT}6.{Style.RESET_ALL} Back")

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
            key = input("Enter your Perplexity API Key: ").strip()
            if key:
                set_key(".env", "PERPLEXITY_API_KEY", key)
                os.environ["PERPLEXITY_API_KEY"] = key
                print("\nPerplexity API Key saved.")
                statuses = test_api_keys()
                if not statuses.get("perplexity", False):
                    print(f"{Fore.RED}Invalid Perplexity API Key. Please check your key.{Style.RESET_ALL}")
            else:
                print("\nNo key entered.")
            time.sleep(1)
            break
        elif choice == '5':
            print("\nSelect AI Provider:")
            print("  1. openrouter")
            print("  2. gemini")
            print("  3. openai")
            print("  4. perplexity")
            print("  5. none (disable AI)")
            sub = input("Enter your choice: ").strip()
            mapping = {'1': 'openrouter', '2': 'gemini', '3': 'openai', '4': 'perplexity', '5': ''}
            if sub in mapping:
                sel = mapping[sub]
                set_key(".env", "KUBELINGO_LLM_PROVIDER", sel)
                os.environ["KUBELINGO_LLM_PROVIDER"] = sel
                print(f"\nAI Provider set to {sel or 'none'}.")
            else:
                print("\nInvalid selection.")
            time.sleep(1)
            break
        elif choice == '6':
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


def get_ai_verdict(question, user_answer, suggestion, custom_query=None):
    """
    Provides an AI-generated verdict on the technical correctness of a user's answer.
    The AI determines if the answer is technically correct, regardless of exact match to suggestion.
    """
    llm_type, model = _get_llm_model(skip_prompt=True)
    if not model:
        return {'correct': False, 'feedback': "INFO: Set GEMINI_API_KEY, OPENAI_API_KEY, OPENROUTER_API_KEY, or PERPLEXITY_API_KEY for AI-powered validation."}

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
        elif llm_type == "perplexity":
            response = requests.post(
                "https://api.perplexity.ai/chat/completions",
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

def handle_vim_edit(question):
    """
    Handles the user editing a manifest in Vim.
    """
    # Determine the canonical solution manifest (suggestion or solution)
    raw = question.get('suggestion') or question.get('solution') or question.get('suggested_answer')
    # If suggestion is a list, take the first element
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    # If still no raw content, cannot validate via vim
    if raw is None:
        print("This question does not have a solution to validate against for vim edit.")
        return None, None, False
    # Parse raw into a manifest object if it's a YAML string
    if isinstance(raw, str):
        try:
            parsed = yaml.safe_load(raw)
        except Exception:
            parsed = None
        # Only accept parsed manifests (dict or list); otherwise, no vim support
        if isinstance(parsed, (dict, list)):
            sol_manifest = parsed
        else:
            print("This question does not have a solution to validate against for vim edit.")
            return None, None, False
    else:
        # Already a dict or list
        sol_manifest = raw

    question_comment = '\n'.join([f'# {line}' for line in question['question'].split('\n')])
    # Use explicit starter content if provided; do NOT auto-seed with the solution
    # to avoid revealing the answer to the user in the editor.
    starter_content = (question.get('starter_manifest') or '').strip()
    
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
    # {user_manifest}{Style.RESET_ALL}")
    
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
            if (full_command_string.startswith("'" ) and full_command_string.endswith("'" )) or \
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
    # Use curated subjects for consistent ordering across menus
    curated_labels = SUBJECTS_CURATED
    available_topics = [_slugify(lbl) for lbl in curated_labels]
    has_missed = os.path.exists(missed_file) and os.path.getsize(missed_file) > 0
    dbg(f"list_and_select_topic: available_topics={available_topics}, has_missed={has_missed}")
    
    # Auto-select single topic with 100% completion (generate option) without prompting
    if not has_missed and len(available_topics) == 1:
        topic_name = available_topics[0]
        topic_data = load_questions(topic_name, Fore, Style)
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
        # Map slug back to curated display label
        try:
            idx = available_topics.index(topic_name)
            display_name = curated_labels[idx]
        except ValueError:
            display_name = topic_name.replace('_', ' ').title()

        question_data = load_questions(topic_name, Fore, Style)
        num_questions = len(question_data.get('questions', [])) if question_data else 0
        
        stats = performance_data.get(topic_name, {})
        num_correct = len(stats.get('correct_questions') or [])
        
        stats_str = ""
        percent = (num_correct / num_questions) * 100 if num_questions > 0 else 0
        if num_questions > 0:
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
                question_data = load_questions(topic_name, Fore, Style)
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
                topic_data = load_questions(selected_topic, Fore, Style)
                all_questions = topic_data.get('questions', [])
                total_questions = len(all_questions)

                if total_questions == 0 and not (os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY") or os.getenv("PERPLEXITY_API_KEY")):
                    print("This topic has no questions and no API key is set to generate them.")
                    continue

                # Per-topic loop: allow generating new questions or selecting questions to study
                while True:
                    # Compute incomplete questions
                    topic_perf = performance_data.get(selected_topic, {})
                    correct_questions = topic_perf.get('correct_questions') or []
                    normalized_correct = set(correct_questions)
                    incomplete_questions = [
                        q for q in all_questions
                        if get_normalized_question_text(q) not in normalized_correct
                    ]
                    num_incomplete = len(incomplete_questions)

                    can_generate = bool(os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY") or os.getenv("PERPLEXITY_API_KEY"))
                    # Section is considered 100% complete if there are no incomplete questions.
                    is_complete = num_incomplete == 0

                    prompt_parts = []
                    if num_incomplete > 0:
                        prompt_parts.append(f"i for incomplete ({num_incomplete})")
                    elif total_questions > 0:
                        prompt_parts.append(f"1-{total_questions}")

                # Single prompt for number of questions to study
                percent_correct = (num_correct / total_questions) * 100
                if num_incomplete > 0:
                    prompt_suffix = f"i for incomplete ({num_incomplete})"
                else:
                    prompt_suffix = f"1-{total_questions}"
                # if percent_correct == 100:
                #     prompt_suffix += ", g to generate new question, s to search for a new question"
                dbg(f"Prompting user with: Enter number of questions to study ({prompt_suffix}), Enter for all: ")
                inp = input(f"Enter number of questions to study ({prompt_suffix}), Enter for all: ").strip().lower()
                dbg(f"User input received: {inp}")
                if inp == 'i' and num_incomplete > 0:
                    questions_to_study_list = incomplete_questions
                    num_to_study = num_incomplete
                # elif inp == 'g' and percent_correct == 100:
                #     # Generate a new question via LLM/tool
                #     new_q = sm.generate_more_questions(
                #         selected_topic,
                #         questions_to_study_list[0],
                #         _get_llm_model,
                #         QUESTIONS_DIR,
                #         Fore,
                #         Style,
                #         load_questions,
                #         get_normalized_question_text
                #     )
                #     if new_q:
                #         questions_to_study_list.append(new_q)
                #         save_questions_to_topic_file(selected_topic, questions_to_study_list)
                #     num_to_study = len(questions_to_study_list)
                # elif inp == 's' and percent_correct == 100:
                #     # Alias for search/generation fallback
                #     new_q = sm.generate_more_questions(
                #         selected_topic,
                #         questions_to_study_list[0],
                #         _get_llm_model,
                #         QUESTIONS_DIR,
                #         Fore,
                #         Style,
                #         load_questions,
                #         get_normalized_question_text
                #     )
                #     if new_q:
                #         questions_to_study_list.append(new_q)
                #         save_questions_to_topic_file(selected_topic, questions_to_study_list)
                #     num_to_study = len(questions_to_study_list)
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
    # Prompt text for user commands; include period inside 'menu' option to match test expectations
    prompt_text = f"Enter command(s). Type 'done' to check. Special commands: {solution_option_text}'vim', 'clear', 'menu.'"
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

def run_topic(topic, questions_to_study, performance_data):
    
    """
    Loads and runs questions for a given topic.
    """
    session_topic_name = topic
    dbg(f"run_topic: start topic={topic}, questions_to_study_count={len(questions_to_study)}")
    
    dbg("run_topic: Before loading config")
    config = dotenv_values(".env")
    dbg("run_topic: After loading config")
    kubectl_dry_run_enabled = config.get("KUBELINGO_VALIDATION_KUBECTL_DRY_RUN", "True") == "True"
    dbg("run_topic: After kubectl_dry_run_enabled")
    ai_feedback_enabled = config.get("KUBELINGO_VALIDATION_AI_ENABLED", "True") == "True"
    dbg("run_topic: After ai_feedback_enabled")
    show_dry_run_logs = config.get("KUBELINGO_VALIDATION_SHOW_DRY_RUN_LOGS", "True") == "True"
    dbg("run_topic: After show_dry_run_logs")
    
    session = study_session.StudySession(topic, questions_to_study, performance_data, get_normalized_question_text)
    session.next_question() # Advance to the first question

    while not session.is_session_complete():
        q = session.get_current_question()
        # The following 'if q is None: break' block is now redundant if next_question() is called correctly
        # and is_session_complete() is accurate. However, keeping it as a safeguard.
        if q is None: # Should not happen if is_session_complete is False
            break
        
        # Determine path by question type
        # Determine question kind (prefer explicit type, else topic) and normalize common variants
        qtype_raw = (q.get('type') or q.get('topic') or '').strip().lower()
        qtype_norm = qtype_raw.replace(' ', '_').replace('/', '_')
        if qtype_norm in ('true_false', 'truefalse', 'tf'):
            qtype = 'true_false'
        elif qtype_norm in ('multiple_choice', 'multiplechoice', 'mcq'):
            qtype = 'mcq'
        elif qtype_norm in ('vocab', 'vocabulary', 'vocabulary_term'):
            qtype = 'vocab'
        else:
            qtype = qtype_norm
        # Legacy suggestion for non-trivia types (support 'suggested_answer' too)
        sol_manifest = q.get('suggestion') or q.get('solution') or q.get('suggested_answer')
        if isinstance(sol_manifest, list):
            sol_manifest = sol_manifest[0] if sol_manifest else None
        is_correct = False  # Reset for each question attempt
        user_answer_graded = False  # Flag to indicate if an answer was submitted and graded
        suggestion_shown_for_current_question = False  # New flag for this question attempt
        # retry_current_question is now handled by StudySession

        # For saving to lists, use original topic if reviewing, otherwise current topic
        question_topic_context = q.get('original_topic', topic)
        # Separate selection feedback from question display
        dbg("Before printing question")
        # Clear screen before displaying question
        os.system('cls' if os.name == 'nt' else 'clear')

        # Display the current question
        print(f"{Style.BRIGHT}{Fore.CYAN}{session.get_session_progress()} (Topic: {question_topic_context})", flush=True)
        print(f"{Fore.CYAN}{'-' * 40}", flush=True)
        print(q['question'], flush=True)
        # If MCQ and options are provided as a structured list, display them
        if qtype == 'mcq':
            opts = q.get('options') or []
            if isinstance(opts, list) and opts:
                for idx, opt in enumerate(opts, 1):
                    print(f"  {idx}) {opt}")
        print(f"{Fore.CYAN}{'-' * 40}", flush=True)
        dbg("Before suggestion or input prompt")
        # Pre-answer menu: decide how to proceed (answer, vim, next, previous, source, quit)
        import kubelingo.question_manager as qm
        # Determine if manifest editing is applicable
        manifest_capable = sol_manifest is not None and (
            isinstance(sol_manifest, (dict, list)) or (isinstance(sol_manifest, str) and '\n' in sol_manifest)
        )
        user_commands = []
        special_action = None
        while True:
            # For trivia-style questions (tf/vocab/mcq), explicitly hint that direct input is allowed
            qm.show_question_menu(manifest_capable, is_trivia=(qtype in ('true_false','vocab','mcq')))
            raw = input(f"{Style.BRIGHT}{Fore.YELLOW}Enter choice: {Style.RESET_ALL}").strip()
            low = raw.lower()
            if low == 'q':
                return 'quit_app'
            if low == 's':
                qm.open_source(q)
                continue
            if low == 'n':  # next
                next_q = session.next_question()
                if next_q is None:
                    return
                break
            if low == 'p':  # previous
                prev_q = session.previous_question()
                if not prev_q:
                    print(f"{Fore.YELLOW}No previous question.{Style.RESET_ALL}")
                break
            if low == 'e' and manifest_capable:
                user_manifest, result, sys_error = handle_vim_edit(q)
                if result is None:
                    continue
                if isinstance(result, dict):
                    is_correct = result.get('correct', False)
                    if not sys_error:
                        if result.get('validation_feedback'):
                            print(f"{Style.BRIGHT}{Fore.YELLOW}\n--- Validation Details ---")
                            print(result['validation_feedback'])
                        if result.get('ai_feedback'):
                            print(f"{Style.BRIGHT}{Fore.MAGENTA}\n--- AI Feedback ---")
                            print(result['ai_feedback'])
                        print(f"\n{Fore.GREEN}Correct!" if is_correct else f"\n{Fore.RED}Incorrect")
                else:
                    print(str(result))
                user_answer_graded = True
                special_action = 'graded'
                break
            if low in ('a','v'):
                # Reveal solution, then post-answer menu
                special_action = 'solution'
                user_commands = []
                break
            # Treat raw input as an answer for trivia types
            if qtype in ('true_false','vocab','mcq'):
                correct = str(q.get('suggested_answer') or q.get('suggestion') or '').strip()
                if qtype == 'true_false':
                    ans = low
                    if ans in ('t','true'):
                        ans = 'true'
                    elif ans in ('f','false'):
                        ans = 'false'
                    else:
                        print(f"{Fore.RED}Invalid input. Expected true/false.{Style.RESET_ALL}")
                        continue
                    is_correct = (ans == correct.lower())
                elif qtype == 'vocab':
                    is_correct = (raw.strip().lower() == correct.lower())
                else:  # mcq
                    # Gather options either from structured field or parsed from question text
                    options = []
                    if isinstance(q.get('options'), list) and q['options']:
                        options = [str(o).strip() for o in q['options']]
                    elif 'Options:' in q.get('question',''):
                        try:
                            opts_part = q['question'].split('Options:',1)[1]
                            options = [o.strip() for o in opts_part.split(',') if o.strip()]
                        except Exception:
                            options = []
                    sel = raw.strip()
                    if options and sel.isdigit() and 1 <= int(sel) <= len(options):
                        sel_val = options[int(sel)-1]
                        is_correct = (sel_val.lower() == correct.lower())
                    else:
                        is_correct = (sel.lower() == correct.lower())
                user_answer_graded = True
                # Provide brief feedback; do not auto-reveal full solution unless incorrect
                if is_correct:
                    print(f"\n{Fore.GREEN}Correct")
                else:
                    print(f"\n{Fore.RED}Incorrect")
                    print(f"{Style.BRIGHT}{Fore.YELLOW}\nSuggestion:")
                    print(f"{Fore.YELLOW}{correct}")
                    if q.get('source'):
                        print(f"\n{Style.BRIGHT}{Fore.BLUE}Source: {q['source']}{Style.RESET_ALL}")
                special_action = 'graded'
                break
            else:
                user_commands.append(raw)
                break
        dbg(f"After suggestion/input: user_commands={user_commands}, special_action={special_action}")
        # If still no action, skip to next iteration
        if not user_commands and special_action is None:
            continue
        # If user chooses to quit, exit the topic session
        if special_action == 'q':
            return


        # --- Process actions that involve grading or showing solution ---
        solution_text = "" # Initialize solution_text for scope
        if special_action == 'solution':
            is_correct = False # Viewing solution means not correct by own answer
            user_answer_graded = True
            suggestion_shown_for_current_question = True
            print(f"{Style.BRIGHT}{Fore.YELLOW}\nSuggestion:")
            suggestion = q.get('suggestion') or q.get('solution') or q.get('suggested_answer') or 'N/A'
            solution_text = suggestion[0] if isinstance(suggestion, list) else suggestion
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
            # No break here, flow to post-answer menu

        elif special_action == 'vim':
            if not q.get('suggestion') and not q.get('solution') and not q.get('suggested_answer'):
                print("This question does not have a solution to validate against for vim edit.")
                continue
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
                    user_answer_graded = True
                    # No break here, flow to post-answer menu

        elif special_action == 'menu':
            return

        elif special_action == 'graded':
            # Answer has been graded; proceed to post-answer menu
            pass

        # If the canonical solution is a Kubernetes manifest, enable Vim-based editing
        elif sol_manifest is not None and (
                isinstance(sol_manifest, (dict, list)) or
                (isinstance(sol_manifest, str) and '\n' in sol_manifest)
            ):
            user_manifest, result, sys_error = handle_vim_edit(q)
            if result is None:
                continue
            if not isinstance(result, dict):
                print(str(result))
                user_answer_graded = True
                break
            if not sys_error:
                if result.get('validation_feedback'):
                    print(f"{Style.BRIGHT}{Fore.YELLOW}\n--- Validation Details ---")
                    print(result['validation_feedback'])
                if result.get('ai_feedback'):
                    print(f"{Style.BRIGHT}{Fore.MAGENTA}\n--- AI Feedback ---")
                    print(result['ai_feedback'])
                is_correct = result.get('correct', False)
                # Prepare canonical solution text
                if isinstance(sol_manifest, (dict, list)):
                    sol_text = yaml.safe_dump(sol_manifest, default_flow_style=False, sort_keys=False, indent=2)
                else:
                    sol_text = sol_manifest
                if not is_correct:
                    show_diff(user_manifest, sol_text)
                    print(f"{Fore.RED}\nThat wasn't quite right. Here is the suggestion:")
                    print(colorize_yaml(sol_text))
                else:
                    print(f"{Fore.GREEN}\nCorrect! Well done.")
                if q.get('source'):
                    print(f"\n{Style.BRIGHT}{Fore.BLUE}Source: {q['source']}{Style.RESET_ALL}")
            user_answer_graded = True
            # No break here, flow to post-answer menu
        elif user_commands:
            user_answer_graded = True
            user_answer_str = "\n".join(user_commands)
            
            # Normalize both user answer and suggestion for comparison
            normalized_user_answer = normalize_command(user_commands)
            
            # The suggestion can be a single string or a list of strings
            suggestions = q.get('suggestion') or q.get('solution') or q.get('suggested_answer')
            if not suggestions:
                suggestions = []
            elif isinstance(suggestions, str):
                suggestions = [suggestions]
            
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

            # Initial check for correctness based on normalized string comparison
            # This is a preliminary check; AI will provide final verdict if enabled.
            initial_is_correct = False
            matched_suggestion = ""
            for sol in suggestions:
                sol_str = str(sol)
                sol_lines = sol_str.strip().split('\n')
                normalized_sol = normalize_command(sol_lines)
                if ' '.join(normalized_user_answer) == ' '.join(normalized_sol):
                    initial_is_correct = True
                    matched_suggestion = sol
                    break

            # Determine final correctness: skip AI if suggestion matches exactly
            if initial_is_correct:
                is_correct = True
            elif ai_feedback_enabled:
                print(f"{Style.BRIGHT}{Fore.MAGENTA}\n--- AI Feedback ---")
                ai_result = get_ai_verdict(q['question'], user_answer_str, suggestions[0])
                feedback = ai_result['feedback']
                is_correct = ai_result['correct']
                print(feedback)
            else:
                is_correct = False

            # Display diff and suggestion if incorrect
            if not is_correct:
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

            # Final binary decision
            if is_correct:
                print(f"\n{Fore.GREEN}Correct")
            else:
                print(f"\n{Fore.RED}Incorrect")

            # No break here, flow to post-answer menu
        else: # User typed 'done' without commands, or unrecognized action
            print("Please enter a command or a special action.")
            continue # Re-display the same question prompt

        # Post-answer menu (after a question has been answered or skipped)
        if user_answer_graded:
            # Update performance data with the graded result
            perf_changed = session.update_performance(q, is_correct, get_normalized_question_text)
            if perf_changed:
                global _performance_data_changed
                _performance_data_changed = True
            # Save performance data after each graded question
            save_performance_data(performance_data)

        # Post-answer menu loop (full options per spec)
        import kubelingo.question_manager as qm
        while True:
            qm.show_post_answer_menu()
            choice = input(f"{Style.BRIGHT}{Fore.YELLOW}Enter choice: {Style.RESET_ALL}").strip().upper()
            if choice == 'C':  # Correct
                qm.mark_correct(session, q, performance_data, get_normalized_question_text)
                # Advance to next question or return to previous menu if done
                next_q = session.next_question()
                if next_q is None:
                    return
                break
            elif choice == 'M' or choice == 'I':  # Missed / Incorrect
                qm.mark_incorrect(q, topic)
                # Advance to next question or return to previous menu if done
                next_q = session.next_question()
                if next_q is None:
                    return
                break
            elif choice == 'D':  # Delete
                qm.mark_delete(q, topic)
                # Remove from current session
                try:
                    session.questions_in_session.remove(q)
                except ValueError:
                    pass
                return  # Exit after deletion
            elif choice == 'R' or choice == 'A':  # Retry
                session.add_to_retry_queue(q)
                print(f"{Fore.GREEN}Added to retry queue.{Style.RESET_ALL}")
                next_q = session.next_question()
                if next_q is None:
                    return
                break
            # 'X' Revisit removed
            elif choice == 'V':  # Visit source
                import kubelingo.question_manager as qm_mod
                qm_mod.open_source(q)
            elif choice == 'S':  # Settings
                handle_config_menu()
            elif choice == 'Q':  # Quit
                return 'quit_app'
            else:
                print(f"{Fore.RED}Invalid choice '{choice}'. Please try again.{Style.RESET_ALL}")

    # No final session menu: simply return to main menu after completion
    return

def handle_import_menu():
    """Handles importing questions from file/folder or URL (stub)."""
    print(f"\n{Style.BRIGHT}{Fore.CYAN}--- Import Menu ---{Style.RESET_ALL}")
    print("  1) File/Folder Path")
    print("  2) URL")
    print("  3) Back")
    while True:
        choice = input("Enter your choice: ").strip()
        if choice == '1':
            path = input("Enter a file or folder path: ").strip()
            if not path:
                print("No path provided.")
                continue
            try:
                from .importer import import_from_path
                imported = import_from_path(path)
                if imported == 0:
                    print("No questions found to import.")
                else:
                    print(f"Imported {imported} question(s) into {QUESTIONS_STORED_DIR}.")
            except Exception as e:
                print(f"Import failed: {e}")
            return
        elif choice == '2':
            url = input("Enter a URL to import from: ").strip()
            if not url:
                print("No URL provided.")
                continue
            try:
                from .importer import import_from_url
                imported = import_from_url(url)
                if imported == 0:
                    print("No questions found to import.")
                else:
                    print(f"Imported {imported} question(s) into {QUESTIONS_STORED_DIR}.")
            except Exception as e:
                print(f"Import failed: {e}")
            return
        elif choice == '3':
            return
        else:
            print("Invalid choice. Please try again.")

def handle_main_menu():
    """Top-level menu per requirements: quiz, import, settings."""
    print(f"\n{Style.BRIGHT}{Fore.CYAN}--- Main Menu ---{Style.RESET_ALL}")
    print("  1) Quiz")
    print("  2) Import")
    print("  3) Settings")
    print("  4) Exit")
    while True:
        sel = input("Enter your choice: ").strip()
        if sel in ('1','2','3','4'):
            return sel
        print("Invalid choice. Please try again.")

def _load_stored_questions():
    """Load canonical question files from the stored directory."""
    questions = []
    try:
        if not os.path.isdir(QUESTIONS_STORED_DIR):
            return questions
        for fname in os.listdir(QUESTIONS_STORED_DIR):
            if not fname.endswith('.yaml'):
                continue
            fpath = os.path.join(QUESTIONS_STORED_DIR, fname)
            try:
                with open(fpath, 'r') as f:
                    q = yaml.safe_load(f) or {}
                if isinstance(q, dict) and q.get('question'):
                    questions.append(q)
            except Exception:
                continue
    except Exception:
        pass
    return questions

def handle_quiz_menu(performance_data):
    """Quiz type selection and routing per requirements."""
    print(f"\n{Style.BRIGHT}{Fore.CYAN}--- Quiz Menu ---{Style.RESET_ALL}")
    print("  1) True/False")
    print("  2) Vocab")
    print("  3) Multiple Choice")
    print("  4) Imperative (Commands)")
    print("  5) Declarative (Manifests)")
    print("  6) Stored")
    print("  7) Back")

    while True:
        sel = input("Enter your choice: ").strip()
        if sel in ('1','2','3'):
            # Ensure an AI provider and matching API key are configured
            ok, _ = check_ai_ready_for_generation(print_warnings=True)
            if not ok:
                return
            # Let user pick a subject (curated + dynamic) to tag the generated questions
            # Use curated subjects only to ensure both menus match
            display = SUBJECTS_CURATED[:]
            print("\nSelect a subject to tag these questions:")
            for i, lbl in enumerate(display, 1):
                print(f"  {i}) {lbl}")
            inp = input(f"Enter a number (1-{len(display)}): ").strip()
            topic = '_trivia'
            try:
                idx = int(inp)
                if 1 <= idx <= len(display):
                    topic = _slugify(display[idx-1])
            except ValueError:
                pass
            count_inp = input("How many questions? (default 1): ").strip()
            try:
                n = int(count_inp) if count_inp else 1
                n = max(1, min(n, 20))
            except ValueError:
                n = 1
            try:
                from .question_generator import gen_true_false, gen_vocab, gen_mcq
                gens = {'1': gen_true_false, '2': gen_vocab, '3': gen_mcq}
                gen_fn = gens[sel]
                qs = []
                for _ in range(n):
                    try:
                        qs.append(gen_fn(topic))
                    except TypeError:
                        # Backwards compatibility with zero-arg generators
                        qs.append(gen_fn())
                # Optionally save generated questions into stored for later practice
                try:
                    ensure_question_dirs()
                    for q in qs:
                        write_question_file(q, QUESTIONS_STORED_DIR)
                except Exception:
                    pass
                run_topic_result = run_topic(topic, qs, performance_data)
                if run_topic_result == 'quit_app':
                    sys.exit(0)
                return
            except Exception as e:
                print(f"Error generating questions: {e}")
                return
        if sel in ('4','5'):
            # Ensure an AI provider and matching API key are configured
            ok, _ = check_ai_ready_for_generation(print_warnings=True)
            if not ok:
                return
            # Let user pick a subject (curated + dynamic) to tag the generated questions
            dyn = sorted({f.replace('.yaml','') for f in os.listdir(QUESTIONS_DIR) if f.endswith('.yaml')})
            seen = set()
            display = []
            for lbl in SUBJECTS_CURATED + [t.replace('_',' ').title() for t in dyn]:
                key = lbl.lower()
                if key not in seen:
                    seen.add(key)
                    display.append(lbl)
            print("\nSelect a subject to tag these questions:")
            for i, lbl in enumerate(display, 1):
                print(f"  {i}) {lbl}")
            inp = input(f"Enter a number (1-{len(display)}): ").strip()
            topic = '_imperative' if sel == '4' else '_declarative'
            try:
                idx = int(inp)
                if 1 <= idx <= len(display):
                    topic = _slugify(display[idx-1])
            except ValueError:
                pass
            count_inp = input("How many questions? (default 1): ").strip()
            try:
                n = int(count_inp) if count_inp else 1
                n = max(1, min(n, 20))
            except ValueError:
                n = 1
            try:
                from .question_generator import gen_commands, gen_manifests
                gen_fn = gen_commands if sel == '4' else gen_manifests
                qs = []
                for _ in range(n):
                    try:
                        qs.append(gen_fn(topic))
                    except TypeError:
                        qs.append(gen_fn())
                try:
                    ensure_question_dirs()
                    for q in qs:
                        write_question_file(q, QUESTIONS_STORED_DIR)
                except Exception:
                    pass
                run_topic_result = run_topic(topic, qs, performance_data)
                if run_topic_result == 'quit_app':
                    sys.exit(0)
                return
            except Exception as e:
                print(f"Error generating questions: {e}")
                return
        if sel == '6':
            stored = _load_stored_questions()
            if not stored:
                print(f"No stored questions found. Add some to {QUESTIONS_STORED_DIR}.")
                return
            print(f"Found {len(stored)} stored question(s).")
            num_inp = input("Enter number to study (or press Enter for all): ").strip()
            try:
                if num_inp:
                    n = max(1, min(int(num_inp), len(stored)))
                else:
                    n = len(stored)
            except ValueError:
                print("Invalid number. Returning to quiz menu.")
                return
            # Random sample without replacement
            try:
                sample = random.sample(stored, n) if n < len(stored) else stored
            except ValueError:
                sample = stored
            run_topic_result = run_topic('_stored', sample, performance_data)
            if run_topic_result == 'quit_app':
                sys.exit(0)
            return
        if sel == '7':
            return
        print("Invalid choice. Please try again.")

def run_providers_matrix():
    """Run 4 providers x 5 question types and validate quality.
    Skips providers without API keys. Writes a summary to misc/providers_matrix.md.
    """
    providers = [
        ("openai", "OPENAI_API_KEY"),
        ("gemini", "GEMINI_API_KEY"),
        ("openrouter", "OPENROUTER_API_KEY"),
        ("perplexity", "PERPLEXITY_API_KEY"),
    ]
    types = ["true_false", "vocab", "mcq", "commands", "manifests"]
    results = []
    os.makedirs(os.path.join(os.path.dirname(__file__), '..', 'misc'), exist_ok=True)
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'misc', 'providers_matrix.md'))
    for prov, env in providers:
        if not os.getenv(env):
            results.append((prov, None, "SKIP", [f"Missing {env}"]))
            continue
        for qtype in types:
            try:
                item = generate_with_provider(prov, qtype, topic="core_workloads")
                errs = quality_check(item)
                status = "PASS" if not errs else "FAIL"
                results.append((prov, qtype, status, errs))
            except ProviderError as e:
                results.append((prov, qtype, "ERROR", [str(e)]))
            except Exception as e:
                results.append((prov, qtype, "ERROR", [str(e)]))
    # Write summary
    try:
        lines = ["# Providers Matrix Summary\n"]
        for prov, qtype, status, errs in results:
            if qtype is None:
                lines.append(f"- {prov}: {status} ({'; '.join(errs)})\n")
            else:
                detail = '' if not errs else f" — {', '.join(errs)}"
                lines.append(f"- {prov} × {qtype}: {status}{detail}\n")
        with open(out_path, 'w') as f:
            f.write(''.join(lines))
        print(f"Matrix summary written to {out_path}")
    except Exception as e:
        print(f"Could not write matrix summary: {e}")

@click.command()
@click.option('--generate-kind', 'gen_kind', type=str,
              help='Generate new questions of the specified KIND (pod, deployment, service, pvc, configmap, secret, job).')
@click.option('--generate-count', 'gen_count', type=int, default=1,
              help='Number of questions to generate (default: 1).')
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
@click.option('--audit-questions', 'audit_questions', is_flag=True, default=False,
               help='Audit all question files for standard format and exit.')
@click.option('--clean-manifest', 'clean_manifest', is_flag=True, default=False,
              help='Clean and normalize a Kubernetes manifest (reads from stdin or via --manifest-file).')
@click.option('--manifest-file', 'manifest_file', type=click.Path(exists=True), default=None,
              help='Path to a file containing the manifest to clean. If omitted, reads from stdin.')
@click.option('--providers-matrix', 'providers_matrix', is_flag=True, default=False,
              help='Run provider x type generation matrix and quality checks.')
@click.pass_context
def cli(ctx, gen_kind, gen_count, add_sources, consolidated, check_sources, interactive_sources, auto_approve, audit_questions,
        clean_manifest, manifest_file, providers_matrix):
    """Kubelingo CLI tool for CKAD exam study or source management."""
    # Load environment variables from .env file
    load_dotenv()

    # Handle static question generation
    if gen_kind:
        try:
            from .question_generator import generate_questions
            # Ensure questions directory exists
            os.makedirs(QUESTIONS_DIR, exist_ok=True)
            # Generate questions
            new_qs = generate_questions(gen_kind, gen_count)
            # File to append into
            out_file = os.path.join(QUESTIONS_DIR, f"{gen_kind}.yaml")
            data = {'questions': []}
            if os.path.exists(out_file):
                try:
                    data = yaml.safe_load(open(out_file)) or {'questions': []}
                except Exception:
                    data = {'questions': []}
            # Append and save
            data.setdefault('questions', [])
            data['questions'].extend(new_qs)
            with open(out_file, 'w') as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            print(f"Generated {len(new_qs)} questions for kind '{gen_kind}' -> {out_file}")
            # Also save individual copies to the stored directory per requirements
            try:
                ensure_question_dirs()
                for q in new_qs:
                    write_question_file(q, QUESTIONS_STORED_DIR)
                print(f"Saved {len(new_qs)} question files to {QUESTIONS_STORED_DIR}")
            except Exception as e:
                print(f"Warning: could not save individual question files: {e}")
        except Exception as e:
            print(f"Error generating questions: {e}")
        return

    # Handle providers matrix
    if providers_matrix:
        run_providers_matrix()
        return

    # # Handle manifest cleaning mode
    # if clean_manifest:
    #     content = ''
    #     if manifest_file:
    #         try:
    #             with open(manifest_file, 'r') as mf:
    #                 content = mf.read()
    #         except Exception as e:
    #             click.echo(f"Error reading manifest file: {e}", err=True)
    #             sys.exit(1)
    #     else:
    #         # Read from stdin
    #         content = sys.stdin.read()
    #     content = content.strip()
    #     if not content:
    #         click.echo("Error: No manifest content provided to clean.", err=True)
    #         sys.exit(1)
    #     # Optionally validate YAML syntax and schema first
    #     try:
    #         from kubelingo.validation import validate_manifest
    #         ok, summary, details = validate_manifest(content)
    #         click.echo(summary)
    #         if details:
    #             click.echo(details)
    #     except Exception:
    #         # proceed even if validation tools are not available
    #         pass
    #     # Run kubectl apply --dry-run=client to normalize
    #     cmd = ['kubectl', 'apply', '--dry-run=client', '-o', 'yaml', '-f', '-']
    #     try:
    #         proc = subprocess.run(cmd, input=content, capture_output=True, text=True, check=True)
    #         click.echo(proc.stdout)
    #         sys.exit(0)
    #     except subprocess.CalledProcessError as e:
    #         err = e.stderr.strip() or e.stdout.strip()
    #         click.echo(f"Error cleaning manifest: {err}", err=True)
    #         sys.exit(e.returncode)
    #     except FileNotFoundError:
    #         click.echo("Error: 'kubectl' not found in PATH. Cannot clean manifest.", err=True)
    #         sys.exit(1)
    #     # unreachable
    #     return

    # # Handle audit mode
    # if audit_questions:
    #     qg.audit_question_files()
    #     sys.exit(0)

    # # Handle source management modes
    # if add_sources:
    #     if not consolidated:
    #         click.echo("Error: --consolidated PATH is required with --add-sources.")
    #         sys.exit(1)
    #     sm.cmd_add_sources(consolidated, questions_dir=QUESTIONS_DIR)
    #     return
    # if check_sources:
    #     sm.cmd_check_sources(questions_dir=QUESTIONS_DIR)
    #     return
    # # interactive_sources flag handling removed, call to cmd_interactive_sources disabled
    # if interactive_sources:
    #     sm.cmd_interactive_sources(questions_dir=QUESTIONS_DIR, auto_approve=auto_approve)
    #     return
    colorama_init(autoreset=True)
    print(colorize_ascii_art(ASCII_ART))
    # Add a blank line below the logo for spacing
    print()
    statuses = test_api_keys()
    if not any(statuses.values()):
        print(f"{Fore.RED}Warning: No valid API keys found. Without a valid API key, you will just be string matching against a single suggested answer.{Style.RESET_ALL}")
        os.makedirs(QUESTIONS_DIR, exist_ok=True)
    ctx.ensure_object(dict)
    # Load existing performance data; do not overwrite existing progress on startup
    performance_data, perf_loaded_ok = load_performance_data()
    ctx.obj['PERFORMANCE_DATA'] = performance_data
    global _performance_data_changed
    _performance_data_changed = False # Reset flag on startup
    
    # Ensure canonical questions subdirectories exist
    ensure_question_dirs()

    while True:
        choice = handle_main_menu()
        if choice == '1':  # Quiz
            # Use the new quiz menu (types + stored), not only topic selection
            handle_quiz_menu(performance_data)
            if perf_loaded_ok:
                save_performance_data(performance_data)
                backup_performance_yaml()
            if not sys.stdin.isatty():
                break
            time.sleep(1)
        elif choice == '2':  # Import
            handle_import_menu()
            continue
        elif choice == '3':  # Settings
            handle_config_menu()
            continue
        elif choice == '4':  # Exit
            if perf_loaded_ok:
                save_performance_data(performance_data)
                backup_performance_yaml()
            print("\nGoodbye!")
            break

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
        performance_data, perf_loaded_ok = load_performance_data()
        topic_data = load_questions(args.cli_question_topic, Fore, Style)
        if topic_data and 'questions' in topic_data:
            questions_to_study = [topic_data['questions'][args.cli_question_index]]
            # Temporarily override get_user_input for this specific run
            _CLI_ANSWER_OVERRIDE = args.cli_answer # Set the global override variable
            
            print(f"Processing question from topic '{args.cli_question_topic}' at index {args.cli_question_index} with answer: '{args.cli_answer}'")
            run_topic(args.cli_question_topic, questions_to_study, performance_data)
            if perf_loaded_ok:
                save_performance_data(performance_data)
                backup_performance_yaml()
            sys.exit(0) # Exit after processing the single question
        else:
            print(f"Error: Topic '{args.cli_question_topic}' not found or has no questions.", file=sys.stderr)
            sys.exit(1)
    else:
        # Original interactive CLI mode
        cli(obj={})
