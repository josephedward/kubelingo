import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
import difflib
import logging

from kubelingo.utils.validation import commands_equivalent, validate_yaml_structure

try:
    import questionary
except ImportError:
    questionary = None

try:
    import yaml
except ImportError:
    yaml = None

from kubelingo.modules.base.session import StudySession
from kubelingo.modules.base.loader import load_session
from kubelingo.gosandbox_integration import GoSandboxIntegration

# Colored terminal output (ANSI codes) - copied from cli.py
class _AnsiFore:
    CYAN = '\033[36m'
    MAGENTA = '\033[35m'
    YELLOW = '\033[33m'
    GREEN = '\032[32m'
    RED = '\033[31m'
class _AnsiStyle:
    RESET_ALL = '\033[0m'
Fore = _AnsiFore()
Style = _AnsiStyle()

# Quiz data directory (project root 'data/' directory)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, os.pardir))
DATA_DIR = os.path.join(ROOT, 'data')
DEFAULT_DATA_FILE = os.path.join(DATA_DIR, 'ckad_quiz_data.json')
YAML_QUESTIONS_FILE = os.path.join(DATA_DIR, 'yaml_edit_questions.json')
VIM_QUESTIONS_FILE = os.path.join(DATA_DIR, 'vim_quiz_data.json')
# History file for storing past quiz performance
HISTORY_FILE = os.path.join(os.path.expanduser('~'), '.cli_quiz_history.json')

def mark_question_for_review(data_file, category, prompt_text):
    """Adds 'review': True to the matching question in the JSON data file."""
    try:
        with open(data_file, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(Fore.RED + f"Error opening data file for review flagging: {e}" + Style.RESET_ALL)
        return
    changed = False
    for section in data:
        if section.get('category') == category:
            # Support both 'questions' and 'prompts' keys.
            qs = section.get('questions', []) or section.get('prompts', [])
            for item in qs:
                if item.get('prompt') == prompt_text:
                    item['review'] = True
                    changed = True
                    break
        if changed:
            break
    if not changed:
        print(Fore.RED + f"Warning: question not found in {data_file} to flag for review." + Style.RESET_ALL)
        return
    try:
        with open(data_file, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(Fore.RED + f"Error writing data file when flagging for review: {e}" + Style.RESET_ALL)


def unmark_question_for_review(data_file, category, prompt_text):
    """Removes 'review' flag from the matching question in the JSON data file."""
    try:
        with open(data_file, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(Fore.RED + f"Error opening data file for un-flagging: {e}" + Style.RESET_ALL)
        return
    changed = False
    for section in data:
        if section.get('category') == category:
            # Support both 'questions' and 'prompts' keys.
            qs = section.get('questions', []) or section.get('prompts', [])
            for item in qs:
                if item.get('prompt') == prompt_text and item.get('review'):
                    del item['review']
                    changed = True
                    break
        if changed:
            break
    if not changed:
        print(Fore.RED + f"Warning: flagged question not found in {data_file} to un-flag." + Style.RESET_ALL)
        return
    try:
        with open(data_file, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(Fore.RED + f"Error writing data file when un-flagging: {e}" + Style.RESET_ALL)


def check_dependencies(*commands):
    """Check if all command-line tools in `commands` are available."""
    missing = []
    for cmd in commands:
        if not shutil.which(cmd):
            missing.append(cmd)
    return missing

def load_questions(data_file):
    # Load quiz data from JSON file
    try:
        with open(data_file, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(Fore.RED + f"Error loading quiz data from {data_file}: {e}" + Style.RESET_ALL)
        sys.exit(1)
    questions = []
    for cat in data:
        category = cat.get('category', '')
        for item in cat.get('prompts', []):
            question_type = item.get('type', 'command')
            question = {
                'category': category,
                'prompt': item.get('prompt', ''),
                'explanation': item.get('explanation', ''),
                'type': question_type,
                'review': item.get('review', False)
            }
            if question_type == 'yaml_edit':
                if not yaml:
                    # If yaml lib is missing, we can't process these questions.
                    continue
                question['starting_yaml'] = item.get('starting_yaml', '')
                question['correct_yaml'] = item.get('correct_yaml', '')
            elif question_type == 'live_k8s_edit':
                question['starting_yaml'] = item.get('starting_yaml', '')
                question['assert_script'] = item.get('assert_script', '')
            else:  # command
                question['response'] = item.get('response', '')
            questions.append(question)
    return questions
    
class NewSession(StudySession):
    """A study session for all Kubernetes-related quizzes."""

    def __init__(self, logger):
        super().__init__(logger)
        self.cluster_name = None
        self.kubeconfig_path = None
        self.region = None
        self.creds_acquired = False
        self.live_session_active = False # To control cleanup logic

    def initialize(self):
        """Basic initialization. Live session initialization is deferred."""
        return True

    def run_exercises(self, args):
        """
        Router for running exercises. It decides which quiz to run.
        """
        if args.live:
            return self._run_live_mode(args)

        # For non-live exercises, all quiz types are presented in one menu.
        self._run_command_quiz(args)

    def _run_command_quiz(self, args):
        """Run a quiz session for command-line questions."""
        start_time = datetime.now()
        questions = load_questions(args.file)

        # In interactive mode, prompt user for quiz type (flagged/category)
        is_interactive = questionary and not args.category and not args.review_only and not args.num
        if is_interactive:
            # Check for flagged command questions
            flagged_command_questions = [q for q in questions if q.get('review')]
            # Check for flagged Vim questions
            vim_questions = []
            if os.path.exists(VIM_QUESTIONS_FILE):
                vim_questions = load_questions(VIM_QUESTIONS_FILE)
            flagged_vim_questions = [q for q in vim_questions if q.get('review')]

            categories = sorted({q['category'] for q in questions if q.get('category')})
            choices = []
            
            if flagged_command_questions:
                choices.append({'name': f"Review {len(flagged_command_questions)} Flagged Command Questions", 'value': "flagged"})
            if flagged_vim_questions:
                choices.append({'name': f"Review {len(flagged_vim_questions)} Flagged Vim Questions", 'value': "vim_review"})

            if flagged_command_questions or flagged_vim_questions:
                choices.append(questionary.Separator())

            choices.append({'name': "All Command Questions", 'value': "all"})
            for category in categories:
                choices.append({'name': f"Commands: {category}", 'value': category})

            choices.append(questionary.Separator())
            choices.append({'name': "YAML Editing Quiz", 'value': "yaml_standard"})
            choices.append({'name': "YAML Progressive Scenarios", 'value': "yaml_progressive"})
            choices.append({'name': "YAML Live Cluster Exercise", 'value': "yaml_live"})
            choices.append({'name': "YAML Create Custom Exercise", 'value': "yaml_create"})
            choices.append(questionary.Separator())
            choices.append({'name': "Vim Commands Quiz", 'value': "vim_quiz"})

            selected = questionary.select(
                "Choose an exercise type or subject area:",
                choices=choices,
                use_indicator=True
            ).ask()

            if selected is None:
                print(f"\n{Fore.YELLOW}Quiz cancelled.{Style.RESET_ALL}")
                return

            editor = VimYamlEditor()
            if selected == 'flagged':
                args.review_only = True
            elif selected == 'vim_review':
                args.review_only = True
                return self._run_vim_commands_quiz(args)
            elif selected == 'yaml_standard':
                return self._run_yaml_editing_mode(args)
            elif selected == 'yaml_progressive':
                file_path = input("Enter path to progressive scenarios JSON file: ").strip()
                if not file_path: return
                try:
                    with open(file_path, 'r') as f:
                        exercises = json.load(f)
                    return editor.run_progressive_yaml_exercises(exercises)
                except Exception as e:
                    print(f"Error loading exercises file {file_path}: {e}")
            elif selected == 'yaml_live':
                file_path = input("Enter path to live cluster exercise JSON file: ").strip()
                if not file_path: return
                try:
                    with open(file_path, 'r') as f:
                        exercise = json.load(f)
                    return editor.run_live_cluster_exercise(exercise)
                except Exception as e:
                    print(f"Error loading live exercise file {file_path}: {e}")
            elif selected == 'yaml_create':
                return editor.create_interactive_question()
            elif selected == 'vim_quiz':
                args.review_only = False
                return self._run_vim_commands_quiz(args)
            elif selected != 'all':
                args.category = selected

        if args.review_only:
            questions = [q for q in questions if q.get('review')]
            if not questions:
                print(Fore.YELLOW + "No questions flagged for review found." + Style.RESET_ALL)
                return

        if args.category:
            questions = [q for q in questions if q.get('category') == args.category]
            if not questions:
                print(Fore.YELLOW + f"No questions found in category '{args.category}'." + Style.RESET_ALL)
                return

        command_questions = [q for q in questions if q.get('type') == 'command']
        if not command_questions:
            print(Fore.YELLOW + "No command questions available for this quiz." + Style.RESET_ALL)
            return

        num_to_ask = args.num if args.num > 0 else len(command_questions)
        questions_to_ask = random.sample(command_questions, min(num_to_ask, len(command_questions)))

        if not questions_to_ask:
            print(Fore.YELLOW + "No questions to ask." + Style.RESET_ALL)
            return

        correct_count = 0
        per_category_stats = {}
        total_asked = len(questions_to_ask)

        print(f"\n{Fore.CYAN}=== Starting Kubelingo Quiz ==={Style.RESET_ALL}")
        print(f"File: {Fore.CYAN}{os.path.basename(args.file)}{Style.RESET_ALL}, Questions: {Fore.CYAN}{total_asked}{Style.RESET_ALL}")

        for i, q in enumerate(questions_to_ask, 1):
            category = q.get('category', 'General')
            if category not in per_category_stats:
                per_category_stats[category] = {'asked': 0, 'correct': 0}
            per_category_stats[category]['asked'] += 1

            print(f"\n{Fore.YELLOW}Question {i}/{total_asked} (Category: {category}){Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}{q['prompt']}{Style.RESET_ALL}")

            try:
                user_answer = input(f'{Fore.CYAN}Your answer: {Style.RESET_ALL}').strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n{Fore.YELLOW}Quiz interrupted.{Style.RESET_ALL}")
                break
            
            is_correct = commands_equivalent(user_answer, q.get('response', ''))
            if is_correct:
                correct_count += 1
                per_category_stats[category]['correct'] += 1
                print(f"{Fore.GREEN}Correct!{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}Incorrect.{Style.RESET_ALL}")
                print(f"{Fore.GREEN}Correct answer: {q.get('response', '')}{Style.RESET_ALL}")

            self.logger.info(f"Question {i}/{total_asked}: prompt=\"{q['prompt']}\" expected=\"{q.get('response', '')}\" answer=\"{user_answer}\" result=\"{'correct' if is_correct else 'incorrect'}\"")

            if q.get('explanation'):
                print(f"{Fore.CYAN}Explanation: {q['explanation']}{Style.RESET_ALL}")

            # --- Post-question action menu ---
            action_interrupted = False
            while True:
                print() # Spacer
                try:
                    is_flagged = q.get('review', False)
                    flag_option = "Un-flag for Review" if is_flagged else "Flag for Review"
                    
                    if questionary:
                        choices = ["Next Question", flag_option, "Get LLM Clarification"]
                        action = questionary.select("Choose an action:", choices=choices, use_indicator=True).ask()
                        if action is None: raise KeyboardInterrupt
                    else:
                        # Fallback for no questionary
                        print("Choose an action:")
                        print("  1: Next Question")
                        print(f"  2: {flag_option}")
                        print("  3: Get LLM Clarification")
                        choice = input("Enter choice [1]: ").strip()
                        action_map = {'1': "Next Question", '2': flag_option, '3': "Get LLM Clarification"}
                        action = action_map.get(choice, "Next Question")

                    if action == "Next Question":
                        break
                    elif action.startswith("Flag for Review"):
                        mark_question_for_review(args.file, q['category'], q['prompt'])
                        q['review'] = True
                        print(Fore.MAGENTA + "Question flagged for review." + Style.RESET_ALL)
                    elif action.startswith("Un-flag for Review"):
                        unmark_question_for_review(args.file, q['category'], q['prompt'])
                        q['review'] = False
                        print(Fore.MAGENTA + "Question un-flagged." + Style.RESET_ALL)
                    elif action == "Get LLM Clarification":
                        # Use internal LLM session for explanations
                        try:
                            session = load_session('llm', self.logger)
                            if session.initialize():
                                session.run_exercises(q)
                                session.cleanup()
                            else:
                                print(Fore.RED + "LLM module failed to initialize." + Style.RESET_ALL)
                        except Exception as e:
                            print(Fore.RED + f"Error invoking LLM module: {e}" + Style.RESET_ALL)

                except (EOFError, KeyboardInterrupt):
                    print(f"\n{Fore.YELLOW}Quiz interrupted.{Style.RESET_ALL}")
                    action_interrupted = True
                    break

            if action_interrupted:
                break

        end_time = datetime.now()
        duration = str(end_time - start_time).split('.')[0]

        print(f"\n{Fore.CYAN}=== Quiz Complete ==={Style.RESET_ALL}")
        score = (correct_count / total_asked * 100) if total_asked > 0 else 0
        print(f"You got {Fore.GREEN}{correct_count}{Style.RESET_ALL} out of {Fore.YELLOW}{total_asked}{Style.RESET_ALL} correct ({Fore.CYAN}{score:.1f}%{Style.RESET_ALL}).")
        print(f"Time taken: {Fore.CYAN}{duration}{Style.RESET_ALL}")

        # Save history
        new_history_entry = {
            'timestamp': start_time.strftime('%Y-%m-%d %H:%M:%S'),
            'num_questions': total_asked,
            'num_correct': correct_count,
            'duration': duration,
            'data_file': os.path.basename(args.file),
            'category_filter': args.category,
            'per_category': per_category_stats
        }

        history = []
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r') as f:
                    history_data = json.load(f)
                    if isinstance(history_data, list):
                        history = history_data
            except (json.JSONDecodeError, IOError):
                pass  # Start with fresh history if file is corrupt or unreadable

        history.insert(0, new_history_entry)

        try:
            with open(HISTORY_FILE, 'w') as f:
                json.dump(history, f, indent=2)
        except IOError as e:
            print(Fore.RED + f"Error saving quiz history: {e}" + Style.RESET_ALL)


    def _run_yaml_editing_mode(self, args):
        """Run semantic YAML editing exercises from JSON definitions."""
        if yaml is None:
            print(f"{Fore.RED}YAML library not installed. Please run 'pip install pyyaml'.{Style.RESET_ALL}")
            return

        try:
            with open(YAML_QUESTIONS_FILE, 'r') as f:
                sections = json.load(f)
        except Exception as e:
            print(f"Error loading YAML exercise data from {YAML_QUESTIONS_FILE}: {e}")
            return

        editor = VimYamlEditor()
        yaml_exercises = []
        for section in sections:
            category = section.get('category', 'General')
            for item in section.get('prompts', []):
                if item.get('question_type') == 'yaml_edit':
                    item['category'] = category
                    yaml_exercises.append(item)

        if not yaml_exercises:
            print("No YAML exercises found in data file.")
            return

        print(f"\n{Fore.CYAN}=== Kubelingo YAML Editing Mode ==={Style.RESET_ALL}")
        print(f"Found {len(yaml_exercises)} YAML editing exercises.")
        print(f"Editor: {os.environ.get('EDITOR', 'vim')}")

        for idx, question in enumerate(random.sample(yaml_exercises, len(yaml_exercises)), 1):
            print(f"\n{Fore.YELLOW}Exercise {idx}/{len(yaml_exercises)}: {question.get('prompt')}{Style.RESET_ALL}")
            success = editor.run_yaml_edit_question(question, index=idx)
            if success and question.get('explanation'):
                print(f"{Fore.GREEN}Explanation: {question['explanation']}{Style.RESET_ALL}")
            if idx < len(yaml_exercises):
                try:
                    cont = input("Continue to next exercise? (y/N): ")
                    if not cont.lower().startswith('y'):
                        break
                except (EOFError, KeyboardInterrupt):
                    print("\nExiting exercise mode.")
                    break
        print(f"\n{Fore.CYAN}=== YAML Editing Session Complete ==={Style.RESET_ALL}")

    def _run_vim_commands_quiz(self, args):
        """Runs the Vim commands quiz, with flagging support."""
        start_time = datetime.now()
        data_file = VIM_QUESTIONS_FILE
        if not os.path.exists(data_file):
            print(f"{Fore.RED}Vim questions data file not found at {data_file}{Style.RESET_ALL}")
            return
        
        questions = load_questions(data_file)

        if args.review_only:
            questions = [q for q in questions if q.get('review')]
            if not questions:
                print(Fore.YELLOW + "No Vim questions flagged for review found." + Style.RESET_ALL)
                return
            print(Fore.MAGENTA + f"Starting review session for {len(questions)} flagged Vim questions." + Style.RESET_ALL)
        
        questions_to_ask = random.sample(questions, len(questions))
            
        correct_count = 0
        total_asked = len(questions_to_ask)

        print(f"\n{Fore.CYAN}--- Basic Vim Commands Quiz ---{Style.RESET_ALL}")
        print("Test your knowledge of essential Vim commands.")

        for i, q in enumerate(questions_to_ask, 1):
            category = q.get('category', 'Vim')

            print(f"\n{Fore.YELLOW}Question {i}/{total_asked}{Style.RESET_ALL}")
            print(f"How do you: {Fore.MAGENTA}{q['prompt']}{Style.RESET_ALL}?")

            try:
                user_answer = input(f'{Fore.CYAN}Your answer: {Style.RESET_ALL}').strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n{Fore.YELLOW}Quiz interrupted.{Style.RESET_ALL}")
                break
            
            is_correct = user_answer == q.get('response', '')
            if is_correct:
                correct_count += 1
                print(f"\n{Fore.GREEN}Correct!{Style.RESET_ALL}")
            else:
                print(f"\n{Fore.RED}Incorrect.{Style.RESET_ALL}")
                print(f"{Fore.GREEN}Correct answer: {q.get('response', '')}{Style.RESET_ALL}")

            self.logger.info(f"Vim Question {i}/{total_asked}: prompt=\"{q['prompt']}\" expected=\"{q.get('response', '')}\" answer=\"{user_answer}\" result=\"{'correct' if is_correct else 'incorrect'}\"")

            # --- Post-question action menu ---
            action_interrupted = False
            while True:
                print() # Spacer
                try:
                    is_flagged = q.get('review', False)
                    flag_option = "Un-flag for Review" if is_flagged else "Flag for Review"
                    
                    if questionary:
                        choices = ["Next Question", flag_option, "Get LLM Clarification"]
                        action = questionary.select("Choose an action:", choices=choices, use_indicator=True).ask()
                        if action is None: raise KeyboardInterrupt
                    else:
                        # Fallback for no questionary
                        print("Choose an action:")
                        print("  1: Next Question")
                        print(f"  2: {flag_option}")
                        print("  3: Get LLM Clarification")
                        choice = input("Enter choice [1]: ").strip()
                        action_map = {'1': "Next Question", '2': flag_option, '3': "Get LLM Clarification"}
                        action = action_map.get(choice, "Next Question")

                    if action == "Next Question":
                        break
                    elif action.startswith("Flag for Review"):
                        mark_question_for_review(data_file, q['category'], q['prompt'])
                        q['review'] = True
                        print(Fore.MAGENTA + "Question flagged for review." + Style.RESET_ALL)
                    elif action.startswith("Un-flag for Review"):
                        unmark_question_for_review(data_file, q['category'], q['prompt'])
                        q['review'] = False
                        print(Fore.MAGENTA + "Question un-flagged." + Style.RESET_ALL)
                    elif action == "Get LLM Clarification":
                        # Use internal LLM session for explanations
                        try:
                            session = load_session('llm', self.logger)
                            if session.initialize():
                                session.run_exercises(q)
                                session.cleanup()
                            else:
                                print(Fore.RED + "LLM module failed to initialize." + Style.RESET_ALL)
                        except Exception as e:
                            print(Fore.RED + f"Error invoking LLM module: {e}" + Style.RESET_ALL)

                except (EOFError, KeyboardInterrupt):
                    print(f"\n{Fore.YELLOW}Quiz interrupted.{Style.RESET_ALL}")
                    action_interrupted = True
                    break

            if action_interrupted:
                break

        end_time = datetime.now()
        duration = str(end_time - start_time).split('.')[0]

        print(f"\n{Fore.CYAN}--- Vim Quiz Complete ---{Style.RESET_ALL}")
        score = (correct_count / total_asked * 100) if total_asked > 0 else 0
        print(f"You got {Fore.GREEN}{correct_count}{Style.RESET_ALL} out of {Fore.YELLOW}{total_asked}{Style.RESET_ALL} correct ({Fore.CYAN}{score:.1f}%{Style.RESET_ALL}).")
        print(f"Time taken: {Fore.CYAN}{duration}{Style.RESET_ALL}")

    def _run_live_mode(self, args):
        """Handles setup and execution of live Kubernetes exercises."""
        if not self._initialize_live_session():
            return
        
        all_questions = load_questions(args.file)
        live_qs = [q for q in all_questions if q.get('type') == 'live_k8s_edit']
        if not live_qs:
            print(Fore.YELLOW + "No live Kubernetes exercises found in data file." + Style.RESET_ALL)
            return
        
        for i, q in enumerate(live_qs, 1):
            print(f"\n{Fore.CYAN}=== Cloud Exercise {i}/{len(live_qs)} ==={Style.RESET_ALL}")
            print(Fore.YELLOW + f"Q: {q['prompt']}" + Style.RESET_ALL)
            self._run_one_exercise(q)

    def _initialize_live_session(self):
        """Provisions a temporary EKS cluster for the session, or uses existing context."""
        deps = check_dependencies('go', 'kubectl')
        if deps:
            print(Fore.RED + f"Missing dependencies for live questions: {', '.join(deps)}. Aborting." + Style.RESET_ALL)
            return False

        self.live_session_active = True

        if not shutil.which('eksctl'):
            print(Fore.YELLOW + "Warning: 'eksctl' not found. Using pre-configured Kubernetes context." + Style.RESET_ALL)
            self.cluster_name = "pre-configured"
            return True

        self.cluster_name = f"kubelingo-quiz-{random.randint(1000, 9999)}"
        # ... rest of the live session setup from the original file ...
        return True
    
    def _run_one_exercise(self, q):
        """Handles a single live Kubernetes question with an ephemeral EKS cluster."""
        is_correct = False
        # Ensure dependencies are available
        deps = check_dependencies('go', 'eksctl', 'kubectl')
        if deps:
            print(Fore.RED + f"Missing dependencies for live questions: {', '.join(deps)}. Skipping." + Style.RESET_ALL)
            return

        cluster_name = f"kubelingo-quiz-{random.randint(1000, 9999)}"
        kubeconfig_path = os.path.join(tempfile.gettempdir(), f"{cluster_name}.kubeconfig")
        user_yaml_str = ''
        try:
            # Acquire sandbox credentials
            print(Fore.YELLOW + "Acquiring AWS sandbox credentials via gosandbox..." + Style.RESET_ALL)
            gs = GoSandboxIntegration()
            creds = gs.acquire_credentials()
            if not creds:
                print(Fore.RED + "Failed to acquire AWS credentials. Cannot proceed with cloud exercise." + Style.RESET_ALL)
                return
            gs.export_to_environment()

            # Provision EKS cluster
            region = os.environ.get('AWS_REGION', 'us-west-2')
            node_type = os.environ.get('CLUSTER_INSTANCE_TYPE', 't3.medium')
            node_count = os.environ.get('NODE_COUNT', '2')
            print(Fore.YELLOW + f"Provisioning EKS cluster '{cluster_name}' "
                               f"(region={region}, nodes={node_count}, type={node_type})..." + Style.RESET_ALL)
            subprocess.run([
                'eksctl', 'create', 'cluster',
                '--name', cluster_name,
                '--region', region,
                '--nodegroup-name', 'worker-nodes',
                '--node-type', node_type,
                '--nodes', node_count
            ], check=True)

            # Write kubeconfig
            os.environ['KUBECONFIG'] = kubeconfig_path
            with open(kubeconfig_path, 'w') as kc:
                subprocess.run(['kubectl', 'config', 'view', '--raw'], stdout=kc, check=True)

            editor = os.environ.get('EDITOR', 'vim')
            # User edit loop
            while True:
                with tempfile.NamedTemporaryFile(mode='w+', suffix=".yaml", delete=False, encoding='utf-8') as tmp_yaml:
                    tmp_yaml.write(q.get('starting_yaml', ''))
                    tmp_path = tmp_yaml.name

                print(f"Opening a temp file in '{editor}' for you to edit...")
                try:
                    subprocess.run([editor, tmp_path], check=True)
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    print(Fore.RED + f"Error opening editor '{editor}': {e}. Skipping question." + Style.RESET_ALL)
                    break

                with open(tmp_path, 'r', encoding='utf-8') as f:
                    user_yaml_str = f.read()
                os.remove(tmp_path)

                print("Applying your YAML to the cluster...")
                apply_proc = subprocess.run([
                    'kubectl', 'apply', '-f', '-'
                ], input=user_yaml_str, text=True, capture_output=True)
                if apply_proc.returncode != 0:
                    print(Fore.RED + "Error applying YAML:" + Style.RESET_ALL)
                    print(apply_proc.stderr)
                else:
                    print("Running validation script...")
                    with tempfile.NamedTemporaryFile(mode='w+', suffix=".sh", delete=False, encoding='utf-8') as tmp_assert:
                        tmp_assert.write(q.get('assert_script', 'exit 1'))
                        assert_path = tmp_assert.name
                    os.chmod(assert_path, 0o755)
                    assert_proc = subprocess.run(['bash', assert_path], capture_output=True, text=True)
                    os.remove(assert_path)
                    if assert_proc.returncode == 0:
                        print(Fore.GREEN + "Correct!" + Style.RESET_ALL)
                        print(assert_proc.stdout)
                        is_correct = True
                        break
                    else:
                        print(Fore.RED + "Incorrect. Validation failed:" + Style.RESET_ALL)
                        print(assert_proc.stdout or assert_proc.stderr)

                try:
                    retry = input("Reopen editor to try again? [Y/n]: ").strip().lower()
                except EOFError:
                    retry = 'n'
                if retry.startswith('n'):
                    break
        finally:
            # Delete cluster and cleanup
            print(Fore.YELLOW + f"Deleting EKS cluster '{cluster_name}'..." + Style.RESET_ALL)
            subprocess.run([
                'eksctl', 'delete', 'cluster',
                '--name', cluster_name,
                '--region', os.environ.get('AWS_REGION', 'us-west-2')
            ], check=True)
            if os.path.exists(kubeconfig_path):
                os.remove(kubeconfig_path)
            if 'KUBECONFIG' in os.environ:
                del os.environ['KUBECONFIG']
        self.logger.info(f"Live exercise: prompt=\"{q['prompt']}\" result=\"{'correct' if is_correct else 'incorrect'}\"")

    def cleanup(self):
        """Deletes the EKS cluster if one was created for a live session."""
        if not self.live_session_active or not self.cluster_name or self.cluster_name == "pre-configured":
            return
        # ... cleanup logic from the original file ...

# ==============================================================================
# YAML/Vim Quiz components, moved from vim_yaml_editor.py
# ==============================================================================

class VimYamlEditor:
    """
    Provides functionality to create, edit, and validate Kubernetes YAML manifests
    interactively using Vim.
    """
    def __init__(self):
        pass

    def create_yaml_exercise(self, exercise_type, template_data=None):
        """Creates a YAML exercise template for a given resource type."""
        exercises = {
            "pod": self._pod_exercise,
            "configmap": self._configmap_exercise,
            "deployment": self._deployment_exercise,
            "service": self._service_exercise,
            "secret": self._secret_exercise
        }
        if exercise_type in exercises:
            return exercises[exercise_type](template_data or {})
        raise ValueError(f"Unknown exercise type: {exercise_type}")

    def _pod_exercise(self, data):
        template = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {"name": data.get("name", "nginx-pod"),
                         "labels": data.get("labels", {"app": "nginx"})},
            "spec": {"containers": [{
                "name": data.get("container_name", "nginx"),
                "image": data.get("image", "nginx:1.20"),
                "ports": data.get("ports", [{"containerPort": 80}])
            }]}
        }
        if data.get("env_vars"):
            template["spec"]["containers"][0]["env"] = data["env_vars"]
        if data.get("volume_mounts"):
            template["spec"]["containers"][0]["volumeMounts"] = data["volume_mounts"]
            template["spec"]["volumes"] = data.get("volumes", [])
        return template

    def _configmap_exercise(self, data):
        return {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": data.get("name", "app-config")},
            "data": data.get("data", {"database_url": "mysql://localhost:3306/app",
                                          "debug": "true"})
        }
    def _deployment_exercise(self, data):
        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": data.get("name", "example-deployment")},
            "spec": {
                "replicas": data.get("replicas", 1),
                "selector": {"matchLabels": data.get("selector", {"app": "example"})},
                "template": {
                    "metadata": {"labels": data.get("selector", {"app": "example"})},
                    "spec": {"containers": [{
                        "name": data.get("container_name", "example"),
                        "image": data.get("image", "nginx:latest"),
                        "ports": data.get("ports", [{"containerPort": 80}])
                    }]}
                }
            }
        }
    def _service_exercise(self, data):
        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": data.get("name", "example-service")},
            "spec": {
                "selector": data.get("selector", {"app": "example"}),
                "ports": data.get("ports", [{"port": 80, "targetPort": 80}]),
                "type": data.get("type", "ClusterIP")
            }
        }

    def _secret_exercise(self, data):
        return {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": data.get("name", "my-secret")},
            "type": "Opaque",
            "data": data.get("data", {})
        }

    def edit_yaml_with_vim(self, yaml_content, filename="exercise.yaml"):
        """
        Opens YAML content in Vim for interactive editing.

        This method saves the provided YAML content to a temporary file and opens it
        using the editor specified by the EDITOR environment variable, defaulting to 'vim'.
        After editing, it reads the modified content, parses it as YAML, and returns
        the resulting Python object. The temporary file is deleted afterward.

        Args:
            yaml_content (str or dict): The initial YAML content, either as a raw
                                       string or a Python dictionary.
            filename (str): A suggested filename. This parameter is kept for backward
                            compatibility but is currently ignored.

        Returns:
            dict or None: The parsed YAML content as a Python dictionary, or None if
                          the editor fails to launch or the edited content is not
                          valid YAML.
        """
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode='w', encoding='utf-8') as tmp:
            # If yaml_content is a raw YAML string, write it directly; otherwise dump the Python object
            if isinstance(yaml_content, str):
                tmp.write(yaml_content)
            else:
                yaml.dump(yaml_content, tmp, default_flow_style=False)
            tmp_filename = tmp.name

        # Launch editor
        editor = os.environ.get('EDITOR', 'vim')
        try:
            subprocess.run([editor, tmp_filename], check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Error launching editor. Ensure EDITOR is set and available.")
            os.unlink(tmp_filename)
            return None

        # Read edited content
        try:
            with open(tmp_filename, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Failed to parse YAML: {e}")
            return None
        finally:
            os.unlink(tmp_filename)


    def run_yaml_edit_question(self, question, index=None):
        """
        Runs a full YAML editing exercise for a single question.

        This method orchestrates the exercise by:
        1. Displaying the prompt.
        2. Opening the starting YAML in Vim for editing.
        3. Allowing multiple attempts to edit and validate the YAML.
        4. Comparing the user's final YAML with the expected solution.
        5. Providing feedback and showing the correct solution if needed.

        Args:
            question (dict): A dictionary containing the exercise details, including
                             'prompt', 'starting_yaml', and 'correct_yaml'.
            index (int, optional): The index of the question for display purposes.

        Returns:
            bool: True if the user's solution matches the expected solution (or if it
                  is structurally valid when no solution is provided), False otherwise.
        """
        prompt = question.get('prompt') or question.get('requirements', '')
        print(f"\n=== Exercise {index}: {prompt} ===")
        # Prepare initial YAML and expected solution
        starting = question.get('starting_yaml', '')
        expected_raw = question.get('correct_yaml')
        expected_obj = None
        if expected_raw is not None and yaml:
            try:
                expected_obj = yaml.safe_load(expected_raw) if isinstance(expected_raw, str) else expected_raw
            except Exception:
                expected_obj = None
        # Interactive edit loop, allow retries on failure
        success = False
        last_valid = False
        content_to_edit = starting
        while True:
            edited = self.edit_yaml_with_vim(content_to_edit, f"exercise-{index}.yaml")
            if edited is None:
                try:
                    retry = input("Could not parse YAML. Try again from last valid state? (y/N): ").strip().lower().startswith('y')
                except (EOFError, KeyboardInterrupt):
                    retry = False
                if not retry:
                    break
                continue

            content_to_edit = edited  # Update content for next retry
            # Semantic validation of required fields
            validation_result = validate_yaml_structure(yaml.dump(edited))
            if validation_result['valid']:
                msg = "YAML is valid"
                if validation_result['warnings']:
                    msg += f" (warnings: {', '.join(validation_result['warnings'])})"
            else:
                msg = f"Invalid: {', '.join(validation_result['errors'])}"
            print(f"Validation: {msg}")
            last_valid = validation_result['valid']
            # If expected solution provided, compare
            if expected_obj is not None:
                if edited == expected_obj:
                    print("✅ Correct!")
                    success = True
                    break
                print("❌ YAML does not match expected output. Differences:")
                try:
                    exp_lines = yaml.dump(expected_obj, default_flow_style=False).splitlines()
                    edit_lines = yaml.dump(edited, default_flow_style=False).splitlines()
                    for line in difflib.unified_diff(exp_lines, edit_lines, fromfile='Expected', tofile='Your', lineterm=''):
                        print(line)
                except Exception as diff_err:
                    print(f"Error generating diff: {diff_err}")
            else:
                # No expected, use basic validation
                if valid:
                    success = True
                    break
            # Ask user to retry or skip
            try:
                retry = input("Try again? (y/N): ").strip().lower().startswith('y')
            except (EOFError, KeyboardInterrupt):
                retry = False
            if not retry:
                break
        # If expected exists and failed after retries, show expected solution
        if expected_obj is not None and not success:
            print("\nExpected solution:" )
            try:
                print(yaml.dump(expected_obj, default_flow_style=False))
            except Exception:
                print(expected_raw)
        # Return success for expected-based, else last validation status
        return success if expected_obj is not None else last_valid

    def run_progressive_yaml_exercises(self, exercises):
        """Run multi-step YAML exercise with progressive complexity."""
        if not exercises:
            print("No exercises provided.")
            return False
        current_yaml = exercises[0].get('starting_yaml', '')
        for step_idx, step in enumerate(exercises, start=1):
            print(f"\n=== Step {step_idx}: {step.get('prompt', '')} ===")
            content_to_edit = current_yaml
            while True:
                edited = self.edit_yaml_with_vim(content_to_edit, f"step-{step_idx}.yaml")
                if edited is None:
                    return False
                if 'validation_func' in step and callable(step['validation_func']):
                    valid, msg = step['validation_func'](edited)
                    print(f"Step validation: {msg}")
                    if not valid:
                        try:
                            retry = input("Fix this step? (y/N): ").strip().lower().startswith('y')
                        except (EOFError, KeyboardInterrupt):
                            retry = False
                        if retry:
                            content_to_edit = edited
                            continue
                        return False
                current_yaml = edited
                break
        return True

    def run_scenario_exercise(self, scenario):
        """Run scenario-based exercise with dynamic requirements."""
        title = scenario.get('title', '')
        print(f"\n=== Scenario: {title} ===")
        description = scenario.get('description', '')
        if description:
            print(description)
        current_yaml = scenario.get('base_template', '')
        for requirement in scenario.get('requirements', []):
            desc = requirement.get('description', '')
            print(f"\n📋 Requirement: {desc}")
            if requirement.get('hints'):
                try:
                    show_hints = input("Show hints? (y/N): ").strip().lower().startswith('y')
                except (EOFError, KeyboardInterrupt):
                    show_hints = False
                if show_hints:
                    for hint in requirement.get('hints', []):
                        print(f"💡 {hint}")
            edited = self.edit_yaml_with_vim(current_yaml)
            if edited is None:
                continue
            if self._validate_requirement(edited, requirement):
                print("✅ Requirement satisfied!")
                current_yaml = edited
            else:
                print("❌ Requirement not met. Try again.")
        return current_yaml

    def run_live_cluster_exercise(self, exercise):
        """Interactive exercise that applies to real cluster."""
        print(f"\n🚀 Live Exercise: {exercise.get('prompt', '')}")
        starting_yaml = exercise.get('starting_yaml', '')
        edited_yaml = self.edit_yaml_with_vim(starting_yaml)
        if edited_yaml is None:
            return False
        try:
            apply_choice = input("Apply to cluster? (y/N): ").strip().lower().startswith('y')
        except (EOFError, KeyboardInterrupt):
            apply_choice = False
        if apply_choice:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(edited_yaml, f)
                temp_path = f.name
            try:
                result = subprocess.run(['kubectl', 'apply', '-f', temp_path], capture_output=True, text=True)
                if result.returncode == 0:
                    print("✅ Successfully applied to cluster!")
                    if exercise.get('validation_script'):
                        self._run_validation_script(exercise['validation_script'])
                else:
                    print(f"❌ Apply failed: {result.stderr}")
            finally:
                os.unlink(temp_path)
        return True

    def create_interactive_question(self):
        """Build custom YAML exercise interactively."""
        if yaml is None:
            print("YAML library not available.")
            return None
        print("\n=== Create Custom YAML Exercise ===")
        resource_types = ["pod", "deployment", "service", "configmap", "secret"]
        print("Available resource types: " + ", ".join(resource_types))
        try:
            resource_type = input("Choose resource type: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return None
        if resource_type not in resource_types:
            print("Invalid resource type")
            return None
        requirements = []
        while True:
            try:
                req = input("Add requirement (or 'done'): ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nCustom exercise creation cancelled.")
                return None
            if req.lower() == 'done':
                break
            requirements.append(req)
        if not requirements:
            print("No requirements added, cancelling exercise.")
            return None
        template = self.create_yaml_exercise(resource_type)
        starting_yaml = yaml.dump(template, default_flow_style=False)
        exercise = {
            'prompt': f"Create a {resource_type} with: {', '.join(requirements)}",
            'starting_yaml': starting_yaml
        }
        return self.run_yaml_edit_question(exercise)

    def _validate_requirement(self, yaml_obj, requirement):
        """Internal helper to validate a single requirement."""
        if 'validation_func' in requirement and callable(requirement['validation_func']):
            valid, _ = requirement['validation_func'](yaml_obj)
            return valid
        return True

    def _run_validation_script(self, script):
        """Internal helper to run an external validation script."""
        try:
            if isinstance(script, str):
                result = subprocess.run(script, shell=True, capture_output=True, text=True)
            else:
                result = subprocess.run(script, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Validation script failed: {result.stderr}")
                return False
            print(result.stdout)
            return True
        except Exception as e:
            print(f"Error running validation script: {e}")
            return False


