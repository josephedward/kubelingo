import os
import requests
import random
import readline
import time
import yaml
import argparse
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
import openai
from openai import AuthenticationError
from thefuzz import fuzz
import tempfile
import subprocess
import difflib
from colorama import Fore, Style, init as colorama_init



def colorize_ascii_art(ascii_art_string):
    """Applies a green and cyan pattern to the ASCII art string."""
    colors = [Fore.GREEN, Fore.CYAN] # Use only green and cyan
    
    lines = ascii_art_string.splitlines()
    colored_lines = []
    
    # Find the center of the logo (approximately)
    max_width = max(len(line) for line in lines)
    max_height = len(lines)
    center_x = max_width // 2
    center_y = max_height // 2

    for y, line in enumerate(lines):
        colored_line = []
        for x, char in enumerate(line):
            if char == ' ':
                colored_line.append(' ')
            else:
                # Calculate distance from center (Manhattan distance for simplicity)
                distance = abs(x - center_x) + abs(y - center_y)
                
                # Alternate colors based on distance or a combination of x and y
                # This will create a concentric or diagonal pattern
                color_index = (distance // 2) % len(colors) # Adjust divisor for pattern density
                color = colors[color_index]
                colored_line.append(f"{color}{char}{Style.RESET_ALL}")
        colored_lines.append("".join(colored_line))
    return "\n".join(colored_lines)
from pygments import highlight
from pygments.lexers import YamlLexer
from pygments.formatters import TerminalFormatter
from dotenv import load_dotenv, dotenv_values, set_key
import click
import sys
import webbrowser
try:
    from googlesearch import search
except ImportError:
    search = None

ASCII_ART = r"""                                      bbbbbbbb
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

def ensure_user_data_dir():
    """Ensures the user_data directory exists."""
    os.makedirs(USER_DATA_DIR, exist_ok=True)

def load_performance_data():
    """Loads performance data from the user data directory."""
    ensure_user_data_dir()
    if not os.path.exists(PERFORMANCE_FILE):
        return {}
    with open(PERFORMANCE_FILE, 'r') as f:
        try:
            return yaml.safe_load(f) or {}
        except yaml.YAMLError:
            return {}

def save_performance_data(data):
    """Saves performance data."""
    ensure_user_data_dir()
    with open(PERFORMANCE_FILE, 'w') as f:
        yaml.dump(data, f)

def save_questions_to_topic_file(topic, questions_data):
    """Saves questions data to the specified topic YAML file."""
    ensure_user_data_dir() # This ensures user_data, but questions are in 'questions' dir
    topic_file = f"questions/{topic}.yaml"
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
    topic_file = f"questions/{topic}.yaml"
    
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

def clear_screen():
    """Clears the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def load_questions(topic):
    """Loads questions from a YAML file based on the topic."""
    file_path = f"questions/{topic}.yaml"
    if not os.path.exists(file_path):
        print(f"Error: Question file not found at {file_path}")
        available_topics = [f.replace('.yaml', '') for f in os.listdir('questions') if f.endswith('.yaml')]
        if available_topics:
            print("Available topics: " + ", ".join(available_topics))
        return None
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

def get_normalized_question_text(question_dict):
    return question_dict.get('question', '').strip().lower()

def handle_keys_menu():
    """Handles the API key configuration menu."""
    while True:
        clear_screen()
        print(f"\n{Style.BRIGHT}{Fore.CYAN}--- API Key Configuration ---")
        # Load existing config to display current state
        config = dotenv_values(".env")
        gemini_key = config.get("GEMINI_API_KEY", "Not Set")
        openai_key = config.get("OPENAI_API_KEY", "Not Set")
        openrouter_key = config.get("OPENROUTER_API_KEY", "Not Set")

        gemini_display = f"{Fore.GREEN}{gemini_key}{Style.RESET_ALL}" if gemini_key != 'Not Set' else f"{Fore.RED}Not Set{Style.RESET_ALL}"
        openai_display = f"{Fore.GREEN}{openai_key}{Style.RESET_ALL}" if openai_key != 'Not Set' else f"{Fore.RED}Not Set{Style.RESET_ALL}"
        openrouter_display = f"{Fore.GREEN}{openrouter_key}{Style.RESET_ALL}" if openrouter_key != 'Not Set' else f"{Fore.RED}Not Set{Style.RESET_ALL}"

        print(f"  {Style.BRIGHT}1.{Style.RESET_ALL} Set Gemini API Key (current: {gemini_display})")
        print(f"  {Style.BRIGHT}2.{Style.RESET_ALL} Set OpenAI API Key (current: {openai_display})")
        print(f"  {Style.BRIGHT}3.{Style.RESET_ALL} Set OpenRouter API Key (current: {openrouter_display})")
        print(f"  {Style.BRIGHT}4.{Style.RESET_ALL} Back to Configuration Menu")

        choice = input("Enter your choice: ").strip()

        if choice == '1':
            key = input("Enter your Gemini API Key: ").strip()
            if key:
                set_key(".env", "GEMINI_API_KEY", key)
                os.environ["GEMINI_API_KEY"] = key # Update current session
                print("\nGemini API Key saved.")
            else:
                print("\nNo key entered.")
            time.sleep(1)
        elif choice == '2':
            key = input("Enter your OpenAI API Key: ").strip()
            if key:
                set_key(".env", "OPENAI_API_KEY", key)
                os.environ["OPENAI_API_KEY"] = key # Update current session
                print("\nOpenAI API Key saved.")
            else:
                print("\nNo key entered.")
            time.sleep(1)
        elif choice == '3':
            key = input("Enter your OpenRouter API Key: ").strip()
            if key:
                set_key(".env", "OPENROUTER_API_KEY", key)
                os.environ["OPENROUTER_API_KEY"] = key # Update current session
                print("\nOpenRouter API Key saved.")
            else:
                print("\nNo key entered.")
            time.sleep(1)
        elif choice == '4':
            break
        else:
            print("Invalid choice. Please try again.")
            time.sleep(1)




def handle_validation_menu():
    """Handles the validation configuration menu."""
    while True:
        clear_screen()
        print(f"\n{Style.BRIGHT}{Fore.CYAN}--- Validation Configuration ---")
        config = dotenv_values(".env")

        # Get current settings, defaulting to 'True' (on) if not set
        kubectl_dry_run = config.get("KUBELINGO_VALIDATION_KUBECTL_DRY_RUN", "True")
        ai_feedback = config.get("KUBELINGO_VALIDATION_AI_FEEDBACK", "True")
        show_dry_run_logs = config.get("KUBELINGO_VALIDATION_SHOW_DRY_RUN_LOGS", "True")
        verbose_ai_feedback = config.get("KUBELINGO_VALIDATION_VERBOSE_AI_FEEDBACK", "True")

        # Display toggles
        def get_display(value):
            return f"{Fore.GREEN}On{Style.RESET_ALL}" if value == "True" else f"{Fore.RED}Off{Style.RESET_ALL}"

        print(f"  {Style.BRIGHT}1.{Style.RESET_ALL} Toggle kubectl dry-run (current: {get_display(kubectl_dry_run)})")
        print(f"  {Style.BRIGHT}2.{Style.RESET_ALL} Toggle AI feedback (current: {get_display(ai_feedback)})")
        print(f"  {Style.BRIGHT}3.{Style.RESET_ALL} Show kubectl dry-run logs (current: {get_display(show_dry_run_logs)})")
        print(f"  {Style.BRIGHT}4.{Style.RESET_ALL} Verbose AI feedback (current: {get_display(verbose_ai_feedback)})")
        print(f"  {Style.BRIGHT}5.{Style.RESET_ALL} Back to Configuration Menu")

        choice = input("Enter your choice: ").strip()

        if choice == '1':
            set_key(".env", "KUBELINGO_VALIDATION_KUBECTL_DRY_RUN", "False" if kubectl_dry_run == "True" else "True")
        elif choice == '2':
            set_key(".env", "KUBELINGO_VALIDATION_AI_FEEDBACK", "False" if ai_feedback == "True" else "True")
        elif choice == '3':
            set_key(".env", "KUBELINGO_VALIDATION_SHOW_DRY_RUN_LOGS", "False" if show_dry_run_logs == "True" else "True")
        elif choice == '4':
            set_key(".env", "KUBELINGO_VALIDATION_VERBOSE_AI_FEEDBACK", "False" if verbose_ai_feedback == "True" else "True")
        elif choice == '5':
            break
        else:
            print("Invalid choice. Please try again.")
            time.sleep(1)

def handle_config_menu():
    """Handles the main configuration menu."""
    while True:
        clear_screen()
        print(f"\n{Style.BRIGHT}{Fore.CYAN}--- Configuration Menu ---")
        print(f"  {Style.BRIGHT}1.{Style.RESET_ALL} API Keys")
        print(f"  {Style.BRIGHT}2.{Style.RESET_ALL} Validation Settings")
        print(f"  {Style.BRIGHT}3.{Style.RESET_ALL} Back to Main Menu")
        
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



def _get_llm_model(is_retry=False):
    """
    Determines which LLM to use based on available API keys and returns the appropriate model.
    If no valid keys are found, it prompts the user for action.
    """
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    openrouter_api_key = os.environ.get("OPENROUTER_API_KEY")

    current_llm_type = None
    current_model = None

    # Try OpenRouter first since it's free
    if openrouter_api_key and not current_model:
        try:
            # Test the OpenRouter API directly
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
            
            # Return openrouter config
            current_llm_type = "openrouter"
            current_model = {
                "api_key": openrouter_api_key,
                "headers": headers,
                "default_model": "deepseek/deepseek-r1-0528:free"
            }
            return current_llm_type, current_model
        except Exception as e:
            print(f"{Fore.RED}Error with OpenRouter API: {e}{Style.RESET_ALL}")
            os.environ.pop("OPENROUTER_API_KEY", None)
            set_key(".env", "OPENROUTER_API_KEY", "")

    # Try Gemini next
    if gemini_api_key and not current_model:
        try:
            genai.configure(api_key=gemini_api_key)
            # Attempt a small call to validate the key
            genai.GenerativeModel('gemini-1.5-flash-latest').generate_content("hello", stream=False)
            current_llm_type = "gemini"
            current_model = genai.GenerativeModel('gemini-1.5-flash-latest')
            return current_llm_type, current_model
        except google_exceptions.InvalidArgument:
            print(f"{Fore.RED}Invalid Gemini API Key. Please check your key.{Style.RESET_ALL}")
            # Clear the invalid key from environment and .env file
            os.environ.pop("GEMINI_API_KEY", None)
            set_key(".env", "GEMINI_API_KEY", "")
        except Exception as e:
            print(f"{Fore.RED}Error with Gemini API: {e}{Style.RESET_ALL}")
            os.environ.pop("GEMINI_API_KEY", None)
            set_key(".env", "GEMINI_API_KEY", "")

    # If Gemini failed or not set, try OpenAI
    if openai_api_key and not current_model:
        try:
            client = openai.OpenAI(api_key=openai_api_key)
            # Attempt a small call to validate the key
            client.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": "hello"}], max_tokens=5)
            current_llm_type = "openai"
            current_model = client
            return current_llm_type, current_model
        except AuthenticationError:
            print(f"{Fore.RED}Invalid OpenAI API Key. Please check your key.{Style.RESET_ALL}")
            # Clear the invalid key from environment and .env file
            os.environ.pop("OPENAI_API_KEY", None)
            set_key(".env", "OPENAI_API_KEY", "")
        except Exception as e:
            print(f"{Fore.RED}Error with OpenAI API: {e}{Style.RESET_ALL}")
            os.environ.pop("OPENAI_API_KEY", None)
            set_key(".env", "OPENAI_API_KEY", "")

    # If OpenAI failed or not set, try OpenRouter
    if openrouter_api_key and not current_model:
        try:
            # Test the OpenRouter API directly
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
            
            # Return openrouter config
            current_llm_type = "openrouter"
            current_model = {
                "api_key": openrouter_api_key,
                "headers": headers,
                "default_model": "deepseek/deepseek-r1-0528:free"
            }
            return current_llm_type, current_model
        except Exception as e:
            print(f"{Fore.RED}Error with OpenRouter API: {e}{Style.RESET_ALL}")
            os.environ.pop("OPENROUTER_API_KEY", None)
            set_key(".env", "OPENROUTER_API_KEY", "")

    # If no model could be configured
    if not current_model and not is_retry:
        print(f"\n{Fore.YELLOW}No valid LLM API key found (Gemini, OpenAI or OpenRouter). AI features will be disabled.{Style.RESET_ALL}")
        if click.confirm(f"{Fore.CYAN}Would you like to configure API keys now?{Style.RESET_ALL}", default=True):
            handle_config_menu()
            # After configuring, try to get the model again
            return _get_llm_model(is_retry=True)
        else:
            print(f"{Fore.YELLOW}Continuing without AI features.{Style.RESET_ALL}")
            return None, None
    elif not current_model and is_retry:
        print(f"{Fore.YELLOW}Still no valid LLM API key after configuration. Continuing without AI features.{Style.RESET_ALL}")
        return None, None
    
    return current_llm_type, current_model


def get_llm_feedback(question, user_answer, solution, verbose=True):
    """Provides LLM-generated feedback on a user's answer."""
    llm_type, model = _get_llm_model()
    if not model:
        return "INFO: Set GEMINI_API_KEY or OPENAI_API_KEY for AI-powered feedback." # Return info if no LLM

    if verbose:
        prompt = f'''
        You are a Kubernetes expert providing feedback on a student's answer for a CKAD exam practice question.
        The student was asked:
        ---
        Question: {question}
        ---
        The student provided this answer:
        ---
        Student Answer:\n{user_answer}
        ---
        The canonical solution is:
        ---
        Solution:\n{solution}
        ---
        Your task is to provide brief, constructive feedback on the student's answer. 
        - If the answer is correct, praise the student and briefly explain why it's a good answer.
        - If the answer is incorrect, explain the mistake clearly and concisely. 
        - If the student's answer is a reasonable alternative, acknowledge it.
        - Keep the feedback to 2-3 sentences.
        '''
    else:
        prompt = f'''
        You are a Kubernetes expert providing feedback on a student's answer for a CKAD exam practice question.
        The student was asked:
        ---
        Question: {question}
        ---
        The student provided this answer:
        ---
        Student Answer:\n{user_answer}
        ---
        The canonical solution is:
        ---
        Solution:\n{solution}
        ---
        Your task is to determine if the student's answer is correct. Respond with "Correct" or "Incorrect".
        '''

    if llm_type == "gemini":
        try:
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            return f"Error getting feedback from Gemini LLM: {e}"
    elif llm_type == "openai":
        try:
            resp = model.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a Kubernetes expert providing feedback on a student's answer for a CKAD exam practice question."},
                    {"role": "user", "content": prompt}
                ]
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            return f"Error getting feedback from OpenAI LLM: {e}"
    elif llm_type == "openrouter":
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=model["headers"],
                json={
                    "model": model["default_model"],
                    "messages": [
                        {"role": "system", "content": "You are a Kubernetes expert providing feedback on a student's answer for a CKAD exam practice question."},
                        {"role": "user", "content": prompt}
                    ]
                }
            )
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content'].strip()
        except Exception as e:
            return f"Error getting feedback from OpenRouter LLM: {e}"
    else:
        return "INFO: No LLM configured"



# get_llm_feedback function removed temporarily for debugging


def validate_manifest_with_llm(question_dict, user_manifest, verbose=True):
    """Validates a user-submitted manifest using the LLM."""
    llm_type, model = _get_llm_model()
    if not model:
        return {'correct': False, 'feedback': "INFO: Set GEMINI_API_KEY, OPENAI_API_KEY, or OPENROUTER_API_KEY for AI-powered manifest validation."}

    solution_manifest = question_dict['solution']

    # Compose prompt for validation
    if verbose:
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
        Your task is to determine if the student's manifest is functionally correct. The manifests do not need to be textually identical. Do not penalize differences in metadata.name or container names; focus on correct apiVersion, kind, relevant metadata fields (except names), and spec details.
        First, on a line by itself, write "CORRECT" or "INCORRECT".
        Then, on a new line, provide a brief, one or two-sentence explanation for your decision.
        '''
    else:
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
        Your task is to determine if the student's manifest is functionally correct. The manifests do not need to be textually identical. Do not penalize differences in metadata.name or container names; focus on correct apiVersion, kind, relevant metadata fields (except names), and spec details.
        Respond with "CORRECT" or "INCORRECT".
        '''
    # Use only the configured LLM
    if llm_type == "gemini":
        try:
            response = model.generate_content(prompt)
            text = response.text.strip()
        except Exception as e:
            return {'correct': False, 'feedback': f"Error validating manifest with Gemini LLM: {e}"}
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
            return {'correct': False, 'feedback': f"Error validating manifest with OpenAI LLM: {e}"}
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
            return {'correct': False, 'feedback': f"Error validating manifest with OpenRouter LLM: {e}"}
    else:
        return {'correct': False, 'feedback': "No LLM configured"}
    lines = text.split('\n')
    is_correct = lines[0].strip().upper() == "CORRECT"
    feedback = "\n".join(lines[1:]).strip()
    return {'correct': is_correct, 'feedback': feedback}


def handle_vim_edit(question, verbose_ai_feedback=True):
    """Handles the user editing a manifest in Vim."""
    # Determine the canonical solution manifest
    if 'solutions' in question and isinstance(question['solutions'], list) and question['solutions']:
        sol_manifest = question['solutions'][0]
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

    if not cleaned_user_manifest.strip():
        print("Manifest is empty. Marking as incorrect.")
        return user_manifest, {'correct': False, 'feedback': 'The submitted manifest was empty.'}, False

    print(f"{Fore.CYAN}\nValidating manifest with kubectl dry-run...")
    dry_run_success, user_dry_run_feedback, ai_dry_run_feedback = validate_manifest_with_kubectl_dry_run(cleaned_user_manifest)
    print(user_dry_run_feedback)

    if not dry_run_success:
        result = {'correct': False, 'feedback': ai_dry_run_feedback}
    else:
        result = {'correct': True, 'feedback': ai_dry_run_feedback}
    
    return user_manifest, result, False


def validate_manifest_with_kubectl_dry_run(manifest_content):
    # Check if it's likely a Kubernetes YAML manifest
    if not manifest_content.strip().startswith(('apiVersion:', 'kind:')):
        return False, f"{Fore.YELLOW}Skipping kubectl dry-run: Not a Kubernetes YAML manifest.{Style.RESET_ALL}", "Skipped: Not a Kubernetes YAML manifest."

    with tempfile.NamedTemporaryFile(mode='w+', suffix=".yaml", delete=False) as tmp_file:
        tmp_file.write(manifest_content)
        tmp_file.flush()
        tmp_path = tmp_file.name

    try:
        # Use --dry-run=client to validate syntax without connecting to a cluster
        # Use --validate=true for schema validation
        cmd = ["kubectl", "apply", "--dry-run=client", "--validate=true", "-f", tmp_path]
        process = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        os.unlink(tmp_path) # Clean up the temporary file

        ai_feedback = process.stdout.strip() + "\n" + process.stderr.strip()

        if process.returncode == 0:
            return True, f"{Fore.GREEN}kubectl dry-run successful!{Style.RESET_ALL}", ai_feedback
        else:
            return False, f"{Fore.RED}kubectl dry-run failed. Please check your manifest.{Style.RESET_ALL}", ai_feedback
    except FileNotFoundError:
        os.unlink(tmp_path) # Clean up even if kubectl not found
        return False, f"{Fore.RED}Error: 'kubectl' command not found. Please ensure kubectl is installed and in your system's PATH to enable dry-run validation.{Style.RESET_ALL}", "kubectl not found"
    except Exception as e:
        os.unlink(tmp_path) # Clean up on other exceptions
        return False, f"{Fore.RED}An unexpected error occurred during kubectl dry-run: {e}{Style.RESET_ALL}\n", str(e)

def generate_more_questions(topic, existing_question):
    """Generates more questions based on an existing one."""
    llm_type, model = _get_llm_model()
    if not model:
        print("\nINFO: Set GEMINI_API_KEY, OPENAI_API_KEY, or OPENROUTER_API_KEY environment variables to generate new questions.")
        return None

    print("\nGenerating a new question... this might take a moment.")
    try:
        question_type = random.choice(['command', 'manifest'])
        prompt = f'''
        You are a Kubernetes expert creating questions for a CKAD study guide.
        Based on the following example question about '{topic}', please generate one new, distinct but related question.

        Example Question:
        ---
        {yaml.safe_dump({'questions': [existing_question]})}
        ---

        Your new question should be a {question_type}-based question.
        - If it is a 'command' question, the solution should be a single or multi-line shell command (e.g., kubectl).
        - If it is a 'manifest' question, the solution should be a complete YAML manifest and the question should be phrased to ask for a manifest.

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
        
        # Handle 'k' alias for 'kubectl'
        if words[0] == 'k':
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
        normalized_command_parts = main_command + positional_args + grouped_flags
        normalized_lines.append(' '.join(normalized_command_parts))
    return normalized_lines

def list_and_select_topic(performance_data):

    """Lists available topics and prompts the user to select one."""
    ensure_user_data_dir()
    available_topics = sorted([f.replace('.yaml', '') for f in os.listdir('questions') if f.endswith('.yaml')])
    
    has_missed = os.path.exists(MISSED_QUESTIONS_FILE) and os.path.getsize(MISSED_QUESTIONS_FILE) > 0

    if not available_topics and not has_missed:
        print("No question topics found and no missed questions to review.")
        return None

    print(f"\n{Style.BRIGHT}{Fore.CYAN}Please select a topic to study:{Style.RESET_ALL}")
    if has_missed:
        missed_questions_count = len(load_questions_from_list(MISSED_QUESTIONS_FILE))
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

        print(f"  {Style.BRIGHT}{i+1}.{Style.RESET_ALL} {display_name} [{num_questions} questions]{stats_str}")
    
    if has_missed:
        print(f"  {Style.BRIGHT}c.{Style.RESET_ALL} Configuration Menu")
        
        print(f"  {Style.BRIGHT}q.{Style.RESET_ALL} Quit")
    

    while True:
        try:
            prompt = f"\nEnter a number (0-{len(available_topics)}), 'c', or 'q': "
            choice = input(prompt).lower()

            if choice == '0' and has_missed:
                missed_questions_count = len(load_questions_from_list(MISSED_QUESTIONS_FILE))
                if missed_questions_count == 0:
                    print("No missed questions to review. Well done!")
                    continue # Go back to topic selection

                while True:
                    num_to_study_input = input(f"Enter number of missed questions to study (1-{missed_questions_count}, or press Enter for all): ").strip().lower()
                    if num_to_study_input == 'all' or num_to_study_input == '':
                        num_to_study = missed_questions_count
                        break
                    try:
                        num_to_study = int(num_to_study_input)
                        if 1 <= num_to_study <= missed_questions_count:
                            break
                        else:
                            print(f"Please enter a number between 1 and {missed_questions_count}, or 'all'.")
                    except ValueError:
                        print("Invalid input. Please enter a number or 'all'.")
                missed_questions = load_questions_from_list(MISSED_QUESTIONS_FILE)
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

                incomplete_questions = [
                    q for q in all_questions 
                    if get_normalized_question_text(q) not in correct_questions_normalized
                ]
                num_incomplete = len(incomplete_questions)

                questions_to_study_list = all_questions # Default to all questions
                current_total_questions = total_questions

                while True:
                    prompt_suffix = ""
                    if num_incomplete > 0:
                        prompt_suffix = f", 'i' for incomplete ({num_incomplete})"
                    
                    num_to_study_input = input(f"Enter number of questions to study (1-{current_total_questions}{prompt_suffix}, or press Enter for all): ").strip().lower()
                    
                    if num_to_study_input == 'all' or num_to_study_input == '':
                        num_to_study = current_total_questions
                        break
                    elif num_to_study_input == 'i':
                        if num_incomplete == 0:
                            print(f"All questions in '{selected_topic.replace('_', ' ').title()}' have been answered correctly. Well done!")
                            continue # Stay in this loop, let user choose again
                        else:
                            questions_to_study_list = incomplete_questions
                            current_total_questions = num_incomplete
                            print(f"Now selecting from {num_incomplete} incomplete questions.")
                            # Re-prompt with the new total
                            continue
                    try:
                        num_to_study = int(num_to_study_input)
                        if 1 <= num_to_study <= current_total_questions:
                            break
                        else:
                            print(f"Please enter a number between 1 and {current_total_questions}, or 'all'.")
                    except ValueError:
                        print("Invalid input. Please enter a number or 'all'.")

                return selected_topic, num_to_study, questions_to_study_list # Return both
            else:
                print("Invalid selection. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number or letter.")
        except (KeyboardInterrupt, EOFError):
            print("\n\nStudy session ended. Goodbye!")
            return None, None, None

def get_user_input():
    """Collects user commands until a terminating keyword is entered."""
    user_commands = []
    special_action = None
    while True:
        try:
            cmd = input(f"{Style.BRIGHT}{Fore.BLUE}> {Style.RESET_ALL}")
        except EOFError:
            special_action = 'skip'
            break
        
        cmd_lower = cmd.strip().lower()

        if cmd_lower == 'done':
            break
        elif cmd_lower == 'clear':
            if user_commands:
                user_commands.clear()
                print(f"{Fore.YELLOW}(Input cleared)")
            else:
                print(f"{Fore.YELLOW}(No input to clear)")
        elif cmd_lower in ['solution', 'issue', 'generate', 'skip', 'vim', 'source', 'menu']:
            special_action = cmd_lower
            break
        elif cmd.strip():
            user_commands.append(cmd.strip())
    return user_commands, special_action


def run_topic(topic, num_to_study, performance_data, questions_to_study):
    """Loads and runs questions for a given topic."""
    config = dotenv_values(".env")
    kubectl_dry_run_enabled = config.get("KUBELINGO_VALIDATION_KUBECTL_DRY_RUN", "True") == "True"
    ai_feedback_enabled = config.get("KUBELINGO_VALIDATION_AI_FEEDBACK", "True") == "True"
    show_dry_run_logs = config.get("KUBELINGO_VALIDATION_SHOW_DRY_RUN_LOGS", "True") == "True"
    verbose_ai_feedback = config.get("KUBELINGO_VALIDATION_VERBOSE_AI_FEEDBACK", "True") == "True"

    session_topic_name = topic
    questions = questions_to_study # Use the passed list directly

    # If it's a missed questions review, the list is already shuffled and limited by num_to_study
    # If it's a regular topic or incomplete questions, we need to shuffle and limit here.
    if topic != '_missed':
        random.shuffle(questions)
        # If num_to_study > 0, limit the number of questions; otherwise, use all
        if num_to_study > 0:
            questions = questions[:num_to_study]
    else:
        # For missed questions, questions_to_study is already shuffled and limited
        # by the list_and_select_topic function.
        pass

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
    while question_index < len(questions):
        q = questions[question_index]
        # Determine canonical solution manifest for diff/display
        if 'solution' in q:
            sol_manifest = q['solution']
        elif 'solutions' in q and isinstance(q['solutions'], list) and q['solutions']:
            sol_manifest = q['solutions'][0]
        else:
            sol_manifest = None
        is_correct = False # Reset for each question attempt
        user_answer_graded = False # Flag to indicate if an answer was submitted and graded

        # For saving to lists, use original topic if reviewing, otherwise current topic
        question_topic_context = q.get('original_topic', topic)

        # --- Inner loop for the current question ---
        # This loop allows special actions (like 'source', 'issue')
        # to be handled without immediately advancing to the next question.
        while True:
            clear_screen()
            print(f"{Style.BRIGHT}{Fore.CYAN}Question {question_index + 1}/{len(questions)} (Topic: {question_topic_context})")
            print(f"{Fore.CYAN}{'-' * 40}")
            print(q['question'])
            print(f"{Fore.CYAN}{'-' * 40}")
            print("Enter command(s). Type 'done' to check. Special commands: 'solution', 'vim', 'clear', 'menu'.")

            user_commands, special_action = get_user_input()

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
                new_q = generate_more_questions(question_topic_context, q)
                if new_q:
                    questions.insert(question_index + 1, new_q)
                    # Save the updated questions list to the topic file
                    # Only save if it's not a missed questions review session
                    if topic != '_missed':
                        save_questions_to_topic_file(question_topic_context, [q for q in questions if q.get('original_topic', topic) == question_topic_context])
                        print(f"Added new question to '{question_topic_context}.yaml'.")
                    else:
                        print("A new question has been added to this session (not saved to file in review mode).")
                input("Press Enter to continue...")
                continue # Re-display the same question prompt (or the new one if it's next)

            # --- Process actions that involve grading or showing solution ---
            solution_text = "" # Initialize solution_text for scope

            if special_action == 'skip':
                is_correct = False
                user_answer_graded = True
                print(f"{Fore.RED}Question skipped. Here's one possible solution:")
                solution_text = q.get('solutions', [q.get('solution', 'N/A')])[0]
                # Print solution in YAML if it's a mapping/sequence or contains newlines
                if isinstance(solution_text, (dict, list)):
                    dumped = yaml.safe_dump(solution_text, default_flow_style=False, sort_keys=False, indent=2)
                    print(colorize_yaml(dumped))
                elif '\n' in solution_text:
                    print(colorize_yaml(solution_text))
                else:
                    print(f"{Fore.YELLOW}{solution_text}")
                if q.get('source'):
                    print(f"\n{Style.BRIGHT}{Fore.BLUE}Source: {q['source']}{Style.RESET_ALL}")
                if ai_feedback_enabled:
                    print(f"{Style.BRIGHT}{Fore.MAGENTA}\n--- AI Feedback ---")
                    feedback = get_llm_feedback(q['question'], "skipped", solution_text, verbose_ai_feedback)
                    print(feedback)
                break # Exit inner loop, go to post-answer menu

            elif special_action == 'solution':
                is_correct = False # Viewing solution means not correct by own answer
                user_answer_graded = True
                print(f"{Style.BRIGHT}{Fore.YELLOW}\nSolution:")
                solution_text = q.get('solutions', [q.get('solution', 'N/A')])[0]
                if isinstance(solution_text, (dict, list)):
                    dumped = yaml.safe_dump(solution_text, default_flow_style=False, sort_keys=False, indent=2)
                    print(colorize_yaml(dumped))
                elif '\n' in solution_text:
                    print(colorize_yaml(solution_text))
                else:
                    print(f"{Fore.YELLOW}{solution_text}")
                if q.get('source'):
                    print(f"\n{Style.BRIGHT}{Fore.BLUE}Source: {q['source']}{Style.RESET_ALL}")
                break # Exit inner loop, go to post-answer menu

            elif special_action == 'vim':
                user_manifest, result, sys_error = handle_vim_edit(q, verbose_ai_feedback)
                if result is None: # Added check for None result
                    continue # Re-display the question prompt
                # If result is not a dict, treat as a message and display
                if not isinstance(result, dict):
                    print(result)
                    user_answer_graded = True
                    break
                if not sys_error:
                    if ai_feedback_enabled:
                        print(f"{Style.BRIGHT}{Fore.MAGENTA}\n--- AI Feedback ---")
                        print(result['feedback'])
                    is_correct = result['correct']
                    if not is_correct:
                        # Use canonical solution manifest
                        if isinstance(sol_manifest, (dict, list)):
                            sol_text = yaml.safe_dump(sol_manifest, default_flow_style=False, sort_keys=False, indent=2)
                        else:
                            sol_text = sol_manifest or ''
                        show_diff(user_manifest, sol_text)
                        print(f"{Fore.RED}\nThat wasn't quite right. Here is the solution:")
                        print(colorize_yaml(sol_text))
                    else:
                        print(f"{Fore.GREEN}\nCorrect! Well done.")
                    if q.get('source'):
                        print(f"\n{Style.BRIGHT}{Fore.BLUE}Source: {q['source']}{Style.RESET_ALL}")
                user_answer_graded = True
                break # Exit inner loop, go to post-answer menu

            elif 'manifest' in q.get('question', '').lower():
                # Automatically use vim for manifest questions
                user_manifest, result, sys_error = handle_vim_edit(q, verbose_ai_feedback)
                if result is None: # Added check for None result
                    continue # Re-display the question prompt
                # If result is not a dict, treat as a message and display
                if not isinstance(result, dict):
                    print(result)
                    user_answer_graded = True
                    break
                if not sys_error:
                    if ai_feedback_enabled:
                        print(f"{Style.BRIGHT}{Fore.MAGENTA}\n--- AI Feedback ---")
                        print(result['feedback'])
                    is_correct = result['correct']
                    if not is_correct:
                        show_diff(user_manifest, q['solution'])
                        print(f"{Fore.RED}\nThat wasn't quite right. Here is the solution:")
                        print(colorize_yaml(q['solution']))
                    else:
                        print(f"{Fore.GREEN}\nCorrect! Well done.")
                    if q.get('source'):
                        print(f"\n{Style.BRIGHT}{Fore.BLUE}Source: {q['source']}{Style.RESET_ALL}")
                user_answer_graded = True
                break # Exit inner loop, go to post-answer menu
            
            else: # User typed 'done' without commands, or empty input
                print("Please enter a command or a special action.")
                continue # Re-display the same question prompt



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
            else:
                # If the question was previously answered correctly, remove it.
                normalized_question_text = get_normalized_question_text(q)
                if normalized_question_text in topic_perf['correct_questions']:
                    topic_perf['correct_questions'].remove(normalized_question_text)
                save_question_to_list(MISSED_QUESTIONS_FILE, q, question_topic_context)

        if topic != '_missed':
                performance_data[topic] = topic_perf
                save_performance_data(performance_data)

        # Post-answer menu loop
        while True:
            print(f"\n{Style.BRIGHT}{Fore.CYAN}--- Question Completed ---")
            print("Options: [n]ext, [b]ack, [i]ssue, [g]enerate, [s]ource, [r]etry, [c]onfigure, [q]uit")
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
            elif post_action == 'g':
                new_q = generate_more_questions(question_topic_context, q)
                if new_q:
                    questions.insert(question_index + 1, new_q)
                    # Save the updated questions list to the topic file
                    # Only save if it's not a missed questions review session
                    if topic != '_missed':
                        save_questions_to_topic_file(question_topic_context, [q for q in questions if q.get('original_topic', topic) == question_topic_context])
                        print(f"Added new question to '{question_topic_context}.yaml'.")
                    else:
                        print("A new question has been added to this session (not saved to file in review mode).")
                input("Press Enter to continue...")
                continue  # Re-display the same question prompt
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
                    for idx, url in enumerate(results, 1):
                        marker = ' (default)' if (idx-1) == default_idx else ''
                        print(f"  {idx}. {url}{marker}")
                    # Prompt user for action
                    while True:
                        sel = input("Enter=assign default, number=assign that, 'o N'=open N, 's'=skip: ").strip().lower()
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
                                file_path = f"questions/{topic}.yaml"
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
                user_commands.clear() # This needs to be handled by get_user_input or similar
                print("\nRetrying the current question...")
                break # Exit post-answer loop, re-enter inner loop for current question
            elif post_action == 'q':
                # Exit the entire run_topic loop
                return # Return to main menu
            else:
                print("Invalid option. Please choose 'n', 'b', 'i', 'g', 's', 'r', or 'q'.")

    

    clear_screen()
    print(f"{Style.BRIGHT}{Fore.GREEN}Great job! You've completed all questions for this topic.")

def validate_kubectl_command_dry_run(command_string):
    # Only attempt dry-run for commands that typically create/modify resources
    # and can output YAML for client-side validation.
    # This is a heuristic and might not cover all cases.
    if not any(cmd in command_string for cmd in ["create", "run", "apply", "set", "edit"]):
        return True, f"{Fore.YELLOW}Skipping kubectl dry-run: Command type not typically dry-runnable client-side.{Style.RESET_ALL}", "Skipped: Command type not typically dry-runnable client-side."

    # Attempt to append --dry-run=client -o yaml
    # Be careful not to duplicate if already present
    modified_command = command_string
    if "--dry-run" not in modified_command:
        modified_command += " --dry-run=client"
    if "-o" not in modified_command and "--output" not in modified_command:
        modified_command += " -o yaml"

    try:
        cmd = modified_command.split()
        process = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        ai_feedback = process.stdout.strip() + "\n" + process.stderr.strip()

        if process.returncode == 0:
            # If dry-run is successful, check if the output is valid YAML
            try:
                yaml.safe_load(process.stdout)
                return True, f"{Fore.GREEN}kubectl dry-run successful!{Style.RESET_ALL}", ai_feedback
            except yaml.YAMLError:
                return False, f"{Fore.RED}kubectl dry-run produced invalid YAML. Please check your command syntax.{Style.RESET_ALL}", ai_feedback
        else:
            return False, f"{Fore.RED}kubectl dry-run failed. Please check your command syntax.{Style.RESET_ALL}", ai_feedback
    except FileNotFoundError:
        return False, f"{Fore.RED}Error: 'kubectl' command not found. Please ensure kubectl is installed and in your system's PATH to enable dry-run validation.{Style.RESET_ALL}", "kubectl not found"
    except Exception as e:
        return False, f"{Fore.RED}An unexpected error occurred during kubectl dry-run: {e}{Style.RESET_ALL}", str(e)

        

    

    clear_screen()
    print(f"{Style.BRIGHT}{Fore.GREEN}Great job! You've completed all questions for this topic.")

# --- Source Management Commands ---
def get_source_from_consolidated(item):
    metadata = item.get('metadata', {}) or {}
    for key in ('links', 'source', 'citation'):
        if key in metadata and metadata[key]:
            val = metadata[key]
            return val[0] if isinstance(val, list) else val
    return None

def cmd_add_sources(consolidated_file, questions_dir='questions'):
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

def cmd_check_sources(questions_dir='questions'):
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

def cmd_interactive_sources(questions_dir='questions', auto_approve=False):
    """Interactively search and assign sources to questions."""
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
            for i, url in enumerate(results, start=1):
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
        cmd_add_sources(consolidated, questions_dir='questions')
        return
    if check_sources:
        cmd_check_sources(questions_dir='questions')
        return
    if interactive_sources:
        cmd_interactive_sources(questions_dir='questions', auto_approve=auto_approve)
        return
    print(colorize_ascii_art(ASCII_ART))
    colorama_init(autoreset=True)
    if not os.path.exists('questions'):
        os.makedirs('questions')
    ctx.ensure_object(dict)
    ctx.obj['PERFORMANCE_DATA'] = load_performance_data()

    performance_data = ctx.obj['PERFORMANCE_DATA']
    
    while True:
        topic_info = list_and_select_topic(performance_data)
        if topic_info is None or topic_info[0] is None:
            break
        
        selected_topic, num_to_study, questions_to_study = topic_info
        
        run_topic(selected_topic, num_to_study, performance_data, questions_to_study)
        save_performance_data(performance_data)
        
        time.sleep(2)



if __name__ == "__main__":
    cli(obj={})
