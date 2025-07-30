import csv
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import shlex
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
from kubelingo.modules.base.loader import load_session
from kubelingo.modules.json_loader import JSONLoader
from kubelingo.modules.md_loader import MDLoader
from kubelingo.modules.yaml_loader import YAMLLoader
from dataclasses import asdict
from kubelingo.utils.validation import commands_equivalent
# Existing import
# Existing import
from .vim_yaml_editor import VimYamlEditor
from kubelingo.sandbox import spawn_pty_shell, launch_container_sandbox
# (AI integration is loaded dynamically to avoid import-time dependencies)


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
    all_quiz_files = \
        _get_quiz_files() + \
        _get_md_quiz_files() + \
        _get_yaml_quiz_files()

    if os.path.exists(VIM_QUESTIONS_FILE):
        all_quiz_files.append(VIM_QUESTIONS_FILE)

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
            if not q_dict['response'] and q_dict.get('validations'):
                first_val = q_dict['validations'][0]
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

    def initialize(self):
        """Basic initialization. Live session initialization is deferred."""
        return True

    def run_exercises(self, args):
        """
        Router for running exercises. It decides which quiz to run.
        """
        if args.live:
            return self._run_live_mode(args)

        # For non-live exercises, present all quizzes in a unified shell menu.
        self._run_command_quiz(args)
    
    def _run_shell_question(self, q: dict, args) -> bool:
        """
        Unified shell-driven question:
        1) Run any setup commands in q['initial_cmds'].
        2) Launch a PTY or Docker shell for the user to work in.
        3) After exit, execute each ValidationStep in q['validations'], returning
           True if all pass, False otherwise.
        """
        # 1) Setup
        for cmd in q.get('initial_cmds', []):
            subprocess.run(cmd, shell=True)

        # 2) Shell
        if args.docker:
            launch_container_sandbox()
        else:
            spawn_pty_shell()

        # 3) Validation
        all_good = True
        for v in q.get('validations', []):
            cmd = v.get('cmd', '')
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            expected = v.get('matcher', {}).get('exit_code', 0)
            if proc.returncode != expected:
                print(proc.stdout or proc.stderr)
                all_good = False
                break
        return all_good

    def _run_command_quiz(self, args):
        """Run a quiz session for command-line questions."""
        start_time = datetime.now()
        questions = []  # Defer loading until after menu

        # In interactive mode, prompt user for quiz type (flagged/category)
        is_interactive = (
            questionary and not args.category and not args.review_only and not args.num
            and (args.file is None or args.file == DEFAULT_DATA_FILE or not os.path.exists(args.file))
        )
        if is_interactive:
            while True:  # Loop to allow returning to menu after clearing flags
                choices, flagged_command_questions, flagged_vim_questions = self._build_interactive_menu_choices()

                selected = questionary.select(
                    "Choose a Kubernetes exercise:",
                    choices=choices,
                    use_indicator=True
                ).ask()

                if selected is None or selected == 'back':
                    print(f"\n{Fore.YELLOW}Quiz cancelled.{Style.RESET_ALL}")
                    return

                if selected == 'clear_flags':
                    _clear_all_review_flags(self.logger)
                    continue  # Re-display menu

                # Map menu selections to handler methods for cleaner dispatch
                action_map = {
                    'vim_review': self._run_vim_commands_quiz,
                    'yaml_standard': self._run_yaml_editing_mode,
                    'yaml_progressive': self._handle_yaml_progressive,
                    'yaml_live': self._handle_yaml_live,
                    'yaml_create': self._handle_yaml_create,
                    'vim_quiz': self._run_vim_commands_quiz
                }

                if selected in action_map:
                    args.review_only = (selected == 'vim_review')
                    action_map[selected](args)
                    continue

                # Handle cases that populate the `questions` list and fall through
                if selected == 'review':
                    args.review_only = True
                    questions = flagged_command_questions
                    args.file = 'review_session'  # Set a placeholder for history
                elif selected.endswith(('.json', '.md', '.markdown', '.yaml', '.yml')):
                    args.file = selected
                    questions = load_questions(args.file)
                else:
                    print(f"{Fore.RED}Internal error: unhandled selection '{selected}'{Style.RESET_ALL}")
                    return
                # --- Start Quiz ---
                if args.review_only and not questions:
                    print(Fore.YELLOW + "No questions flagged for review found." + Style.RESET_ALL)
                    continue

                if args.category:
                    questions = [q for q in questions if q.get('category') == args.category]
                    if not questions:
                        print(Fore.YELLOW + f"No questions found in category '{args.category}'." + Style.RESET_ALL)
                        continue

                runnable_questions = [q for q in questions if q.get('type', 'command') in ('command', 'live_k8s', 'live_k8s_edit')]
                if not runnable_questions:
                    print(Fore.YELLOW + "No runnable questions available for this quiz." + Style.RESET_ALL)
                    continue

                num_to_ask = args.num if args.num > 0 else len(runnable_questions)
                questions_to_ask = random.sample(runnable_questions, min(num_to_ask, len(runnable_questions)))

                if not questions_to_ask:
                    print(Fore.YELLOW + "No questions to ask." + Style.RESET_ALL)
                    continue

                correct_count = 0
                per_category_stats = {}
                total_questions = len(questions_to_ask)
                asked_count = 0
                skipped_questions = []

                print(f"\n{Fore.CYAN}=== Starting Kubelingo Quiz ==={Style.RESET_ALL}")
                print(f"File: {Fore.CYAN}{os.path.basename(args.file)}{Style.RESET_ALL}, Questions: {Fore.CYAN}{total_questions}{Style.RESET_ALL}")

                from kubelingo.sandbox import spawn_pty_shell, launch_container_sandbox
                
                prompt_session = None
                if PromptSession and FileHistory:
                    prompt_session = PromptSession(history=FileHistory(INPUT_HISTORY_FILE))
                
                quiz_backed_out = False
                current_question_index = 0
                while current_question_index < len(questions_to_ask):
                    q = questions_to_ask[current_question_index]
                    i = current_question_index + 1

                    category = q.get('category', 'General')
                    if category not in per_category_stats:
                        per_category_stats[category] = {'asked': 0, 'correct': 0}

                    user_answer_content = None
                    was_answered = False

                    # Inner loop for the in-quiz menu
                    print(f"\n{Fore.YELLOW}Question {i}/{total_questions} (Category: {category}){Style.RESET_ALL}")
                    print(f"{Fore.MAGENTA}{q['prompt']}{Style.RESET_ALL}")
                    while True:
                        is_flagged = q.get('review', False)
                        flag_option_text = "Unflag" if is_flagged else "Flag"
                        
                        q_type = q.get('type', 'command')
                        answer_text = "Answer (Enter Command)" if q_type == 'command' else "Answer (Open Terminal)"

                        choices = [
                            questionary.Choice(f"1. {answer_text}", value="answer"),
                            questionary.Choice(f"2. {flag_option_text}", value="flag"),
                            questionary.Choice("3. Skip", value="skip"),
                            questionary.Choice("4. Back to Quiz Menu", value="back")
                        ]
                        
                        try:
                            action = questionary.select("Action:", choices=choices, use_indicator=False).ask()
                            if action is None: raise KeyboardInterrupt
                        except (EOFError, KeyboardInterrupt):
                            print(f"\n{Fore.YELLOW}Quiz interrupted.{Style.RESET_ALL}")
                            self.session_manager.save_history(start_time, asked_count, correct_count, str(datetime.now() - start_time).split('.')[0], args, per_category_stats)
                            return

                        if action == "back":
                            quiz_backed_out = True
                            break
                        
                        if action == "skip":
                            if not was_answered:
                                per_category_stats[category]['asked'] += 1
                                asked_count += 1
                            skipped_questions.append(q)
                            self.logger.info(f"Question {i}/{total_questions}: SKIPPED prompt=\"{q['prompt']}\"")
                            current_question_index += 1
                            break

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
                            if not was_answered:
                                per_category_stats[category]['asked'] += 1
                                asked_count += 1
                            was_answered = True

                            is_correct = False
                            if q_type == 'command':
                                if prompt_session:
                                    user_answer_content = prompt_session.prompt(f'{Fore.CYAN}Your answer: {Style.RESET_ALL}').strip()
                                else:
                                    user_answer_content = input(f'{Fore.CYAN}Your answer: {Style.RESET_ALL}').strip()
                                is_correct = commands_equivalent(user_answer_content, q.get('response', ''))
                            else: # live_k8s, etc.
                                is_correct = self._run_shell_question(q, args)

                            self.logger.info(
                                f"Question {i}/{total_questions}: prompt=\"{q['prompt']}\" result=\"{'correct' if is_correct else 'incorrect'}\""
                            )
                            if is_correct:
                                correct_count += 1
                                per_category_stats[category]['correct'] += 1
                                print(f"{Fore.GREEN}Correct!{Style.RESET_ALL}")
                                if q.get('explanation'):
                                    print(f"{Fore.CYAN}Explanation: {q['explanation']}{Style.RESET_ALL}")
                                # AI explanation if enabled
                                from kubelingo.modules.llm.session import AIHelper
                                if getattr(AIHelper, 'enabled', False):
                                    ai_text = AIHelper().get_explanation(q)
                                    if ai_text:
                                        print(ai_text)
                                current_question_index += 1
                                break
                            else:
                                print(f"{Fore.RED}Incorrect.{Style.RESET_ALL}")
                                if q_type == 'command':
                                    print(f"{Fore.GREEN}Correct answer: {q.get('response', '')}{Style.RESET_ALL}")
                                # AI explanation if enabled
                                from kubelingo.modules.llm.session import AIHelper
                                if getattr(AIHelper, 'enabled', False):
                                    ai_text = AIHelper().get_explanation(q)
                                    if ai_text:
                                        print(ai_text)
                                continue

                        if action == "check":
                            if not was_answered:
                                if q_type == 'command':
                                    print(f"{Fore.GREEN}Correct answer: {q.get('response', '')}{Style.RESET_ALL}")
                                else:
                                    print(f"{Fore.YELLOW}Answer cannot be shown directly for this question type. Please attempt a solution first.{Style.RESET_ALL}")
                                continue

                            if q_type == 'command':
                                # Determine if comparing YAML manifest or command
                                expected_resp = (q.get('response', '') or '').strip()
                                if '\n' in expected_resp and yaml:
                                    # Compare YAML structures
                                    try:
                                        expected_obj = yaml.safe_load(expected_resp)
                                        answer_obj = yaml.safe_load(user_answer_content or '')
                                        is_correct = (answer_obj == expected_obj)
                                    except Exception:
                                        is_correct = False
                                else:
                                    is_correct = commands_equivalent(user_answer_content, expected_resp)
                            elif q_type in ['live_k8s_edit', 'live_k8s']:
                                is_correct = self._run_one_exercise(q, is_check_only=True)

                            self.logger.info(f"Question {i}/{total_questions}: prompt=\"{q['prompt']}\" result=\"{'correct' if is_correct else 'incorrect'}\"")
                            if is_correct:
                                correct_count += 1
                                per_category_stats[category]['correct'] += 1
                                print(f"{Fore.GREEN}Correct!{Style.RESET_ALL}")
                                if q.get('explanation'):
                                    print(f"{Fore.CYAN}Explanation: {q['explanation']}{Style.RESET_ALL}")
                                # AI-generated detailed explanation (if enabled)
                                from kubelingo.modules.llm.session import AIHelper
                                if getattr(AIHelper, 'enabled', False):
                                    ai = AIHelper()
                                    ai_text = ai.get_explanation(q)
                                    if ai_text:
                                        print(ai_text)
                                current_question_index += 1
                                break
                            else:
                                print(f"{Fore.RED}Incorrect.{Style.RESET_ALL}")
                                if q_type == 'command':
                                    print(f"{Fore.GREEN}Correct answer: {q.get('response', '')}{Style.RESET_ALL}")
                                # AI-generated detailed explanation (if enabled)
                                from kubelingo.modules.llm.session import AIHelper
                                if getattr(AIHelper, 'enabled', False):
                                    ai = AIHelper()
                                    ai_text = ai.get_explanation(q)
                                    if ai_text:
                                        print(ai_text)
                                continue
                    if quiz_backed_out:
                        break  # Exit question loop to go back to quiz menu
                
                if quiz_backed_out:
                    continue  # Go back to quiz selection menu

                end_time = datetime.now()
                duration = str(end_time - start_time).split('.')[0]
                
                if skipped_questions:
                    print(f"\n{Fore.CYAN}--- Reviewing {len(skipped_questions)} Skipped Questions ---{Style.RESET_ALL}")
                    for q in skipped_questions:
                        print(f"\n{Fore.YELLOW}Skipped: {q['prompt']}{Style.RESET_ALL}")
                        print(f"{Fore.GREEN}Correct answer: {q.get('response', 'See explanation.')}{Style.RESET_ALL}")
                        if q.get('explanation'):
                            print(f"{Fore.CYAN}Explanation: {q['explanation']}{Style.RESET_ALL}")

                print(f"\n{Fore.CYAN}=== Quiz Complete ==={Style.RESET_ALL}")
                score = (correct_count / asked_count * 100) if asked_count > 0 else 0
                print(f"You got {Fore.GREEN}{correct_count}{Style.RESET_ALL} out of {Fore.YELLOW}{asked_count}{Style.RESET_ALL} correct ({Fore.CYAN}{score:.1f}%{Style.RESET_ALL}).")
                print(f"Time taken: {Fore.CYAN}{duration}{Style.RESET_ALL}")
                
                self.session_manager.save_history(start_time, asked_count, correct_count, duration, args, per_category_stats)
                # After quiz completion, loop back to the menu
                continue
        else:
            # Non-interactive mode
            # For a simple, non-interactive command quiz, try the Rust version first.
            if not args.review_only and not args.live and args.file == DEFAULT_DATA_FILE:
                try:
                    from kubelingo.bridge import rust_bridge
                    if rust_bridge.is_available():
                        if rust_bridge.run_command_quiz(args):
                            return  # Success, we're done.
                        else:
                            # Rust bridge is available but failed to run the quiz.
                            print(f"{Fore.YELLOW}Rust command quiz execution failed, falling back to Python implementation.{Style.RESET_ALL}")
                except ImportError:
                    pass  # No rust bridge, just fall through to Python.

            if args.review_only:
                # Load all flagged questions from all command quiz files
                all_files = _get_quiz_files()
                all_flagged = []
                for f in all_files:
                    qs = load_questions(f)
                    for q in qs:
                        if q.get('review'):
                            q['data_file'] = f  # Tag with origin file
                            all_flagged.append(q)
                questions = all_flagged
            else:
                questions = load_questions(args.file)

        if args.review_only and not questions:
            print(Fore.YELLOW + "No questions flagged for review found." + Style.RESET_ALL)
            return

        if args.category:
            questions = [q for q in questions if q.get('category') == args.category]
            if not questions:
                print(Fore.YELLOW + f"No questions found in category '{args.category}'." + Style.RESET_ALL)
                return

        runnable_questions = [q for q in questions if q.get('type', 'command') in ('command', 'live_k8s', 'live_k8s_edit')]
        if not runnable_questions:
            print(Fore.YELLOW + "No runnable questions available for this quiz." + Style.RESET_ALL)
            return

        num_to_ask = args.num if args.num > 0 else len(runnable_questions)
        questions_to_ask = random.sample(runnable_questions, min(num_to_ask, len(runnable_questions)))

        if not questions_to_ask:
            print(Fore.YELLOW + "No questions to ask." + Style.RESET_ALL)
            return

        correct_count = 0
        per_category_stats = {}
        total_questions = len(questions_to_ask)
        asked_count = 0
        skipped_questions = []

        print(f"\n{Fore.CYAN}=== Starting Kubelingo Quiz ==={Style.RESET_ALL}")
        print(f"File: {Fore.CYAN}{os.path.basename(args.file)}{Style.RESET_ALL}, Questions: {Fore.CYAN}{total_questions}{Style.RESET_ALL}")

        from kubelingo.sandbox import spawn_pty_shell, launch_container_sandbox
        
        prompt_session = None
        if PromptSession and FileHistory:
            prompt_session = PromptSession(history=FileHistory(INPUT_HISTORY_FILE))
        
        current_question_index = 0
        while current_question_index < len(questions_to_ask):
            q = questions_to_ask[current_question_index]
            i = current_question_index + 1

            category = q.get('category', 'General')
            if category not in per_category_stats:
                per_category_stats[category] = {'asked': 0, 'correct': 0}

            user_answer_content = None
            was_answered = False

            # Inner loop for the in-quiz menu
            print(f"\n{Fore.YELLOW}Question {i}/{total_questions} (Category: {category}){Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}{q['prompt']}{Style.RESET_ALL}")
            while True:
                is_flagged = q.get('review', False)
                flag_option_text = "Unflag" if is_flagged else "Flag"
                
                q_type = q.get('type', 'command')
                answer_text = "Answer (Enter Command)" if q_type == 'command' else "Answer (Open Terminal)"
                
                choices = [
                    questionary.Choice(f"1. {answer_text}", value="answer"),
                    questionary.Choice("2. Check Answer", value="check"),
                    questionary.Choice(f"3. {flag_option_text}", value="flag"),
                    questionary.Choice("4. Skip", value="skip"),
                    questionary.Choice("5. Back to Quiz Menu", value="back")
                ]
                
                try:
                    action = questionary.select("Action:", choices=choices, use_indicator=False).ask()
                    if action is None: raise KeyboardInterrupt
                except (EOFError, KeyboardInterrupt):
                    print(f"\n{Fore.YELLOW}Quiz interrupted.{Style.RESET_ALL}")
                    self.session_manager.save_history(start_time, asked_count, correct_count, str(datetime.now() - start_time).split('.')[0], args, per_category_stats)
                    return

                if action == "back":
                    end_time = datetime.now()
                    duration = str(end_time - start_time).split('.')[0]
                    self.session_manager.save_history(start_time, asked_count, correct_count, duration, args, per_category_stats)
                    return
                
                if action == "skip":
                    if not was_answered:
                        per_category_stats[category]['asked'] += 1
                        asked_count += 1
                    skipped_questions.append(q)
                    self.logger.info(f"Question {i}/{total_questions}: SKIPPED prompt=\"{q['prompt']}\"")
                    current_question_index += 1
                    break

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
                    if not was_answered:
                        per_category_stats[category]['asked'] += 1
                        asked_count += 1
                    was_answered = True

                    if q_type == 'command':
                        if prompt_session:
                            user_answer_content = prompt_session.prompt(f'{Fore.CYAN}Your answer: {Style.RESET_ALL}').strip()
                        else:
                            user_answer_content = input(f'{Fore.CYAN}Your answer: {Style.RESET_ALL}').strip()
                    else:
                        sandbox_func = launch_container_sandbox if args.docker else spawn_pty_shell
                        sandbox_func()
                        user_answer_content = "sandbox_session_completed"

                if action == "check":
                    if not was_answered:
                        if q_type == 'command':
                            print(f"{Fore.GREEN}Correct answer: {q.get('response', '')}{Style.RESET_ALL}")
                        else:
                            print(f"{Fore.YELLOW}Answer cannot be shown directly for this question type. Please attempt a solution first.{Style.RESET_ALL}")
                        continue
                    
                    if q_type == 'command':
                        is_correct = commands_equivalent(user_answer_content, q.get('response', ''))
                    elif q_type in ['live_k8s_edit', 'live_k8s']:
                        is_correct = self._run_one_exercise(q, is_check_only=True)

                    self.logger.info(f"Question {i}/{total_questions}: prompt=\"{q['prompt']}\" result=\"{'correct' if is_correct else 'incorrect'}\"")
                    if is_correct:
                        correct_count += 1
                        per_category_stats[category]['correct'] += 1
                        print(f"{Fore.GREEN}Correct!{Style.RESET_ALL}")
                        if q.get('explanation'):
                            print(f"{Fore.CYAN}Explanation: {q['explanation']}{Style.RESET_ALL}")
                        current_question_index += 1
                        break
                    else:
                        print(f"{Fore.RED}Incorrect.{Style.RESET_ALL}")
                        if q_type == 'command':
                            print(f"{Fore.GREEN}Correct answer: {q.get('response', '')}{Style.RESET_ALL}")
                        continue
            
        end_time = datetime.now()
        duration = str(end_time - start_time).split('.')[0]
        
        if skipped_questions:
            print(f"\n{Fore.CYAN}--- Reviewing {len(skipped_questions)} Skipped Questions ---{Style.RESET_ALL}")
            for q in skipped_questions:
                print(f"\n{Fore.YELLOW}Skipped: {q['prompt']}{Style.RESET_ALL}")
                print(f"{Fore.GREEN}Correct answer: {q.get('response', 'See explanation.')}{Style.RESET_ALL}")
                if q.get('explanation'):
                    print(f"{Fore.CYAN}Explanation: {q['explanation']}{Style.RESET_ALL}")

        print(f"\n{Fore.CYAN}=== Quiz Complete ==={Style.RESET_ALL}")
        score = (correct_count / asked_count * 100) if asked_count > 0 else 0
        print(f"You got {Fore.GREEN}{correct_count}{Style.RESET_ALL} out of {Fore.YELLOW}{asked_count}{Style.RESET_ALL} correct ({Fore.CYAN}{score:.1f}%{Style.RESET_ALL}).")
        print(f"Time taken: {Fore.CYAN}{duration}{Style.RESET_ALL}")
        
        self.session_manager.save_history(start_time, asked_count, correct_count, duration, args, per_category_stats)

    def _build_interactive_menu_choices(self):
        """Helper to construct the list of choices for the interactive menu."""
        all_quiz_files = sorted(
            _get_quiz_files() + _get_md_quiz_files() + _get_yaml_quiz_files() +
            ([VIM_QUESTIONS_FILE] if os.path.exists(VIM_QUESTIONS_FILE) else [])
        )
        all_flagged = get_all_flagged_questions()

        choices = []
        if all_flagged:
            choices.append({'name': f"Review {len(all_flagged)} Flagged Questions", 'value': "review"})
        
        if all_quiz_files:
            choices.append(questionary.Separator("Standard Quizzes"))
            for file_path in all_quiz_files:
                base = os.path.basename(file_path)
                name = os.path.splitext(base)[0]
                subject = humanize_module(name)
                title = f"  {subject} ({base})"
                choices.append(questionary.Choice(title=title, value=file_path))
        
        if all_flagged:
            choices.append(questionary.Separator())
            choices.append({'name': f"Clear All {len(all_flagged)} Review Flags", 'value': "clear_flags"})

        choices.append(questionary.Separator())
        choices.append({'name': "Back to Main Menu", 'value': "back"})

        return choices, all_flagged

    def _run_live_mode(self, args):
        """DEPRECATED: Handles setup and execution of live Kubernetes exercises."""
        # This method is no longer used by the unified quiz runner.
        pass

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
        """
        Handles validation for a single exercise by running its assertion script.
        """
        is_correct = False
        # The 'response' field in legacy questions can be treated as a simple shell assertion.
        assertion = q.get('assert_script') or q.get('response')
        # For live Kubernetes exercises, allow user to run commands in an interactive prompt
        if q.get('type') == 'live_k8s':
            prompt_sess = None
            if PromptSession:
                prompt_sess = PromptSession()
            # Loop until user signals completion
            while True:
                try:
                    if prompt_sess:
                        cmd_line = prompt_sess.prompt(f"{Fore.CYAN}Your command: {Style.RESET_ALL}").strip()
                    else:
                        cmd_line = input('Your command: ').strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break
                if cmd_line.lower() == 'done':
                    break
                parts = cmd_line.split()
                try:
                    proc = subprocess.run(parts, capture_output=True, text=True, check=False)
                    if proc.stdout:
                        print(proc.stdout, end='')
                    if proc.stderr:
                        print(proc.stderr, end='')
                except Exception as e:
                    print(f"{Fore.RED}Error running command: {e}{Style.RESET_ALL}")
        if not assertion:
            # If there's no way to validate, we can't determine correctness.
            # This might be intended for questions that are purely informational.
            # For now, we'll treat it as incorrect from a grading perspective.
            print(f"{Fore.YELLOW}Warning: No validation script found for this question.{Style.RESET_ALL}")
            return False

        try:
            with tempfile.NamedTemporaryFile(mode='w+', suffix=".sh", delete=False, encoding='utf-8') as tmp_assert:
                tmp_assert.write(assertion)
                assert_path = tmp_assert.name
            os.chmod(assert_path, 0o755)

            # The validation script will use the default KUBECONFIG from the environment
            assert_proc = subprocess.run(['bash', assert_path], capture_output=True, text=True)
            os.remove(assert_path)

            if assert_proc.returncode == 0:
                if assert_proc.stdout:
                    print(assert_proc.stdout)
                is_correct = True
            else:
                # Provide feedback from the script's output
                print(assert_proc.stdout or assert_proc.stderr)
        except Exception as e:
            print(Fore.RED + f"An unexpected error occurred during validation: {e}" + Style.RESET_ALL)
        # Log the outcome of the live exercise
        result = 'correct' if is_correct else 'incorrect'
        self.logger.info(f"Live exercise: prompt=\"{q.get('prompt')}\" result=\"{result}\"")
        return is_correct

    def cleanup(self):
        """Deletes the EKS cluster if one was created for a live session."""
        if not self.live_session_active or not self.cluster_name or self.cluster_name == "pre-configured":
            return
        # ... cleanup logic from the original file ...



