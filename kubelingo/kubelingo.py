import os
import random
import readline
import time
import yaml
import argparse
import google.generativeai as genai
import openai
from thefuzz import fuzz
import tempfile
import subprocess
import difflib
from colorama import Fore, Style, init as colorama_init



def colorize_ascii_art(ascii_art_string):
    """Applies a green and black pattern to the ASCII art string."""
    colors = [Fore.GREEN, Fore.WHITE] # Use only green and white
    
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

def handle_config_menu():
    """Handles the API key configuration menu."""
    while True:
        clear_screen()
        print(f"\n{Style.BRIGHT}{Fore.CYAN}--- API Key Configuration ---")
        # Load existing config to display current state
        config = dotenv_values(".env")
        gemini_key = config.get("GEMINI_API_KEY", "Not Set")
        openai_key = config.get("OPENAI_API_KEY", "Not Set")

        print(f"  {Style.BRIGHT}1.{Style.RESET_ALL} Set Gemini API Key (current: {Fore.YELLOW}{bool(gemini_key != 'Not Set')}{Style.RESET_ALL})")
        print(f"  {Style.BRIGHT}2.{Style.RESET_ALL} Set OpenAI API Key (current: {Fore.YELLOW}{bool(openai_key != 'Not Set')}{Style.RESET_ALL})")
        print(f"  {Style.BRIGHT}3.{Style.RESET_ALL} Back to Main Menu")
        
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
            break
        else:
            print("Invalid choice. Please try again.")
            time.sleep(1)

def _get_llm_model():
    """Determines which LLM to use based on available API keys and returns the appropriate model."""
    load_dotenv() # Load environment variables from .env file
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    openai_api_key = os.environ.get("OPENAI_API_KEY")

    if gemini_api_key:
        try:
            genai.configure(api_key=gemini_api_key)
            return "gemini", genai.GenerativeModel('gemini-1.5-flash-latest')
        except Exception as e:
            print(f"Warning: Could not configure Gemini model: {e}")
    
    if openai_api_key:
        try:
            # Assuming a default client for now, can be configured further if needed
            client = openai.OpenAI(api_key=openai_api_key)
            return "openai", client
        except Exception as e:
            print(f"Warning: Could not configure OpenAI model: {e}")
            
    return None, None

def get_llm_feedback(question, user_answer, solution):
    """Provides LLM-generated feedback on a user's answer."""
    llm_type, model = _get_llm_model()
    if not model:
        return "INFO: Set GEMINI_API_KEY or OPENAI_API_KEY for AI-powered feedback." # Return info if no LLM

    try:
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
        if llm_type == "gemini":
            response = model.generate_content(prompt)
            return response.text.strip()
        elif llm_type == "openai":
            response = model.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a Kubernetes expert providing feedback on a student's answer for a CKAD exam practice question."},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error getting feedback from LLM: {e}"

# get_llm_feedback function removed temporarily for debugging


def validate_manifest_with_llm(question_dict, user_manifest):
    """Validates a user-submitted manifest using the LLM."""
    llm_type, model = _get_llm_model()
    if not model:
        return {'correct': False, 'feedback': "INFO: Set GEMINI_API_KEY or OPENAI_API_KEY for AI-powered manifest validation."}

    solution_manifest = question_dict['solution']

    try:
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
        Your task is to determine if the student's manifest is functionally correct. The manifests do not need to be textually identical. Check for correct apiVersion, kind, metadata, and spec details.
        First, on a line by itself, write "CORRECT" or "INCORRECT".
        Then, on a new line, provide a brief, one or two-sentence explanation for your decision.
        '''
        if llm_type == "gemini":
            response = model.generate_content(prompt)
            lines = response.text.strip().split('\n')
        elif llm_type == "openai":
            response = model.chat.completions.create(
                model="gpt-3.5-turbo", # Or another suitable model
                messages=[
                    {"role": "system", "content": "You are a Kubernetes expert grading a student's YAML manifest for a CKAD exam practice question."},
                    {"role": "user", "content": prompt}
                ]
            )
            lines = response.choices[0].message.content.strip().split('\n')

        is_correct = lines[0].strip().upper() == "CORRECT"
        feedback = "\n".join(lines[1:]).strip()
        
        return {'correct': is_correct, 'feedback': feedback}
    except Exception as e:
        return {'correct': False, 'feedback': f"Error validating manifest with LLM: {e}"}


def handle_vim_edit(question):
    """Handles the user editing a manifest in Vim."""
    if 'solution' not in question:
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
        subprocess.run(['vim', '-c', "set tabstop=2 shiftwidth=2 expandtab", tmp_path], check=True)
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

    if not user_manifest.strip():
        print("Manifest is empty. Marking as incorrect.")
        return user_manifest, {'correct': False, 'feedback': 'The submitted manifest was empty.'}, False

    print(f"{Fore.CYAN}\nValidating manifest with AI...")
    result = validate_manifest_with_llm(question, user_manifest)
    return user_manifest, result, False

def generate_more_questions(topic, existing_question):
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
        elif llm_type == "openai":
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
        num_correct = len(stats.get('correct_questions', []))
        
        stats_str = ""
        if num_questions > 0:
            percent = (num_correct / num_questions) * 100
            stats_str = f" ({Fore.GREEN}{num_correct}{Style.RESET_ALL}/{Fore.RED}{num_questions}{Style.RESET_ALL} correct - {Fore.CYAN}{percent:.0f}%{Style.RESET_ALL})"

        print(f"  {Style.BRIGHT}{i+1}.{Style.RESET_ALL} {display_name} [{num_questions} questions]{stats_str}")
    
    if has_missed:
        print(f"  {Style.BRIGHT}c.{Style.RESET_ALL} Configure API Keys")
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
                return '_missed', num_to_study
            elif choice == 'c':
                handle_config_menu()
                continue # Go back to topic selection menu
            elif choice == 'q':
                print("\nGoodbye!")
                return None, None # Exit the main loop

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

                while True:
                    num_to_study_input = input(f"Enter number of questions to study (1-{total_questions}, or press Enter for all): ").strip().lower()
                    if num_to_study_input == 'all' or num_to_study_input == '':
                        num_to_study = total_questions
                        break
                    try:
                        num_to_study = int(num_to_study_input)
                        if 1 <= num_to_study <= total_questions:
                            break
                        else:
                            print(f"Please enter a number between 1 and {total_questions}, or 'all'.")
                    except ValueError:
                        print("Invalid input. Please enter a number or 'all'.")

                return selected_topic, num_to_study # Return both
            else:
                print("Invalid selection. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number or letter.")
        except (KeyboardInterrupt, EOFError):
            print("\n\nStudy session ended. Goodbye!")
            return None, None

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


def run_topic(topic, num_to_study, performance_data):
    """Loads and runs questions for a given topic."""
    questions = []
    session_topic_name = topic
    if topic == '_missed':
        questions = load_questions_from_list(MISSED_QUESTIONS_FILE)
        session_topic_name = "Missed Questions Review"
        if not questions:
            print("No missed questions to review. Well done!")
            return
        random.shuffle(questions) # Shuffle ALL missed questions first
    else:
        data = load_questions(topic)
        if not data or 'questions' not in data:
            print("No questions found in the specified topic file.")
            return
        questions = data['questions']
        random.shuffle(questions) # Also shuffle regular topic questions
    
    questions = questions[:num_to_study]

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
                    print("\nNo source available for this question.")
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
                print(f"{Fore.RED}\nQuestion skipped. Here's one possible solution:")
                solution_text = q.get('solutions', [q.get('solution', 'N/A')])[0]
                if '\n' in solution_text:
                    print(colorize_yaml(solution_text))
                else:
                    print(f"{Fore.YELLOW}{solution_text}")
                if q.get('source'):
                    print(f"\n{Style.BRIGHT}{Fore.BLUE}Source: {q['source']}{Style.RESET_ALL}")
                print(f"{Style.BRIGHT}{Fore.MAGENTA}\n--- AI Feedback ---")
                feedback = get_llm_feedback(q['question'], "skipped", solution_text)
                print(feedback)
                break # Exit inner loop, go to post-answer menu

            elif special_action == 'solution':
                is_correct = False # Viewing solution means not correct by own answer
                user_answer_graded = True
                print(f"{Style.BRIGHT}{Fore.YELLOW}\nSolution:")
                solution_text = q.get('solutions', [q.get('solution', 'N/A')])[0]
                if '\n' in solution_text:
                    print(colorize_yaml(solution_text))
                else:
                    print(f"{Fore.YELLOW}{solution_text}")
                if q.get('source'):
                    print(f"\n{Style.BRIGHT}{Fore.BLUE}Source: {q['source']}{Style.RESET_ALL}")
                break # Exit inner loop, go to post-answer menu

            elif special_action == 'vim':
                user_manifest, result, sys_error = handle_vim_edit(q)
                if not sys_error:
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

            elif user_commands:
                user_answer = "\n".join(user_commands)
                # Exact match check for 'solutions' (e.g., vim commands)
                if 'solutions' in q:
                    solution_list = [str(s).strip() for s in q['solutions']]
                    user_answer_processed = ' '.join(user_answer.split()).strip()
                    if user_answer_processed in solution_list:
                        is_correct = True
                        print(f"{Fore.GREEN}\nCorrect! Well done.")
                    else:
                        solution_text = solution_list[0]
                # Fuzzy match for single 'solution' (e.g., kubectl commands)
                elif 'solution' in q:
                    solution_text = q['solution'].strip()

                    # Process user's multi-line answer
                    user_answer_lines = user_answer.split('\n')
                    normalized_user_answer_lines = normalize_command(user_answer_lines)
                    normalized_user_answer_string = '\n'.join(normalized_user_answer_lines) # Join back for fuzzy matching

                    # Process solution's multi-line command
                    solution_lines = [line.strip() for line in solution_text.split('\n') if not line.strip().startswith('#')]
                    normalized_solution_lines = normalize_command(solution_lines)
                    normalized_solution_string = '\n'.join(normalized_solution_lines) # Join back for fuzzy matching
                    
                    if fuzz.ratio(normalized_user_answer_string, normalized_solution_string) > 95:
                        is_correct = True
                        print(f"{Fore.GREEN}\nCorrect! Well done.")
                    else:
                        solution_text = q['solution'].strip()
                
                if not is_correct:
                    print(f"{Fore.RED}\nNot quite. Here's one possible solution:")
                    if '\n' in solution_text:
                        print(colorize_yaml(solution_text))
                    else:
                        print(f"{Fore.YELLOW}{solution_text}")
                    if q.get('source'):
                        print(f"\n{Style.BRIGHT}{Fore.BLUE}Source: {q['source']}{Style.RESET_ALL}")
                    print(f"{Style.BRIGHT}{Fore.MAGENTA}\n--- AI Feedback ---")
                    feedback = get_llm_feedback(q['question'], normalized_user_answer_string, solution_text)
                    print(feedback)
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
            print("Options: [n]ext, [b]ack, [i]ssue, [g]enerate, [s]ource, [r]etry, [q]uit")
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
                        print("\n'googlesearch-python' is not installed. Cannot search for sources.")
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
        
        selected_topic, num_to_study = topic_info
        
        run_topic(selected_topic, num_to_study, performance_data)
        save_performance_data(performance_data)
        
        print("\nReturning to the main menu...")
        time.sleep(2)



if __name__ == "__main__":
    cli(obj={})
