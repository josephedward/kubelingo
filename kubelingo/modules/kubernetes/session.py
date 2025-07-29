import json
import os
import random
import shutil
import shlex
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

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
except ImportError:
    PromptSession = None
    FileHistory = None

from kubelingo.modules.base.session import StudySession
from kubelingo.modules.base.loader import load_session
from kubelingo.gosandbox_integration import GoSandboxIntegration
from .vim_yaml_editor import VimYamlEditor

try:
    from colorama import Fore, Style
except ImportError:
    # Fallback if colorama is not available
    class Fore:
        RED = GREEN = YELLOW = CYAN = MAGENTA = ""
    class Style:
        RESET_ALL = ""

# Quiz data directory (project root 'question-data/' directory)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, os.pardir))
DATA_DIR = os.path.join(ROOT, 'question-data')
DEFAULT_DATA_FILE = os.path.join(DATA_DIR, 'json', 'ckad_quiz_data.json')
YAML_QUESTIONS_FILE = os.path.join(DATA_DIR, 'json', 'yaml_edit_questions.json')
VIM_QUESTIONS_FILE = os.path.join(DATA_DIR, 'json', 'vim_quiz_data.json')
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
            elif question_type in ('live_k8s_edit', 'live_k8s'):
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
            choices, flagged_command_questions, flagged_vim_questions = self._build_interactive_menu_choices(questions)

            selected = questionary.select(
                "Choose an exercise type or subject area:",
                choices=choices,
                use_indicator=True
            ).ask()

            if selected is None:
                print(f"\n{Fore.YELLOW}Quiz cancelled.{Style.RESET_ALL}")
                return

            # Map menu selections to handler methods for cleaner dispatch
            action_map = {
                'vim_review': self._run_vim_commands_quiz,
                'yaml_standard': self._run_yaml_editing_mode,
                'yaml_progressive': self._handle_yaml_progressive,
                'yaml_live': self._handle_yaml_live,
                'yaml_create': self._handle_yaml_create,
                'vim_quiz': self._run_vim_commands_quiz,
                'killercoda_ckad': self._run_killercoda_ckad
            }

            if selected in action_map:
                # Set review flag for review-specific modes before calling handler
                if selected == 'vim_review':
                    args.review_only = True
                else:
                    args.review_only = False
                # Call the handler and exit
                action_map[selected](args)
                return

            # Handle cases that modify args and fall through to the main quiz loop
            if selected == 'flagged':
                args.review_only = True
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

        prompt_session = None
        if PromptSession and FileHistory:
            history_path = os.path.join(os.path.expanduser('~'), '.kubelingo_input_history')
            prompt_session = PromptSession(history=FileHistory(history_path))

        for i, q in enumerate(questions_to_ask, 1):
            category = q.get('category', 'General')
            if category not in per_category_stats:
                per_category_stats[category] = {'asked': 0, 'correct': 0}
            per_category_stats[category]['asked'] += 1

            print(f"\n{Fore.YELLOW}Question {i}/{total_asked} (Category: {category}){Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}{q['prompt']}{Style.RESET_ALL}")

            try:
                if prompt_session:
                    user_answer = prompt_session.prompt(f'{Fore.CYAN}Your answer: {Style.RESET_ALL}').strip()
                else:
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

    def _build_interactive_menu_choices(self, questions):
        """Helper to construct the list of choices for the interactive menu."""
        flagged_command_questions = [q for q in questions if q.get('review')]
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
        choices.append({'name': "Killercoda CKAD Quiz", 'value': "killercoda_ckad"})
        return choices, flagged_command_questions, flagged_vim_questions

    def _handle_yaml_progressive(self, args):
        """Handler for 'YAML Progressive Scenarios' menu option."""
        editor = VimYamlEditor()
        file_path = input("Enter path to progressive scenarios JSON file: ").strip()
        if not file_path: return
        try:
            with open(file_path, 'r') as f:
                exercises = json.load(f)
            editor.run_progressive_yaml_exercises(exercises)
        except Exception as e:
            print(f"Error loading exercises file {file_path}: {e}")

    def _handle_yaml_live(self, args):
        """Handler for 'YAML Live Cluster Exercise' menu option."""
        editor = VimYamlEditor()
        file_path = input("Enter path to live cluster exercise JSON file: ").strip()
        if not file_path: return
        try:
            with open(file_path, 'r') as f:
                exercise = json.load(f)
            editor.run_live_cluster_exercise(exercise)
        except Exception as e:
            print(f"Error loading live exercise file {file_path}: {e}")

    def _handle_yaml_create(self, args):
        """Handler for 'YAML Create Custom Exercise' menu option."""
        editor = VimYamlEditor()
        editor.create_interactive_question()

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

        prompt_session = None
        if PromptSession and FileHistory:
            history_path = os.path.join(os.path.expanduser('~'), '.kubelingo_vim_history')
            prompt_session = PromptSession(history=FileHistory(history_path))

        for i, q in enumerate(questions_to_ask, 1):
            category = q.get('category', 'Vim')

            print(f"\n{Fore.YELLOW}Question {i}/{total_asked}{Style.RESET_ALL}")
            print(f"How do you: {Fore.MAGENTA}{q['prompt']}{Style.RESET_ALL}?")

            try:
                if prompt_session:
                    user_answer = prompt_session.prompt(f'{Fore.CYAN}Your answer: {Style.RESET_ALL}').strip()
                else:
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

    def _run_killercoda_ckad(self, args):  # pylint: disable=unused-argument
        """Runs the Killercoda CKAD CSV-based quiz via the separate module"""
        try:
            session = load_session('killercoda_ckad', self.logger)
        except Exception as e:
            print(Fore.RED + f"Error loading Killercoda CKAD module: {e}" + Style.RESET_ALL)
            return
        init_ok = session.initialize()
        if not init_ok:
            print(Fore.RED + "Killercoda CKAD quiz initialization failed." + Style.RESET_ALL)
            return
        session.run_exercises(args)
        session.cleanup()

    def _run_live_mode(self, args):
        """Handles setup and execution of live Kubernetes exercises."""
        if not self._initialize_live_session():
            return
        
        all_questions = load_questions(args.file)
        live_qs = [q for q in all_questions if q.get('type') in ('live_k8s_edit', 'live_k8s')]
        if not live_qs:
            print(Fore.YELLOW + "No live Kubernetes exercises found in data file." + Style.RESET_ALL)
            return
        
        for i, q in enumerate(live_qs, 1):
            print(f"\n{Fore.CYAN}=== Cloud Exercise {i}/{len(live_qs)} ==={Style.RESET_ALL}")
            print(Fore.YELLOW + f"Q: {q['prompt']}" + Style.RESET_ALL)
            self._run_one_exercise(q)

    def _initialize_live_session(self):
        """Checks for dependencies and prepares for a live session."""
        deps = check_dependencies('kubectl')
        if deps:
            print(Fore.RED + f"Missing dependency for live questions: {', '.join(deps)}. Aborting." + Style.RESET_ALL)
            print(Fore.YELLOW + "Please ensure you have a Kubernetes cluster configured (e.g., minikube, Docker Desktop)." + Style.RESET_ALL)
            return False

        self.live_session_active = True
        print(Fore.YELLOW + "Live mode enabled. Using your pre-configured Kubernetes context." + Style.RESET_ALL)
        try:
            proc = subprocess.run(['kubectl', 'config', 'current-context'], capture_output=True, text=True, check=False)
            if proc.returncode == 0:
                context = proc.stdout.strip()
                if context:
                    print(f"{Fore.CYAN}Current context: {context}{Style.RESET_ALL}")
                else:
                    # A zero exit code with empty output can also mean no context is set.
                    print(Fore.YELLOW + "Warning: No active Kubernetes context found. "
                                       "You may need to set one with 'kubectl config use-context <name>'." + Style.RESET_ALL)
            else:
                # This handles 'current-context is not set' gracefully.
                print(Fore.YELLOW + "Warning: No active Kubernetes context found. "
                                   "You may need to set one with 'kubectl config use-context <name>'." + Style.RESET_ALL)
        except FileNotFoundError:
            # This is already handled by check_dependencies, but for safety:
            print(Fore.RED + "kubectl command not found. Please ensure it is installed and in your PATH." + Style.RESET_ALL)
            return False

        self.cluster_name = "pre-configured"
        return True
    
    def _run_one_exercise(self, q):
        """Handles a single live Kubernetes question against the user's current context."""
        is_correct = False
        try:
            # --- Interactive shell session ---
            print(Fore.GREEN + "\nYou are in a sandboxed environment. Your commands will run against the current Kubernetes context." + Style.RESET_ALL)
            print(Fore.GREEN + "Type 'done' or 'exit' when you have completed the task." + Style.RESET_ALL)

            if q.get('type') == 'live_k8s_edit' and q.get('starting_yaml'):
                with tempfile.NamedTemporaryFile(mode='w+', suffix=".yaml", delete=False, encoding='utf-8') as tmp_yaml:
                    tmp_yaml.write(q.get('starting_yaml'))
                    print(f"A starting YAML file has been created for you at: {Fore.CYAN}{tmp_yaml.name}{Style.RESET_ALL}")

            prompt_session = None
            if PromptSession and FileHistory:
                history_path = os.path.join(os.path.expanduser('~'), '.kubelingo_sandbox_history')
                prompt_session = PromptSession(history=FileHistory(history_path))

            while True:
                try:
                    if prompt_session:
                        command_str = prompt_session.prompt(f'{Fore.CYAN}(kubelingo-sandbox)$ {Style.RESET_ALL}')
                    else:
                        command_str = input(f'{Fore.CYAN}(kubelingo-sandbox)$ {Style.RESET_ALL}')
                except (EOFError, KeyboardInterrupt):
                    print()  # Newline after prompt
                    command_str = 'done'

                command_str = command_str.strip()

                if not command_str:
                    continue
                if command_str.lower() in ('done', 'exit'):
                    break

                cmd_parts = shlex.split(command_str)

                # Handle interactive editors separately to ensure they run in the foreground
                editor_env = os.environ.get('EDITOR', 'vim')
                # Get just the command name, in case it's a path
                editor_name = editor_env.split('/')[-1]
                interactive_commands = ['vim', 'vi', 'nano', 'emacs', editor_name]

                if cmd_parts[0] in interactive_commands:
                    try:
                        # For editors, run directly and inherit stdio
                        subprocess.run(cmd_parts, check=True)
                    except (subprocess.CalledProcessError, FileNotFoundError) as e:
                        print(f"{Fore.RED}Error running editor: {e}{Style.RESET_ALL}")
                else:
                    try:
                        # For other commands, capture and print output
                        proc = subprocess.run(cmd_parts, capture_output=True, text=True, check=False)
                        if proc.stdout:
                            print(proc.stdout, end='')
                        if proc.stderr:
                            print(Fore.YELLOW + proc.stderr + Style.RESET_ALL, end='')
                    except FileNotFoundError:
                        print(f"{Fore.RED}Command not found: {cmd_parts[0]}{Style.RESET_ALL}")
                    except Exception as e:
                        print(f"{Fore.RED}An error occurred: {e}{Style.RESET_ALL}")

            # --- Validation ---
            print("\nValidating your solution...")
            with tempfile.NamedTemporaryFile(mode='w+', suffix=".sh", delete=False, encoding='utf-8') as tmp_assert:
                tmp_assert.write(q.get('assert_script', 'exit 1'))
                assert_path = tmp_assert.name
            os.chmod(assert_path, 0o755)

            # The validation script will use the default KUBECONFIG from the environment
            assert_proc = subprocess.run(['bash', assert_path], capture_output=True, text=True)
            os.remove(assert_path)

            if assert_proc.returncode == 0:
                print(Fore.GREEN + "Correct!" + Style.RESET_ALL)
                if assert_proc.stdout:
                    print(assert_proc.stdout)
                is_correct = True
            else:
                print(Fore.RED + "Incorrect. Validation failed:" + Style.RESET_ALL)
                print(assert_proc.stdout or assert_proc.stderr)
        except Exception as e:
            print(Fore.RED + f"An unexpected error occurred during the exercise: {e}" + Style.RESET_ALL)
        finally:
            # No cloud resources to clean up in this mode.
            pass
        self.logger.info(f"Live exercise: prompt=\"{q['prompt']}\" result=\"{'correct' if is_correct else 'incorrect'}\"")

    def cleanup(self):
        """Deletes the EKS cluster if one was created for a live session."""
        if not self.live_session_active or not self.cluster_name or self.cluster_name == "pre-configured":
            return
        # ... cleanup logic from the original file ...



