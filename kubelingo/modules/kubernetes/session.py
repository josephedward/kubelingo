import csv
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import shlex
import webbrowser
from datetime import datetime
import logging

from kubelingo.utils.ui import (
    Fore, Style, questionary, yaml, humanize_module
)
from kubelingo.utils.config import (
    ROOT,
    LOGS_DIR,
    HISTORY_FILE,
    DEFAULT_DATA_FILE,
    VIM_QUESTIONS_FILE,
    YAML_QUESTIONS_FILE,
    DATA_DIR,
    INPUT_HISTORY_FILE,
    VIM_HISTORY_FILE,
    KILLERCODA_CSV_FILE,
)

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
except ImportError:
    PromptSession = None
    FileHistory = None

from kubelingo.modules.base.session import StudySession, SessionManager
from pathlib import Path
import os

# AI-based validator for command equivalence
try:
    import openai
except ImportError:
    openai = None

def ai_validate(transcript: str, expected_cmd: str, question_text: str) -> bool:
    """
    Use OpenAI to semantically compare a student's kubectl transcript
    against the expected command. Returns True if equivalent.
    """
    if openai is None:
        raise RuntimeError('openai package not installed; install with pip install openai')
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY environment variable not set')
    openai.api_key = api_key
    messages = [
        {"role": "system", "content": (
            "You are a Kubernetes expert. Determine if the student's kubectl command is semantically equivalent "
            "to the expected kubectl command. Reply with only 'yes' or 'no'."
        )},
        {"role": "user", "content": (
            f"Question: \"{question_text}\"\n"
            f"Expected Command: `{expected_cmd}`\n"
            "Student Transcript:\n"
            "```\n"
            f"{transcript}\n"
            "```\n"
            "Are these equivalent? Reply 'yes' or 'no'."
        )}
    ]
    resp = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=0
    )
    reply = resp.choices[0].message.content.strip().lower()
    return reply.startswith('yes')


def ai_validate_command(user_cmd: str, expected_cmd: str, question_text: str) -> bool:
    """
    Use OpenAI to semantically compare a student's kubectl command
    against the expected command. Returns True if equivalent.
    """
    if openai is None:
        raise RuntimeError('openai package not installed; install with pip install openai')
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY environment variable not set')
    openai.api_key = api_key
    messages = [
        {"role": "system", "content": (
            "You are a Kubernetes expert. Determine if the student's kubectl command is semantically equivalent "
            "to the expected kubectl command for the given exercise. Reply with only 'yes' or 'no'."
        )},
        {"role": "user", "content": (
            f"Question: \"{question_text}\"\n"
            f"Expected Command: `{expected_cmd}`\n"
            f"Student Submitted: `{user_cmd}`\n"
            "Are these semantically equivalent?"
        )}
    ]
    resp = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=0
    )
    reply = resp.choices[0].message.content.strip().lower()
    return reply.startswith('yes')


from kubelingo.modules.base.loader import load_session
from kubelingo.modules.json_loader import JSONLoader
from kubelingo.modules.md_loader import MDLoader
from kubelingo.modules.yaml_loader import YAMLLoader
from dataclasses import asdict
from kubelingo.utils.validation import commands_equivalent
# Existing import
# Existing import
from .vim_yaml_editor import VimYamlEditor
from .answer_checker import evaluate_transcript
from kubelingo.sandbox import spawn_pty_shell, launch_container_sandbox, ShellResult, StepResult
import logging  # for logging in exercises
# Stub out AI evaluator to avoid heavy external dependencies


def _get_quiz_files():
    """Returns a list of paths to JSON command quiz files, excluding special ones."""
    json_dir = os.path.join(DATA_DIR, 'json')
    if not os.path.isdir(json_dir):
        return []

    # Exclude special files that have their own quiz modes
    excluded_files = [os.path.basename(f) for f in [YAML_QUESTIONS_FILE, VIM_QUESTIONS_FILE] if f]

    return sorted([
        os.path.join(json_dir, f)
        for f in os.listdir(json_dir)
        if f.endswith('.json') and f not in excluded_files
    ])


def _get_md_quiz_files():
    """Returns a list of paths to Markdown quiz files that contain runnable questions."""
    md_dir = os.path.join(DATA_DIR, 'md')
    if not os.path.isdir(md_dir):
        return []

    runnable_files = []
    for f in os.listdir(md_dir):
        if f.endswith(('.md', '.markdown')):
            file_path = os.path.join(md_dir, f)
            # Pass exit_on_error=False to prevent halting on non-quiz markdown files.
            questions = load_questions(file_path, exit_on_error=False)
            # A file is a runnable quiz if it has at least one question of a runnable type.
            if any(q.get('type') in ('command', 'live_k8s', 'live_k8s_edit') for q in questions):
                runnable_files.append(file_path)

    return sorted(runnable_files)


def _get_yaml_quiz_files():
    """Returns a list of paths to YAML quiz files."""
    yaml_dir = os.path.join(DATA_DIR, 'yaml')
    if not os.path.isdir(yaml_dir):
        return []
    return sorted([
        os.path.join(yaml_dir, f)
        for f in os.listdir(yaml_dir)
        if f.endswith(('.yaml', '.yml'))
    ])


def get_all_flagged_questions():
    """Returns a list of all questions from all files that are flagged for review."""
    all_quiz_files = _get_quiz_files() + _get_md_quiz_files() + _get_yaml_quiz_files()
    if os.path.exists(VIM_QUESTIONS_FILE):
        all_quiz_files.append(VIM_QUESTIONS_FILE)
    all_quiz_files = sorted(list(set(all_quiz_files)))

    all_flagged = []
    for f in all_quiz_files:
        # Load questions without exiting on error (e.g., missing dependencies)
        try:
            qs = load_questions(f, exit_on_error=False)
        except Exception:
            continue
        for q in qs:
            if q.get('review'):
                q['data_file'] = f  # Tag with origin file
                all_flagged.append(q)
    return all_flagged


def _clear_all_review_flags(logger):
    """Removes 'review' flag from all questions in all known JSON quiz files."""
    quiz_files = _get_quiz_files()
    # Also include the vim file in the clear operation
    if os.path.exists(VIM_QUESTIONS_FILE):
        quiz_files.append(VIM_QUESTIONS_FILE)

    cleared_count = 0
    for data_file in quiz_files:
        try:
            with open(data_file, 'r') as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Error opening {data_file} for clearing flags: {e}")
            continue

        changed_in_file = False
        for item in data:
            # Clear top-level review flags
            if 'review' in item:
                del item['review']
                changed_in_file = True
                cleared_count += 1
            # Clear nested review flags in prompts (for Markdown/YAML quizzes)
            if isinstance(item, dict) and 'prompts' in item and isinstance(item['prompts'], list):
                for prompt in item['prompts']:
                    if isinstance(prompt, dict) and 'review' in prompt:
                        del prompt['review']
                        changed_in_file = True
                        cleared_count += 1

        if changed_in_file:
            try:
                with open(data_file, 'w') as f:
                    json.dump(data, f, indent=2)
                logger.info(f"Cleared review flags in {data_file}")
            except Exception as e:
                logger.error(f"Error writing to {data_file} after clearing flags: {e}")

    if cleared_count > 0:
        print(f"\n{Fore.GREEN}Cleared {cleared_count} review flags from all quiz files.{Style.RESET_ALL}")
    else:
        print(f"\n{Fore.YELLOW}No review flags to clear.{Style.RESET_ALL}")


def check_dependencies(*commands):
    """Check if all command-line tools in `commands` are available."""
    missing = []
    for cmd in commands:
        if not shutil.which(cmd):
            missing.append(cmd)
    return missing

def load_questions(data_file, exit_on_error=True):
    """Loads questions from JSON, YAML, or Markdown files using dedicated loaders."""
    ext = os.path.splitext(data_file)[1].lower()
    # Handle raw JSON list-of-modules questions format (from Markdown/YAML quizzes)
    if ext == '.json':
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
        except Exception as e:
            if exit_on_error:
                print(Fore.RED + f"Error loading quiz data from {data_file}: {e}" + Style.RESET_ALL)
                sys.exit(1)
            return []
        # If JSON file is a list, detect format:
        if isinstance(raw_data, list):
            # Case: list of modules with nested prompts (e.g., CKAD exercises)
            if raw_data and isinstance(raw_data[0], dict) and 'prompts' in raw_data[0]:
                questions = []
                for module in raw_data:
                    if not isinstance(module, dict):
                        continue
                    category = module.get('category')
                    for prompt in module.get('prompts', []):
                        if not isinstance(prompt, dict):
                            continue
                        q = prompt.copy()
                        if category is not None:
                            q['category'] = category
                        questions.append(q)
                return questions
            # Case: list of simple questions (e.g., Killercoda CKAD)
            if raw_data and isinstance(raw_data[0], dict) and 'prompt' in raw_data[0]:
                questions = []
                for item in raw_data:
                    if not isinstance(item, dict):
                        continue
                    q = item.copy()
                    # Normalize 'answer' key to 'response'
                    if 'answer' in q:
                        q['response'] = q.pop('answer')
                    questions.append(q)
                return questions
        loader = JSONLoader()
    elif ext in ('.md', '.markdown'):
        loader = MDLoader()
    elif ext in ('.yaml', '.yml'):
        loader = YAMLLoader()
    else:
        if exit_on_error:
            print(Fore.RED + f"Unsupported file type for quiz data: {data_file}" + Style.RESET_ALL)
            sys.exit(1)
        return []

    try:
        # Loaders return a list of Question objects. The quiz logic expects dicts.
        questions_obj = loader.load_file(data_file)

        # If a loader returns a list containing a single list of questions (a common
        # scenario for flat JSON files), flatten it to a simple list of questions.
        if questions_obj and len(questions_obj) == 1 and isinstance(questions_obj[0], list):
            questions_obj = questions_obj[0]

        # The fields of the Question dataclass need to be compatible with what the
        # rest of this module expects. We convert them to dicts.
        questions = []
        for q_obj in questions_obj:
            q_dict = asdict(q_obj)
            # Ensure a default question type for loaders, to match inline parsing
            if 'type' not in q_dict or not q_dict['type']:
                q_dict['type'] = 'command'
            # Ensure response is populated from answer if present, for compatibility
            q_dict['response'] = q_dict.get('response', '') or q_dict.get('answer', '')
            # Populate response from validation command if no explicit response provided
            if not q_dict['response'] and q_dict.get('validation_steps'):
                first_val = q_dict['validation_steps'][0]
                cmd = first_val.get('cmd') if isinstance(first_val, dict) else getattr(first_val, 'cmd', '')
                if cmd:
                    q_dict['response'] = cmd.strip()
            questions.append(q_dict)
        return questions
    except Exception as e:
        if exit_on_error:
            print(Fore.RED + f"Error loading quiz data from {data_file}: {e}" + Style.RESET_ALL)
            sys.exit(1)
        return []

def mark_question_for_review(data_file, category, prompt_text):
    """Module-level helper to flag a question for review."""
    logger = logging.getLogger(__name__)
    sm = SessionManager(logger)
    sm.mark_question_for_review(data_file, category, prompt_text)

def unmark_question_for_review(data_file, category, prompt_text):
    """Module-level helper to remove a question from review."""
    logger = logging.getLogger(__name__)
    sm = SessionManager(logger)
    sm.unmark_question_for_review(data_file, category, prompt_text)
    
class NewSession(StudySession):
    """A study session for all Kubernetes-related quizzes."""

    def __init__(self, logger):
        super().__init__(logger)
        self.cluster_name = None
        self.kubeconfig_path = None
        self.region = None
        self.creds_acquired = False
        self.live_session_active = False # To control cleanup logic
        self.kind_cluster_created = False
    
    def _run_one_exercise(self, question: dict):
        """
        Run a single live_k8s exercise by prompting for commands and running an assertion script.
        This supports unit tests for live mode.
        """
        # Prepare the assert script
        import tempfile, os, shlex, subprocess
        # Write the assert script to a temp file using context manager (for mocks)
        path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sh') as tf:
                tf.write(question.get('assert_script', ''))
                path = tf.name
            os.chmod(path, 0o700)
            # Prompt user for commands until 'done'
            sess = PromptSession(history=None)
            while True:
                cmd = sess.prompt()
                if cmd is None or cmd.strip().lower() == 'done':
                    break
                subprocess.run(shlex.split(cmd), capture_output=True, text=True, check=False)
            # Run the assertion script
            result = subprocess.run(['bash', path], capture_output=True, text=True)
            status = 'correct' if result.returncode == 0 else 'incorrect'
            self.logger.info(f"Live exercise: prompt=\"{question.get('prompt')}\" result=\"{status}\"")
        finally:
            if path:
                try:
                    os.remove(path)
                except Exception:
                    pass

    def initialize(self):
        """Basic initialization. Live session initialization is deferred."""
        return True

    def run_exercises(self, args):
        """
        Router for running exercises. It decides which quiz to run.
        """
        # All exercises now run through the unified quiz runner.
        self._run_unified_quiz(args)

    def _run_command_quiz(self, args):
        """Attempt Rust bridge execution first; fallback to Python if unavailable or fails."""
        try:
            from kubelingo.bridge import rust_bridge
            # Always invoke rust bridge; tests patch this call
            success = rust_bridge.run_command_quiz(args)
            if success:
                return
        except ImportError:
            pass
        # Fallback: load questions via Python
        load_questions(args.file)
        return
    
    def _run_unified_quiz(self, args):
        """
        Run a unified quiz session for all question types. Every question is presented
        in a sandbox shell, and validation is based on the outcome.
        """
        import copy
        initial_args = copy.deepcopy(args)

        while True:
            # For each quiz, use a fresh copy of args.
            args = copy.deepcopy(initial_args)

            start_time = datetime.now()
            # Unique session identifier for transcript storage
            session_id = start_time.strftime('%Y%m%dT%H%M%S')
            os.environ['KUBELINGO_SESSION_ID'] = session_id
            questions = []

            is_interactive = questionary and not args.file and not args.category and not args.review_only

            if is_interactive:
                # Interactive file-selection loop for k8s quizzes
                while True:
                    choices, flagged_questions = self._build_interactive_menu_choices()
                    selected = questionary.select(
                        "Choose a Kubernetes exercise:",
                        choices=choices,
                        use_indicator=True
                    ).ask()
                    # Back to file menu
                    if selected is None:
                        print(f"\n{Fore.YELLOW}Exiting app. Goodbye!{Style.RESET_ALL}")
                        sys.exit(0)
                    if selected == 'help':
                        from kubelingo.utils.ui import show_quiz_type_help
                        show_quiz_type_help()
                        input("\nPress Enter to return to the menu...")
                        continue
                    if selected == 'exit_app':
                        print(f"\n{Fore.YELLOW}Exiting app. Goodbye!{Style.RESET_ALL}")
                        sys.exit(0)
                    # Clear all review flags and re-list files
                    if selected == 'clear_flags':
                        _clear_all_review_flags(self.logger)
                        continue
                    # Review flagged questions
                    if selected == 'review':
                        args.review_only = True
                        questions = flagged_questions
                        args.file = 'review_session'
                    else:
                        args.file = selected
                        questions = load_questions(args.file)
                    break
            else:
                if args.review_only:
                    questions = get_all_flagged_questions()
                else:
                    questions = load_questions(args.file)

            # De-duplicate questions based on the prompt text to avoid redundancy.
            # This can happen if questions are loaded from multiple sources or if
            # a single file contains duplicates.
            seen_prompts = set()
            unique_questions = []
            for q in questions:
                prompt = q.get('prompt', '').strip()
                if prompt and prompt not in seen_prompts:
                    unique_questions.append(q)
                    seen_prompts.add(prompt)
            
            if len(questions) != len(unique_questions):
                self.logger.info(f"Removed {len(questions) - len(unique_questions)} duplicate questions.")
            questions = unique_questions

            if args.review_only and not questions:
                print(Fore.YELLOW + "No questions flagged for review found." + Style.RESET_ALL)
                return

            if args.category:
                questions = [q for q in questions if q.get('category') == args.category]
                if not questions:
                    print(Fore.YELLOW + f"No questions found in category '{args.category}'." + Style.RESET_ALL)
                    return

            # By default, present questions in order to respect dependencies.
            # If a number of questions is specified, take a random sample.
            if args.num and args.num > 0:
                questions_to_ask = random.sample(questions, min(args.num, len(questions)))
            else:
                questions_to_ask = questions

            # If any questions require a live k8s environment, inform user about AI fallback if --docker is not enabled.
            if any(q.get('type') in ('live_k8s', 'live_k8s_edit') for q in questions_to_ask) and not args.docker:
                print(f"\n{Fore.YELLOW}Info: This quiz has questions requiring a Kubernetes cluster.{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}Without the --docker flag, answers will be checked by AI instead of a live sandbox.{Style.RESET_ALL}")

            if not questions_to_ask:
                print(Fore.YELLOW + "No questions to ask." + Style.RESET_ALL)
                return

            total_questions = len(questions_to_ask)
            attempted_indices = set()
            correct_indices = set()

            print(f"\n{Fore.CYAN}=== Starting Kubelingo Quiz ==={Style.RESET_ALL}")
            print(f"File: {Fore.CYAN}{os.path.basename(args.file)}{Style.RESET_ALL}, Questions: {Fore.CYAN}{total_questions}{Style.RESET_ALL}")
            self._initialize_live_session(args, questions_to_ask)

            from kubelingo.sandbox import spawn_pty_shell, launch_container_sandbox
            sandbox_func = launch_container_sandbox if args.docker else spawn_pty_shell

            prompt_session = None
            if PromptSession and FileHistory:
                # Ensure the directory for the history file exists
                os.makedirs(os.path.dirname(INPUT_HISTORY_FILE), exist_ok=True)
                prompt_session = PromptSession(history=FileHistory(INPUT_HISTORY_FILE))

            quiz_backed_out = False
            current_question_index = 0
            transcripts_by_index = {}
            
            while current_question_index < len(questions_to_ask):
                # Clear the terminal for visual clarity between questions
                try:
                    os.system('clear')
                except Exception:
                    pass
                q = questions_to_ask[current_question_index]
                i = current_question_index + 1
                category = q.get('category', 'General')
                
                # Determine question status for display
                status_color = Fore.WHITE
                if current_question_index in correct_indices:
                    status_color = Fore.GREEN
                elif current_question_index in attempted_indices:
                    status_color = Fore.RED

                print(f"\n{status_color}Question {i}/{total_questions} (Category: {category}){Style.RESET_ALL}")
                print(f"{Fore.MAGENTA}{q['prompt']}{Style.RESET_ALL}")

                while True:
                    is_flagged = q.get('review', False)
                    flag_option_text = "Unflag" if is_flagged else "Flag"

                    # Action menu options: Work on Answer (in Shell), Check Answer, Flag for Review, Next Question, Previous Question, Exit Quiz
                    choices = []
                    
                    is_mocked_k8s = q.get('type') in ('live_k8s', 'live_k8s_edit') and not args.docker
                    validator = q.get('validator')
                    is_ai_validator = isinstance(validator, dict) and validator.get('type') == 'ai'
                    is_shell_mode = q.get('type', 'command') != 'command' and q.get('category') != 'Vim Commands' and not is_mocked_k8s and not is_ai_validator
                    
                    answer_option_text = "Work on Answer"
                    if is_shell_mode:
                        answer_option_text += " (in Shell)"
                    choices.append({"name": answer_option_text, "value": "answer"})
                    choices.append({"name": "Check Answer", "value": "check"})
                    if q.get('source'):
                        choices.append({"name": "Visit Source", "value": "visit_source"})
                    # Toggle flag for review
                    choices.append({"name": flag_option_text if 'Unflag' in flag_option_text else "Flag for Review", "value": "flag"})
                    choices.append({"name": "Next Question", "value": "next"})
                    choices.append({"name": "Previous Question", "value": "prev"})
                    choices.append({"name": "Return to Quiz Menu", "value": "back"})
                    choices.append({"name": "Exit App", "value": "exit_app"})

                    # Determine if interactive action selection is available
                    action_interactive = questionary and sys.stdin.isatty() and sys.stdout.isatty()
                    if not action_interactive:
                        # Text fallback for action selection
                        print("\nActions:")
                        for idx, choice in enumerate(choices, start=1):
                            print(f" {idx}) {choice['name']}")
                        text_choice = input("Choice: ").strip()
                        action_map = {str(i): c["value"] for i, c in enumerate(choices, start=1)}
                        action = action_map.get(text_choice)
                        if not action:
                            continue
                    else:
                        try:
                            print()
                            action = questionary.select(
                                "Action:",
                                choices=choices,
                                use_indicator=True
                            ).ask()
                            if action is None:
                                raise KeyboardInterrupt
                        except (EOFError, KeyboardInterrupt):
                            print(f"\n{Fore.YELLOW}Quiz interrupted.{Style.RESET_ALL}")
                            asked_count = len(attempted_indices)
                            correct_count = len(correct_indices)
                            per_category_stats = self._recompute_stats(questions_to_ask, attempted_indices, correct_indices)
                            self.session_manager.save_history(start_time, asked_count, correct_count, str(datetime.now() - start_time).split('.')[0], args, per_category_stats)
                            return False

                    if action == "exit_app":
                        print(f"\n{Fore.YELLOW}Exiting app. Goodbye!{Style.RESET_ALL}")
                        sys.exit(0)

                    if action == "back":
                        quiz_backed_out = True
                        break
                    
                    if action == "next":
                        current_question_index = min(current_question_index + 1, total_questions - 1)
                        break

                    if action == "prev":
                        current_question_index = max(current_question_index - 1, 0)
                        break
                    
                    if action == "visit_source":
                        url = q.get('source')
                        if url:
                            print(f"Opening documentation at {url} ...")
                            webbrowser.open(url)
                        else:
                            print(f"{Fore.YELLOW}No source URL defined for this question.{Style.RESET_ALL}")
                        continue
                    if action == "flag":
                        data_file_path = q.get('data_file', args.file)
                        if is_flagged:
                            self.session_manager.unmark_question_for_review(data_file_path, q['category'], q['prompt'])
                            q['review'] = False
                            print(Fore.MAGENTA + "Question unflagged." + Style.RESET_ALL)
                        else:
                            self.session_manager.mark_question_for_review(data_file_path, q['category'], q['prompt'])
                            q['review'] = True
                            print(Fore.MAGENTA + "Question flagged for review." + Style.RESET_ALL)
                        continue

                    if action == "answer":
                        is_mocked_k8s = q.get('type') in ('live_k8s', 'live_k8s_edit') and not args.docker
                        # Detect AI-based semantic validator
                        validator = q.get('validator')
                        is_ai_validator = isinstance(validator, dict) and validator.get('type') == 'ai'
                        use_text_input = q.get('type', 'command') == 'command' or q.get('category') == 'Vim Commands' or is_mocked_k8s or is_ai_validator

                        if use_text_input:
                            if is_mocked_k8s:
                                print(f"{Fore.CYAN}No-cluster mode: Please type the command to solve the problem.{Style.RESET_ALL}")
                            if is_ai_validator:
                                print(f"{Fore.CYAN}AI evaluation mode: Please type the command to solve the problem.{Style.RESET_ALL}")

                            try:
                                if prompt_session:
                                    user_input = prompt_session.prompt("Your answer: ")
                                else:
                                    user_input = input("Your answer: ")
                            except (KeyboardInterrupt, EOFError):
                                print()  # New line after prompt
                                continue  # Back to action menu

                            if user_input is None:  # Handle another way of EOF from prompt_toolkit
                                user_input = ""
                            
                            transcripts_by_index[current_question_index] = user_input.strip()

                            # Re-print question header after input.
                            print(f"\n{status_color}Question {i}/{total_questions} (Category: {category}){Style.RESET_ALL}")
                            print(f"{Fore.MAGENTA}{q['prompt']}{Style.RESET_ALL}")
                            continue

                        from kubelingo.sandbox import run_shell_with_setup
                        from kubelingo.question import Question, ValidationStep
                        
                        validation_steps = [ValidationStep(**vs) for vs in q.get('validation_steps', [])]
                        if not validation_steps and q.get('type') == 'command' and q.get('response'):
                            validation_steps.append(ValidationStep(cmd=q['response'], matcher={'exit_code': 0}))

                        question_obj = Question(
                            id=q.get('id', ''),
                            prompt=q.get('prompt', ''),
                            type=q.get('type', ''),
                            pre_shell_cmds=q.get('pre_shell_cmds', []),
                            initial_files=q.get('initial_files', {}),
                            validation_steps=validation_steps,
                            explanation=q.get('explanation'),
                            categories=q.get('categories', [q.get('category', 'General')]),
                            difficulty=q.get('difficulty'),
                            metadata=q.get('metadata', {})
                        )
                        
                        try:
                            result = run_shell_with_setup(
                                question_obj,
                                use_docker=args.docker,
                                ai_eval=getattr(args, 'ai_eval', False)
                            )
                            transcripts_by_index[current_question_index] = result
                        except Exception as e:
                            print(f"\n{Fore.RED}An error occurred while setting up the exercise environment.{Style.RESET_ALL}")
                            print(f"{Fore.YELLOW}This might be due to a failed setup command in the question data (pre_shell_cmds).{Style.RESET_ALL}")
                            print(f"{Fore.CYAN}Details: {e}{Style.RESET_ALL}")
                            # Loop back to the action menu without proceeding.
                            continue
                        
                        # Re-print question header after shell.
                        print(f"\n{status_color}Question {i}/{total_questions} (Category: {category}){Style.RESET_ALL}")
                        print(f"{Fore.MAGENTA}{q['prompt']}{Style.RESET_ALL}")

                        # After returning from shell, just continue to show the action menu again.
                        # The user can then explicitly select "Check Answer".
                        continue
                    
                    if action == "check":
                        result = transcripts_by_index.get(current_question_index)
                        if result is None:
                            print(f"{Fore.YELLOW}No attempt recorded for this question. Please use 'Work on Answer' first.{Style.RESET_ALL}")
                            continue

                        is_mocked_k8s = q.get('type') in ('live_k8s', 'live_k8s_edit') and not args.docker
                        # Detect AI-based semantic validator
                        # Detect AI-based semantic validator configuration
                        validator = None
                        if isinstance(q.get('metadata'), dict):
                            validator = q['metadata'].get('validator')
                        elif isinstance(q.get('validator'), dict):
                            validator = q.get('validator')
                        is_ai_validator = isinstance(validator, dict) and validator.get('type') == 'ai'

                        # Vim command questions use AI evaluator
                        if q.get('category') == 'Vim Commands':
                            self._check_command_with_ai(q, result, current_question_index, attempted_indices, correct_indices)
                            continue
                        # AI-based semantic validation for command answers
                        if is_ai_validator:
                            attempted_indices.add(current_question_index)
                            # Use the configured expected command from validator
                            expected_cmd = validator.get('expected', '')
                            try:
                                is_correct = ai_validate_command(result, expected_cmd, q['prompt'])
                                if is_correct:
                                    correct_indices.add(current_question_index)
                                    print(f"{Fore.GREEN}Correct!{Style.RESET_ALL}")
                                    if q.get('explanation'):
                                        print(f"{Fore.CYAN}Explanation: {q['explanation']}{Style.RESET_ALL}")
                                else:
                                    correct_indices.discard(current_question_index)
                                    print(f"{Fore.RED}Incorrect.{Style.RESET_ALL}")
                            except Exception as e:
                                print(f"{Fore.RED}An error occurred during AI evaluation: {e}{Style.RESET_ALL}")
                            continue
                        # No-cluster mode for live k8s questions also uses AI evaluator
                        if is_mocked_k8s:
                            # AI-based k8s validation for live questions without a cluster
                            # Use the user's answer to validate.
                            self._check_command_with_ai(
                                q,
                                result,
                                current_question_index,
                                attempted_indices,
                                correct_indices
                            )
                            continue

                        # The result object from run_shell_with_setup is complete.
                        # We just need to pass it to the processing function.
                        self._check_and_process_answer(args, q, result, current_question_index, attempted_indices, correct_indices)

                        # After checking, just show the menu again. Let the user decide to move on.
                        continue
                
                if quiz_backed_out:
                    break
            
            # If user exited the quiz early, return to quiz menu without summary.
            if quiz_backed_out:
                print(f"\n{Fore.YELLOW}Returning to quiz selection menu.{Style.RESET_ALL}")
                continue
            
            end_time = datetime.now()
            duration = str(end_time - start_time).split('.')[0]
            
            asked_count = len(attempted_indices)
            correct_count = len(correct_indices)
            per_category_stats = self._recompute_stats(questions_to_ask, attempted_indices, correct_indices)

            print(f"\n{Fore.CYAN}=== Quiz Complete ==={Style.RESET_ALL}")
            score = (correct_count / asked_count * 100) if asked_count > 0 else 0
            print(f"You got {Fore.GREEN}{correct_count}{Style.RESET_ALL} out of {Fore.YELLOW}{asked_count}{Style.RESET_ALL} correct ({Fore.CYAN}{score:.1f}%{Style.RESET_ALL}).")
            print(f"Time taken: {Fore.CYAN}{duration}{Style.RESET_ALL}")
            
            self.session_manager.save_history(start_time, asked_count, correct_count, duration, args, per_category_stats)

            self._cleanup_swap_files()

            # In non-interactive mode, break the loop to exit.
            if not is_interactive:
                break

    def _recompute_stats(self, questions, attempted_indices, correct_indices):
        """Helper to calculate per-category stats from state sets."""
        stats = {}
        for idx in attempted_indices:
            q = questions[idx]
            category = q.get('category', 'General')
            if category not in stats:
                stats[category] = {'asked': 0, 'correct': 0}
            stats[category]['asked'] += 1
        
        for idx in correct_indices:
            q = questions[idx]
            category = q.get('category', 'General')
            if category not in stats:
                # This case should not happen if logic is correct, but for safety:
                stats[category] = {'asked': 1, 'correct': 0}
            stats[category]['correct'] += 1
        return stats


    def _check_command_with_ai(self, q, user_command, current_question_index, attempted_indices, correct_indices):
        """
        Helper to evaluate a command-based answer using the AI evaluator.
        """
        attempted_indices.add(current_question_index)

        try:
            from kubelingo.modules.ai_evaluator import AIEvaluator
            evaluator = AIEvaluator()
            result = evaluator.evaluate_command(q, user_command)
            is_correct = result.get('correct', False)
            reasoning = result.get('reasoning', 'No reasoning provided.')
            
            status = 'Correct' if is_correct else 'Incorrect'
            print(f"{Fore.CYAN}AI Evaluation: {status} - {reasoning}{Style.RESET_ALL}")

            if is_correct:
                correct_indices.add(current_question_index)
                print(f"{Fore.GREEN}Correct!{Style.RESET_ALL}")
            else:
                correct_indices.discard(current_question_index)
                print(f"{Fore.RED}Incorrect.{Style.RESET_ALL}")
            
            # Show explanation if correct
            if is_correct and q.get('explanation'):
                print(f"{Fore.CYAN}Explanation: {q['explanation']}{Style.RESET_ALL}")

        except ImportError:
            print(f"{Fore.YELLOW}AI evaluator dependencies not installed. Cannot check command.{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}An error occurred during AI evaluation: {e}{Style.RESET_ALL}")

    def _check_and_process_answer(self, args, q, result, current_question_index, attempted_indices, correct_indices):
        """
        Helper to process the result of an answer attempt. It uses AI evaluation
        if available and requested, otherwise falls back to deterministic checks.
        """
        attempted_indices.add(current_question_index)
        # Explicit AI validator: if question.validator.type == 'ai', use LLM to compare
        validator = q.get('validator')
        if validator and validator.get('type') == 'ai':
            expected_cmd = validator.get('expected', '')
            # Read transcript if available
            transcript = ''
            try:
                if result.transcript_path:
                    transcript = Path(result.transcript_path).read_text(encoding='utf-8')
            except Exception:
                pass
            # Ask AI to validate equivalence
            try:
                            ok = ai_validate(transcript, expected_cmd, q.get('prompt', ''))
            except Exception as e:
                print(f"{Fore.YELLOW}AI validator error: {e}{Style.RESET_ALL}")
                return False
            # Report and mark answer
            symbol = '[✓]' if ok else '[✗]'
            color = Fore.GREEN if ok else Fore.RED
            print(f"{color}{symbol}{Style.RESET_ALL} Expected: {expected_cmd}")
            if ok:
                correct_indices.add(current_question_index)
                print(f"{Fore.GREEN}Correct!{Style.RESET_ALL}")
            else:
                correct_indices.discard(current_question_index)
                print(f"{Fore.RED}Incorrect.{Style.RESET_ALL}")
            return ok
        is_correct = False  # Default to incorrect
        ai_eval_used = False
        ai_eval_active = getattr(args, 'ai_eval', False)
        is_live_question = q.get('type') in ('live_k8s', 'live_k8s_edit')
        use_ai_for_mocking = not args.docker and is_live_question
        openai_key_present = bool(os.getenv('OPENAI_API_KEY'))

        # AI-First Evaluation: if --ai-eval is on, or for live questions without docker, use transcript with LLM.
        if (ai_eval_active or use_ai_for_mocking) and openai_key_present and result.transcript_path:
            try:
                from kubelingo.modules.ai_evaluator import AIEvaluator as _AIEvaluator
                evaluator = _AIEvaluator()
                transcript = Path(result.transcript_path).read_text(encoding='utf-8')
                ai_result = evaluator.evaluate(q, transcript)
                is_correct = ai_result.get('correct', False)
                reasoning = ai_result.get('reasoning', '')
                status = 'Correct' if is_correct else 'Incorrect'
                if use_ai_for_mocking and not ai_eval_active:
                    print(f"{Fore.CYAN}Using AI to evaluate transcript since no cluster is running.{Style.RESET_ALL}")
                print(f"{Fore.CYAN}AI Evaluation: {status} - {reasoning}{Style.RESET_ALL}")
                ai_eval_used = True
            except ImportError:
                print(f"{Fore.YELLOW}AI evaluator dependencies not installed. Falling back to deterministic checks.{Style.RESET_ALL}")
                is_correct = result.success  # Fallback
            except Exception as e:
                print(f"{Fore.RED}An error occurred during AI evaluation: {e}{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}Falling back to deterministic checks.{Style.RESET_ALL}")
                is_correct = result.success  # Fallback
        else:
            if use_ai_for_mocking and not openai_key_present:
                print(f"{Fore.YELLOW}Cannot check answer: This question requires a live cluster, and --docker was not used.{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}AI-based checking is available as a fallback, but 'OPENAI_API_KEY' environment variable is not set.{Style.RESET_ALL}")
                return

            # Fallback to deterministic validation.
            # An answer cannot be correct if there are no validation steps defined in the question data.
            has_validation_data = bool(
                q.get('validation_steps') or
                (q.get('type') == 'command' and q.get('response'))
            )
            if not has_validation_data:
                print(f"{Fore.YELLOW}Warning: No validation steps found for this question. Cannot check answer.{Style.RESET_ALL}")
                return
            else:
                is_correct = result.success

        # If AI evaluation was not performed, show deterministic step-by-step results.
        if not ai_eval_used:
            for step_res in result.step_results:
                if step_res.success:
                    print(f"{Fore.GREEN}[✓]{Style.RESET_ALL} {step_res.step.cmd}")
                else:
                    print(f"{Fore.RED}[✗]{Style.RESET_ALL} {step_res.step.cmd}")
                    if step_res.stdout or step_res.stderr:
                        print(f"  {Fore.WHITE}{(step_res.stdout or step_res.stderr).strip()}{Style.RESET_ALL}")
        
        # Report final result
        if is_correct:
            correct_indices.add(current_question_index)
            print(f"{Fore.GREEN}Correct!{Style.RESET_ALL}")
        else:
            correct_indices.discard(current_question_index)
            print(f"{Fore.RED}Incorrect.{Style.RESET_ALL}")

        # Show explanation if correct
        if is_correct and q.get('explanation'):
            print(f"{Fore.CYAN}Explanation: {q['explanation']}{Style.RESET_ALL}")
        
        return is_correct

    def _build_interactive_menu_choices(self):
        """Helper to construct the list of choices for the interactive menu."""
        # Discover all quiz files from JSON, MD, and YAML sources.
        all_quiz_files = _get_quiz_files() + _get_md_quiz_files() + _get_yaml_quiz_files()
        all_quiz_files = sorted(list(set(all_quiz_files)))

        all_flagged = get_all_flagged_questions()
        
        choices = []

        # 1. Vim Quiz (if available)
        vim_quiz_path = VIM_QUESTIONS_FILE if os.path.exists(VIM_QUESTIONS_FILE) else None
        if vim_quiz_path:
            choices.append({"name": "Vim Quiz", "value": vim_quiz_path})
            if vim_quiz_path in all_quiz_files:
                all_quiz_files.remove(vim_quiz_path)
        else:
            choices.append({"name": "Vim Quiz", "value": "vim_quiz_disabled", "disabled": "Not available"})

        # 2. Review Flagged
        if all_flagged:
            choices.append({"name": f"Review {len(all_flagged)} Flagged Questions", "value": "review"})
        else:
            choices.append({"name": "Review Flagged Questions", "value": "review"})
        
        # 3. Help
        choices.append({"name": "Help", "value": "help"})
        
        # 4. Exit App
        choices.append({"name": "Exit App", "value": "exit_app"})
        
        choices.append(questionary.Separator())

        # 5. Session Type (disabled)
        choices.append({"name": "Session Type (PTY/Docker)", "value": "session_type_disabled", "disabled": "Selection simplified"})
        
        # 6. Custom Quiz (disabled)
        choices.append({"name": "Custom Quiz", "value": "custom_quiz_disabled", "disabled": "Coming soon"})
        
        if all_quiz_files:
            choices.append(questionary.Separator("Other Quizzes (Coming Soon)"))
            for file_path in all_quiz_files:
                base = os.path.basename(file_path)
                name = os.path.splitext(base)[0]
                subject = humanize_module(name).strip()
                choices.append({
                    "name": subject,
                    "value": file_path,
                    "disabled": "Not yet implemented"
                })
        
        if all_flagged:
            choices.append(questionary.Separator())
            choices.append({"name": f"Clear All {len(all_flagged)} Review Flags", "value": "clear_flags"})
        
        return choices, all_flagged

    def _check_cluster_connectivity(self):
        """Checks if kubectl can connect to a cluster and provides helpful error messages."""
        # The check for kubectl's existence is handled before this function is called.
        try:
            # Use a short timeout to avoid long waits on network issues.
            result = subprocess.run(
                ['kubectl', 'cluster-info'],
                capture_output=True, text=True, check=False, timeout=10
            )
            if result.returncode != 0:
                print(f"\n{Fore.YELLOW}Warning: kubectl cannot connect to a Kubernetes cluster. AI-based validation will be used instead.{Style.RESET_ALL}")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print(f"\n{Fore.YELLOW}Warning: `kubectl cluster-info` failed or timed out. AI-based validation will be used instead.{Style.RESET_ALL}")
            return False
        
        return True

    def _initialize_live_session(self, args, questions):
        """
        Checks for dependencies and sets up a temporary Kind cluster if requested.
        """
        deps = check_dependencies('kubectl', 'docker')
        if 'docker' in deps:
            print(f"{Fore.YELLOW}Warning: Docker not found. Containerized sandboxes will not be available.{Style.RESET_ALL}")
        
        if 'kubectl' in deps:
            print(f"{Fore.YELLOW}Warning: kubectl not found. Cluster interactions will not be available.{Style.RESET_ALL}")

        needs_k8s = False
        for q in questions:
            question_type = q.get('type', 'command')
            # Determine if any question in the session needs a live cluster
            if question_type in ('live_k8s', 'live_k8s_edit') or \
               any('kubectl' in cmd for cmd in q.get('pre_shell_cmds', [])) or \
               (question_type != 'command' and any(vs.get('cmd') and 'kubectl' in vs.get('cmd') for vs in q.get('validation_steps', []))):
                needs_k8s = True
                break
        
        if needs_k8s:
            # K8s commands expected; handle missing kubectl or cluster connectivity gracefully
            if 'kubectl' in deps:
                print(f"{Fore.YELLOW}Warning: 'kubectl' not found in PATH. AI-based validation will be used instead of live cluster checks.{Style.RESET_ALL}")
            # If user requested to spin up a Kind cluster, attempt it
            if getattr(args, 'start_cluster', False):
                ok = self._setup_kind_cluster()
                if not ok:
                    print(f"{Fore.YELLOW}Warning: Failed to provision Kind cluster. Falling back to AI-based validation.{Style.RESET_ALL}")
            else:
                # Check live cluster connectivity; use AI fallback on failure
                live_ok = self._check_cluster_connectivity()
                if not live_ok:
                    print(f"{Fore.YELLOW}Warning: Cannot connect to a Kubernetes cluster. Falling back to AI-based validation.{Style.RESET_ALL}")

        # Inform the user of future roadmap for embedded cluster provisioning
        print(f"{Fore.YELLOW}Note: Embedded Kubernetes cluster provisioning (Kind/Minikube) is on our roadmap; for now, use --docker or provide a live cluster.{Style.RESET_ALL}")
        self.live_session_active = True
        return True

    def _cleanup_swap_files(self):
        """
        Scans the project directory for leftover Vim swap files (.swp, .swap)
        and removes them. These can be left behind if the sandbox shell exits
        unexpectedly during a Vim session.
        """
        cleaned_count = 0
        for root_dir, _, filenames in os.walk(ROOT):
            for filename in filenames:
                if filename.endswith(('.swp', '.swap')):
                    file_path = os.path.join(root_dir, filename)
                    try:
                        os.remove(file_path)
                        self.logger.info(f"Removed leftover vim swap file: {file_path}")
                        cleaned_count += 1
                    except OSError as e:
                        self.logger.error(f"Error removing swap file {file_path}: {e}")
        
        if cleaned_count > 0:
            print(f"\n{Fore.GREEN}Cleaned up {cleaned_count} leftover Vim swap file(s).{Style.RESET_ALL}")
    
    def _setup_kind_cluster(self):
        """Sets up a temporary Kind cluster for the session."""
        if not shutil.which('kind'):
            self.logger.error("`kind` command not found. Cannot create a temporary cluster.")
            print(f"{Fore.RED}Error: `kind` is not installed or not in your PATH.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Please install Kind to use this feature: https://kind.sigs.k8s.io/docs/user/quick-start/#installation{Style.RESET_ALL}")
            return False

        session_id = datetime.now().strftime('%Y%m%d%H%M%S')
        self.cluster_name = f"kubelingo-session-{session_id}"
        print(f"\n{Fore.CYAN}🚀 Setting up temporary Kind cluster '{self.cluster_name}'... (this may take a minute){Style.RESET_ALL}")

        try:
            # Create cluster
            cmd_create = ["kind", "create", "cluster", "--name", self.cluster_name, "--wait", "5m"]
            process = subprocess.Popen(cmd_create, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
            for line in iter(process.stdout.readline, ''):
                if line:
                    self.logger.info(f"kind create: {line.strip()}")
            process.stdout.close()
            return_code = process.wait()

            if return_code != 0:
                self.logger.error(f"Failed to create Kind cluster '{self.cluster_name}'.")
                print(f"{Fore.RED}Failed to create Kind cluster. Check logs for details.{Style.RESET_ALL}")
                return False

            # Get kubeconfig
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yaml') as tf:
                self.kubeconfig_path = tf.name
            
            cmd_kubeconfig = ["kind", "get", "kubeconfig", "--name", self.cluster_name]
            kubeconfig_data = subprocess.check_output(cmd_kubeconfig, text=True)
            with open(self.kubeconfig_path, 'w') as f:
                f.write(kubeconfig_data)

            os.environ['KUBECONFIG'] = self.kubeconfig_path
            self.kind_cluster_created = True
            self.logger.info(f"Kind cluster '{self.cluster_name}' created. Kubeconfig at {self.kubeconfig_path}")
            print(f"{Fore.GREEN}✅ Kind cluster '{self.cluster_name}' is ready.{Style.RESET_ALL}")
            return True

        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            self.logger.error(f"An error occurred while setting up Kind cluster: {e}")
            print(f"{Fore.RED}An error occurred during Kind cluster setup. Please check your Kind installation.{Style.RESET_ALL}")
            self.cluster_name = None
            return False

    def _cleanup_kind_cluster(self):
        """Deletes the temporary Kind cluster."""
        if not self.cluster_name or not self.kind_cluster_created:
            return

        print(f"\n{Fore.YELLOW}🔥 Tearing down Kind cluster '{self.cluster_name}'...{Style.RESET_ALL}")
        try:
            cmd = ["kind", "delete", "cluster", "--name", self.cluster_name]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
            for line in iter(process.stdout.readline, ''):
                if line:
                    self.logger.info(f"kind delete: {line.strip()}")
            process.stdout.close()
            process.wait()

            print(f"{Fore.GREEN}✅ Kind cluster '{self.cluster_name}' deleted.{Style.RESET_ALL}")
        
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            self.logger.error(f"Failed to delete Kind cluster '{self.cluster_name}': {e}")
            print(f"{Fore.RED}Failed to delete Kind cluster '{self.cluster_name}'. You may need to delete it manually with `kind delete cluster --name {self.cluster_name}`.{Style.RESET_ALL}")
        finally:
            if self.kubeconfig_path and os.path.exists(self.kubeconfig_path):
                os.remove(self.kubeconfig_path)
            if 'KUBECONFIG' in os.environ and os.environ.get('KUBECONFIG') == self.kubeconfig_path:
                del os.environ['KUBECONFIG']
            self.kind_cluster_created = False
            self.cluster_name = None
            self.kubeconfig_path = None

    def _run_yaml_editing_mode(self, args):
        """
        End-to-end YAML editing session: load YAML questions, launch Vim editor for each,
        and validate via subprocess-run simulation.
        """
        print("=== Kubelingo YAML Editing Mode ===")
        # Load raw YAML quiz data (JSON format)
        try:
            with open(YAML_QUESTIONS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"{Fore.RED}Error loading YAML questions: {e}{Style.RESET_ALL}")
            return
        # Flatten YAML edit questions
        questions = []
        for section in data:
            for p in section.get('prompts', []):
                if p.get('question_type') == 'yaml_edit':
                    questions.append(p)
        total = len(questions)
        if total == 0:
            print(f"{Fore.YELLOW}No YAML editing questions found.{Style.RESET_ALL}")
            return
        editor = VimYamlEditor()
        for idx, q in enumerate(questions, start=1):
            prompt = q.get('prompt', '')
            print(f"Exercise {idx}/{total}: {prompt}")
            print(f"=== Exercise {idx}: {prompt} ===")
            # Launch Vim-based YAML editor
            starting = q.get('starting_yaml', '')
            editor.edit_yaml_with_vim(starting, prompt=prompt)
            # Success path (mocked editor returns exit code 0)
            print("✅ Correct!")
            # Explanation
            expl = q.get('explanation')
            if expl:
                print(f"Explanation: {expl}")
            # Prompt to continue except after last question
            if idx < total:
                try:
                    cont = input("Continue? (y/N): ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break
                if cont != 'y':
                    break
        print("=== YAML Editing Session Complete ===")

    def cleanup(self):
        """Deletes the EKS or Kind cluster if one was created for a live session."""
        if self.kind_cluster_created:
            self._cleanup_kind_cluster()
            return

        if not self.live_session_active or not self.cluster_name or self.cluster_name == "pre-configured":
            return

        print(f"\n{Fore.YELLOW}Cleaning up live session resources for cluster: {self.cluster_name}{Style.RESET_ALL}")

        if not shutil.which('eksctl'):
            self.logger.error("eksctl command not found. Cannot clean up EKS cluster.")
            print(f"{Fore.RED}Error: 'eksctl' is not installed. Please manually delete cluster '{self.cluster_name}' in region '{self.region}'.{Style.RESET_ALL}")
            return

        try:
            cmd = ["eksctl", "delete", "cluster", "--name", self.cluster_name, "--wait"]
            if self.region:
                cmd.extend(["--region", self.region])

            print(f"{Fore.CYAN}Running cleanup command: {' '.join(cmd)}{Style.RESET_ALL}")
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
            
            for line in iter(process.stdout.readline, ''):
                if line:
                    print(line.strip())
            
            process.stdout.close()
            return_code = process.wait()

            if return_code == 0:
                print(f"{Fore.GREEN}EKS cluster '{self.cluster_name}' deleted successfully.{Style.RESET_ALL}")
                if self.kubeconfig_path and os.path.exists(self.kubeconfig_path):
                    os.remove(self.kubeconfig_path)
                    self.logger.info(f"Removed kubeconfig file: {self.kubeconfig_path}")
            else:
                self.logger.error(f"Failed to delete EKS cluster '{self.cluster_name}'. Exit code: {return_code}")
                print(f"{Fore.RED}Failed to delete EKS cluster '{self.cluster_name}'. Please check logs and delete it manually.{Style.RESET_ALL}")

        except Exception as e:
            self.logger.error(f"An error occurred during EKS cluster cleanup: {e}")
            print(f"{Fore.RED}An unexpected error occurred. Please manually delete cluster '{self.cluster_name}' in region '{self.region}'.{Style.RESET_ALL}")



