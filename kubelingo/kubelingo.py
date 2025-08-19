import os
import random
import readline
import time
import yaml
import argparse
import google.generativeai as genai
from thefuzz import fuzz
import tempfile
import subprocess
import difflib
from colorama import Fore, Style, init as colorama_init
from pygments import highlight
from pygments.lexers import YamlLexer
from pygments.formatters import TerminalFormatter
from dotenv import load_dotenv, dotenv_values, set_key
import click

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
KK::::::K  K:::::KKKu:::::uuuu:::::u   b:::::b     b:::::be:::::::e            l::::l  i::::i   n::::n    n::::ng::::::g    g:::::g o::::o     o::::o
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

def get_llm_feedback(question, user_answer, correct_solution):
    """Gets feedback from Gemini on the user's answer."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        # Return a helpful message if the key is not set.
        return "INFO: Set the GEMINI_API_KEY environment variable to get AI-powered feedback."

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"""
        You are a Kubernetes expert helping a student study for the CKAD exam.
        The student was asked the following question:
        ---
        Question: {question}
        ---
        The student provided this answer:
        ---
        Answer: {user_answer}
        ---
        The correct solution is:
        ---
        Solution: {correct_solution}
        ---
        The student's answer was marked as incorrect.
        Briefly explain why the student's answer is wrong and what they should do to fix it.
        Focus on the differences between the student's answer and the correct solution.
        Be concise and encouraging. Do not just repeat the solution. Your feedback should be 2-3 sentences.
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error getting feedback from LLM: {e}"

def validate_manifest_with_llm(question_dict, user_manifest):
    """Validates a user-submitted manifest using the LLM."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {'correct': False, 'feedback': "INFO: Set GEMINI_API_KEY for AI-powered manifest validation."}

    solution_manifest = question_dict['solution']

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"""
        You are a Kubernetes expert grading a student's YAML manifest for a CKAD exam practice question.
        The student was asked:
        ---
        Question: {question_dict['question']}
        ---
        The student provided this manifest:
        ---
        Student's Manifest:\n{user_manifest}
        ---
        The canonical solution is:
        ---
        Solution Manifest:\n{solution_manifest}
        ---
        Your task is to determine if the student's manifest is functionally correct. The manifests do not need to be textually identical. Check for correct apiVersion, kind, metadata, and spec details.
        First, on a line by itself, write "CORRECT" or "INCORRECT".
        Then, on a new line, provide a brief, one or two-sentence explanation for your decision.
        """
        response = model.generate_content(prompt)
        lines = response.text.strip().split('\n')
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
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("\nINFO: Set the GEMINI_API_KEY environment variable to generate new questions.")
        return None

    print("\nGenerating a new question... this might take a moment.")
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        question_type = random.choice(['command', 'manifest'])
        prompt = f"""
        You are a Kubernetes expert creating questions for a CKAD study guide.
        Based on the following example question about '{topic}', please generate one new, distinct but related question.

        Example Question:
        ---
        {yaml.dump({'questions': [existing_question]})}
        ---

        Your new question should be a {question_type}-based question.
        - If it's a 'command' question, the solution should be a single or multi-line shell command (e.g., kubectl).
        - If it's a 'manifest' question, the solution should be a complete YAML manifest and the question should be phrased to ask for a manifest.

        The new question should be in the same topic area but test a slightly different aspect or use different parameters.
        Provide the output in valid YAML format, as a single item in a 'questions' list.
        The output must include a 'source' field with a valid URL pointing to the official Kubernetes documentation or a highly reputable source that justifies the answer.
        The solution must be correct and working.

        Example for a manifest question:
        questions:
          - question: "Create a manifest for a Pod named 'new-pod'வுகளை"
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
        """
        response = model.generate_content(prompt)
        # Clean the response to only get the YAML part
        cleaned_response = response.text.strip()
        if cleaned_response.startswith('```yaml'):
            cleaned_response = cleaned_response[7:]
        if cleaned_response.endswith('```'):
            cleaned_response = cleaned_response[:-3]

        new_question_data = yaml.safe_load(cleaned_response)
        
        if new_question_data and 'questions' in new_question_data and new_question_data['questions']:
            new_q = new_question_data['questions'][0]
            print("\nNew question generated!")
            
            topic_file = f"questions/{topic}.yaml"
            if os.path.exists(topic_file):
                with open(topic_file, 'r+') as f:
                    data = yaml.safe_load(f) or {'questions': []}
                    data['questions'].append(new_q)
                    f.seek(0)
                    yaml.dump(data, f)
                    f.truncate()
                print(f"Added new question to '{topic}.yaml'.")
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
    """Normalizes a list of kubectl command strings by expanding aliases."""
    normalized_lines = []
    for command in command_lines:
        # Normalize whitespace and split
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
                
        normalized_lines.append(' '.join(words))
    return normalized_lines

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

def list_and_select_topic(performance_data):


    """Lists available topics and prompts the user to select one."""
    ensure_user_data_dir()
    available_topics = sorted([f.replace('.yaml', '') for f in os.listdir('questions') if f.endswith('.yaml')])
    
    has_missed = os.path.exists(MISSED_QUESTIONS_FILE) and os.path.getsize(MISSED_QUESTIONS_FILE) > 0

    if not available_topics and not has_missed:
        print("No question topics found and no missed questions to review.")
        return None

    print(f"\n{Style.BRIGHT}{Fore.CYAN}Please select a topic to study:{Style.RESET_ALL}")
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
        missed_questions_count = len(load_questions_from_list(MISSED_QUESTIONS_FILE))
        print(f"\n{Style.BRIGHT}{Fore.CYAN}Or, select a special action:{Style.RESET_ALL}")
        print(f"  {Style.BRIGHT}0.{Style.RESET_ALL} Review Missed Questions [{missed_questions_count}]")
        print(f"  {Style.BRIGHT}c.{Style.RESET_ALL} Configure API Keys")
        print(f"  {Style.BRIGHT}q.{Style.RESET_ALL} Quit")
    
    while True:
        try:
            prompt = f"\nEnter a number (1-{len(available_topics)}) or '0', 'c', 'q': "
            choice = input(prompt).lower()

            if choice == '0' and has_missed:
                missed_questions_count = len(load_questions_from_list(MISSED_QUESTIONS_FILE))
                if missed_questions_count == 0:
                    print("No missed questions to review. Well done!")
                    continue # Go back to topic selection

                while True:
                    num_to_study_input = input(f"Enter number of missed questions to study (1-{missed_questions_count}, or 'all'): ").strip().lower()
                    if num_to_study_input == 'all':
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
                    num_to_study_input = input(f"Enter number of questions to study (1-{total_questions}, or 'all'): ").strip().lower()
                    if num_to_study_input == 'all':
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
    else:
        data = load_questions(topic)
        if not data or 'questions' not in data:
            print("No questions found in the specified topic file.")
            return
        questions = data['questions']
    
    questions = questions[:num_to_study]

    random.shuffle(questions)

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
                if q.get('source'):
                    try:
                        import webbrowser
                        print(f"Opening source in your browser: {q['source']}")
                        webbrowser.open(q['source'])
                    except Exception as e:
                        print(f"Could not open browser: {e}")
                else:
                    print("\nNo source available for this question. Let's find one.")
                    if search is None:
                        print("  'googlesearch-python' is not installed. Cannot search for sources.")
                    else:
                        while True:
                            search_query = input("  Enter search query (e.g., 'kubernetes <question text>'): ").strip()
                            if not search_query:
                                print("  Search query cannot be empty. Skipping source search.")
                                break

                            print("  Searching for sources...")
                            search_results = []
                            try:
                                search_results = [url for url in search(search_query, num_results=5)]
                            except Exception as e:
                                print(f"  Error during search: {e}")

                            if search_results:
                                print("  Search results:")
                                for j, url in enumerate(search_results):
                                    print(f"    {j+1}. {url}")

                                while True:
                                    select_action = input("    Select a number to use, [o]pen in browser (first result), [s]earch again, [m]anual, [sk]ip, [q]quit: ").strip().lower()
                                    if select_action == 'o':
                                        try:
                                            webbrowser.open(search_results[0])
                                        except Exception as e:
                                            print(f"    Could not open browser: {e}")
                                        continue
                                    elif select_action == 's':
                                        break # Break inner loop to search again
                                    elif select_action == 'm':
                                        manual_source = input("    Enter source URL manually: ").strip()
                                        if manual_source:
                                            q['source'] = manual_source
                                            print(f"    Source added: {q['source']}")
                                            break # Source added
                                        else:
                                            print("    Manual source entry cancelled.")
                                            continue # Go back to search/manual options
                                    elif select_action == 'sk':
                                        print("    Skipping source selection for this question.")
                                        break # Skip this question
                                    elif select_action == 'q':
                                        sys.exit("User quit.") # Exit script
                                    try:
                                        selected_index = int(select_action) - 1
                                        if 0 <= selected_index < len(search_results):
                                            q['source'] = search_results[selected_index]
                                            print(f"    Source added: {q['source']}")
                                            break # Source added
                                        else:
                                            print("    Invalid selection.")
                                    except ValueError:
                                        print("    Invalid input.")
                            else:
                                print("  No search results found.")
                                break # Exit search loop
                input("Press Enter to continue...")
                continue # Re-display the same question prompt

            if special_action == 'generate':
                new_q = generate_more_questions(question_topic_context, q)
                if new_q:
                    questions.insert(question_index + 1, new_q)
                    print("A new question has been added to this session.")
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
                    print("A new question has been added to this session.")
                input("Press Enter to continue...")
                continue # Re-display the same question prompt (or the new one if it's next)
            elif post_action == 's':
                if q.get('source'):
                    try:
                        import webbrowser
                        print(f"Opening source in your browser: {q['source']}")
                        webbrowser.open(q['source'])
                    except Exception as e:
                        print(f"Could not open browser: {e}")
                else:
                    print("\nNo source available for this question.")
                input("Press Enter to continue...")
                continue # Re-display the same question prompt
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


