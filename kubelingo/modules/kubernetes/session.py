import json
import csv
import os
import random
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
import logging

from kubelingo.utils.validation import commands_equivalent
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
    CSV_DIR,
    KILLERCODA_CSV_FILE,
    DATA_DIR,
    INPUT_HISTORY_FILE,
    VIM_HISTORY_FILE,
)

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
except ImportError:
    PromptSession = None
    FileHistory = None

from kubelingo.modules.base.session import StudySession
from kubelingo.modules.base.loader import load_session
# Existing import
from .vim_yaml_editor import VimYamlEditor
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


def get_all_flagged_questions():
    """Returns a list of all questions from all files that are flagged for review."""
    command_quiz_files = _get_quiz_files()

    all_quiz_files = command_quiz_files[:]
    if os.path.exists(VIM_QUESTIONS_FILE):
        all_quiz_files.append(VIM_QUESTIONS_FILE)

    all_flagged = []
    for f in all_quiz_files:
        qs = load_questions(f)
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
        for section in data:
            qs = section.get('questions', []) or section.get('prompts', [])
            for item in qs:
                if 'review' in item:
                    del item['review']
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

def load_questions(data_file):
    # Load quiz data from JSON file
    try:
        with open(data_file, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(Fore.RED + f"Error loading quiz data from {data_file}: {e}" + Style.RESET_ALL)
        sys.exit(1)
    questions = []
    
    if not data:
        return []

    # Heuristic to detect format: flat list vs. list of categories
    is_flat_list = isinstance(data[0], dict) and 'prompt' in data[0]

    if is_flat_list:
        # Wrap flat list in a 'General' category to be processed by the same logic
        data = [{'category': 'General', 'questions': data}]

    for cat in data:
        category = cat.get('category', '')
        # Support both 'questions' and 'prompts' keys for question lists.
        prompts = cat.get('prompts', []) or cat.get('questions', [])
        for item in prompts:
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
                # Also handles the 'answer' key for responses in some formats.
                question['response'] = item.get('response', '') or item.get('answer', '')
            questions.append(question)
    return questions
import logging
from kubelingo.modules.base.session import SessionManager

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

        # For non-live exercises, all quiz types are presented in one menu.
        self._run_command_quiz(args)

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
                    'vim_quiz': self._run_vim_commands_quiz,
                    'killercoda_ckad': self._run_killercoda_ckad
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
                elif selected.endswith('.json'):
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

                runnable_questions = [q for q in questions if q.get('type') in ('command', 'live_k8s', 'live_k8s_edit')]
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
                    while True:
                        print(f"\n{Fore.YELLOW}Question {i}/{total_questions} (Category: {category}){Style.RESET_ALL}")
                        print(f"{Fore.MAGENTA}{q['prompt']}{Style.RESET_ALL}")

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

                            if q_type == 'command':
                                if prompt_session:
                                    # Use plain prompt to avoid ANSI codes in answers
                                    user_answer_content = prompt_session.prompt('Your answer: ').strip()
                                else:
                                    user_answer_content = input('Your answer: ').strip()
                            else:
                                sandbox_func = launch_container_sandbox if args.docker else spawn_pty_shell
                                sandbox_func()
                                user_answer_content = "sandbox_session_completed"
                            continue

                        if action == "check":
                            if q_type == 'command':
                                if not was_answered:
                                    expected = q.get('response', '')
                                    print(f"{Fore.CYAN}Running expected command for environment check: {expected}{Style.RESET_ALL}")
                                    try:
                                        subprocess.run(expected.split(), check=False)
                                    except Exception as e:
                                        print(f"{Fore.RED}Error running expected command: {e}{Style.RESET_ALL}")
                                    continue
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
                                # AI-generated detailed explanation
                                try:
                                    from kubelingo.modules.llm.session import AIHelper
                                    ai = AIHelper()
                                    ai_text = ai.get_explanation(q)
                                    print(ai_text)
                                except ImportError:
                                    pass
                                current_question_index += 1
                                break
                            else:
                                print(f"{Fore.RED}Incorrect.{Style.RESET_ALL}")
                                if q_type == 'command':
                                    print(f"{Fore.GREEN}Correct answer: {q.get('response', '')}{Style.RESET_ALL}")
                                # AI-generated detailed explanation
                                try:
                                    from kubelingo.modules.llm.session import AIHelper
                                    ai = AIHelper()
                                    ai_text = ai.get_explanation(q)
                                    print(ai_text)
                                except ImportError:
                                    pass
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

        runnable_questions = [q for q in questions if q.get('type') in ('command', 'live_k8s', 'live_k8s_edit')]
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
            while True:
                print(f"\n{Fore.YELLOW}Question {i}/{total_questions} (Category: {category}){Style.RESET_ALL}")
                print(f"{Fore.MAGENTA}{q['prompt']}{Style.RESET_ALL}")

                is_flagged = q.get('review', False)
                flag_option_text = "Unflag" if is_flagged else "Flag"
                
                q_type = q.get('type', 'command')
                answer_text = "Answer (Enter Command)" if q_type == 'command' else "Answer (Open Terminal)"
                
                choices = [
                    questionary.Choice(f"1. {answer_text}", value="answer"),
                    questionary.Choice("2. Check Answer", value="check", disabled=not was_answered),
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
                    continue

                if action == "check":
                    if not was_answered:
                        print(f"{Fore.RED}You must select 'Answer' first.{Style.RESET_ALL}")
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
        command_quiz_files = _get_quiz_files()

        all_flagged = get_all_flagged_questions()

        # Separate flagged questions by type for different review modes
        flagged_command_questions = [
            q for q in all_flagged if q.get('type', 'command') in ('command', 'live_k8s', 'live_k8s_edit') and q['data_file'] != VIM_QUESTIONS_FILE
        ]
        flagged_vim_questions = [q for q in all_flagged if q['data_file'] == VIM_QUESTIONS_FILE]

        choices = []

        # Review options
        if flagged_command_questions:
            choices.append({'name': f"Review {len(flagged_command_questions)} Flagged Command Questions", 'value': "review"})
        if flagged_vim_questions:
            choices.append({'name': f"Review {len(flagged_vim_questions)} Flagged Vim Questions", 'value': "vim_review"})

        # Quizzes from files
        if command_quiz_files:
            choices.append(questionary.Separator("Command Quizzes"))
            for file_path in command_quiz_files:
                base = os.path.basename(file_path)
                name = os.path.splitext(base)[0]
                subject = humanize_module(name)
                # Style.DIM was causing rendering issues with questionary
                title = f"  {subject} ({base})"
                choices.append(questionary.Choice(title=title, value=file_path))

        # Other exercises
        choices.append(questionary.Separator("Other Exercises"))
        choices.append({'name': f"YAML Editing Quiz ({os.path.basename(YAML_QUESTIONS_FILE)})", 'value': "yaml_standard"})
        choices.append({'name': "YAML Progressive Scenarios", 'value': "yaml_progressive"})
        choices.append({'name': "YAML Live Cluster Exercise", 'value': "yaml_live"})
        choices.append({'name': "YAML Create Custom Exercise", 'value': "yaml_create"})
        choices.append(questionary.Separator())
        choices.append({'name': f"Vim Commands Quiz ({os.path.basename(VIM_QUESTIONS_FILE)})", 'value': "vim_quiz"})
        # Determine Killercoda CKAD quiz CSV file (env override or default)
        killercoda_csv_file = os.environ.get(
            'KILLERCODA_CSV',
            os.path.join(CSV_DIR, 'killercoda-ckad_072425.csv')
        )
        choices.append({'name': f"Killercoda CKAD Quiz ({os.path.basename(killercoda_csv_file)})", 'value': "killercoda_ckad"})

        # Admin options
        if all_flagged:
            choices.append(questionary.Separator())
            # Fore.YELLOW was causing rendering issues with questionary
            choices.append({'name': f"Clear All {len(all_flagged)} Review Flags", 'value': "clear_flags"})

        choices.append(questionary.Separator())
        choices.append({'name': "Back to Main Menu", 'value': "back"})

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
        """Runs the Vim commands quiz with a standardized, interactive format."""
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
        total_questions = len(questions_to_ask)
        asked_count = 0
        skipped_questions = []

        print(f"\n{Fore.CYAN}=== Starting Vim Commands Quiz ==={Style.RESET_ALL}")
        print(f"File: {Fore.CYAN}{os.path.basename(data_file)}{Style.RESET_ALL}, Questions: {Fore.CYAN}{total_questions}{Style.RESET_ALL}")

        quiz_backed_out = False
        current_question_index = 0
        while current_question_index < len(questions_to_ask):
            q = questions_to_ask[current_question_index]
            i = current_question_index + 1
            category = q.get('category', 'Vim')

            was_answered = False
            user_answer_content = None # Will store path to vim script log

            while True: # Inner loop for the in-quiz menu
                print(f"\n{Fore.YELLOW}Question {i}/{total_questions} (Category: {category}){Style.RESET_ALL}")
                print(f"How do you: {Fore.MAGENTA}{q['prompt']}{Style.RESET_ALL}?")

                is_flagged = q.get('review', False)
                flag_option_text = "Unflag" if is_flagged else "Flag"

                choices = [
                    questionary.Choice("1. Answer (Open Vim)", value="answer"),
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
                    return

                if action == "back":
                    quiz_backed_out = True
                    break

                if action == "skip":
                    if not was_answered:
                        asked_count += 1
                    skipped_questions.append(q)
                    self.logger.info(f"Vim Question {i}/{total_questions}: SKIPPED prompt=\"{q['prompt']}\"")
                    current_question_index += 1
                    break

                if action == "flag":
                    if is_flagged:
                        self.session_manager.unmark_question_for_review(data_file, q['category'], q['prompt'])
                        q['review'] = False
                        print(Fore.MAGENTA + "Question unflagged." + Style.RESET_ALL)
                    else:
                        self.session_manager.mark_question_for_review(data_file, q['category'], q['prompt'])
                        q['review'] = True
                        print(Fore.MAGENTA + "Question flagged for review." + Style.RESET_ALL)
                    continue

                if action == "answer":
                    if not was_answered:
                        asked_count += 1
                    was_answered = True
                    
                    try:
                        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp_content, \
                             tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as tmp_script:
                            tmp_content_path = tmp_content.name
                            user_answer_content = tmp_script.name
                            tmp_content.write("This is a test file for your vim exercise.\n")
                        
                        editor = os.environ.get('EDITOR', 'vim')
                        print(f"\n{Fore.GREEN}Opening a temporary file in {editor}. Perform the action and then exit (e.g., with :q).{Style.RESET_ALL}")
                        
                        cmd = [editor, '-w', user_answer_content, tmp_content_path]
                        subprocess.call(cmd)

                    finally:
                        if 'tmp_content_path' in locals() and os.path.exists(tmp_content_path):
                            os.unlink(tmp_content_path)
                    continue

                if action == "check":
                    if not was_answered:
                        print(f"{Fore.RED}You must select 'Answer' first.{Style.RESET_ALL}")
                        continue
                    
                    is_correct = False
                    try:
                        with open(user_answer_content, 'r') as f:
                            script_log = f.read()
                        
                        expected_command = q.get('response', '')
                        is_correct = expected_command in script_log
                        self.logger.info(f"Vim Question {i}/{total_questions}: prompt=\"{q['prompt']}\" expected=\"{expected_command}\" log_file=\"{user_answer_content}\" result=\"{'correct' if is_correct else 'incorrect'}\"")
                    except Exception as e:
                        self.logger.error(f"Error checking vim script log: {e}")
                    finally:
                        if user_answer_content and os.path.exists(user_answer_content):
                            os.unlink(user_answer_content)

                    if is_correct:
                        correct_count += 1
                        print(f"\n{Fore.GREEN}Correct!{Style.RESET_ALL}")
                        if q.get('explanation'):
                            print(f"{Fore.CYAN}Explanation: {q['explanation']}{Style.RESET_ALL}")
                        current_question_index += 1
                        break
                    else:
                        print(f"\n{Fore.RED}Incorrect.{Style.RESET_ALL}")
                        print(f"{Fore.GREEN}Correct answer: {q.get('response', '')}{Style.RESET_ALL}")
                        continue
            
            if quiz_backed_out:
                break
        
        if quiz_backed_out:
            return

        end_time = datetime.now()
        duration = str(end_time - start_time).split('.')[0]

        if skipped_questions:
            print(f"\n{Fore.CYAN}--- Reviewing {len(skipped_questions)} Skipped Questions ---{Style.RESET_ALL}")
            for q in skipped_questions:
                print(f"\n{Fore.YELLOW}Skipped: How do you: {q['prompt']}{Style.RESET_ALL}")
                print(f"{Fore.GREEN}Correct answer: {q.get('response', 'Not available.')}{Style.RESET_ALL}")

        print(f"\n{Fore.CYAN}--- Vim Quiz Complete ---{Style.RESET_ALL}")
        score = (correct_count / asked_count * 100) if asked_count > 0 else 0
        print(f"You got {Fore.GREEN}{correct_count}{Style.RESET_ALL} out of {Fore.YELLOW}{asked_count}{Style.RESET_ALL} correct ({Fore.CYAN}{score:.1f}%{Style.RESET_ALL}).")
        print(f"Time taken: {Fore.CYAN}{duration}{Style.RESET_ALL}")

    def _run_killercoda_ckad(self, args):
        """Runs the Killercoda CKAD CSV-based quiz"""
        start_time = datetime.now()
        csv_file = os.environ.get('KILLERCODA_CSV', KILLERCODA_CSV_FILE)
        if not os.path.exists(csv_file):
            print(f"{Fore.RED}CSV file not found at {csv_file}{Style.RESET_ALL}")
            return

        # Parse CSV questions: [category, prompt, answer, ...]
        questions = []
        with open(csv_file, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            # Skip header if present
            try:
                first = next(reader)
                if len(first) >= 2 and 'prompt' in first[1].lower():
                    pass
                else:
                    reader = iter([first] + list(reader))
            except StopIteration:
                pass
            for row in reader:
                if len(row) < 3:
                    continue
                cat, prompt, answer = [r.strip() for r in row[:3]]
                if prompt.startswith("'") and prompt.endswith("'"):
                    prompt = prompt[1:-1].strip()
                if answer.startswith("'") and answer.endswith("'"):
                    answer = answer[1:-1].strip()
                if not prompt or not answer:
                    continue
                questions.append({'category': cat or 'CKAD', 'prompt': prompt, 'answer': answer, 'review': False})
        if not questions:
            print(f"{Fore.YELLOW}No questions found in CSV file.{Style.RESET_ALL}")
            return

        # Filter by category if requested
        if getattr(args, 'category', None):
            questions = [q for q in questions if q['category'] == args.category]
            if not questions:
                print(f"{Fore.YELLOW}No CKAD questions in category '{args.category}'.{Style.RESET_ALL}")
                return
        # Determine number to ask
        num = args.num if getattr(args, 'num', 0) > 0 else len(questions)
        if getattr(args, 'randomize', False):
            to_ask = random.sample(questions, min(num, len(questions)))
        else:
            to_ask = questions[:num]

        total_to_ask = len(to_ask)
        correct_count = 0
        asked_count = 0
        skipped_questions = []

        print(f"\n{Fore.CYAN}=== Killercoda CKAD CSV Quiz ==={Style.RESET_ALL}")
        print(f"Starting CKAD quiz with {Fore.CYAN}{total_to_ask}{Style.RESET_ALL} questions.")

        quiz_backed_out = False
        current_question_index = 0
        while current_question_index < len(to_ask):
            q = to_ask[current_question_index]
            i = current_question_index + 1
            category = q.get('category', 'CKAD')
            user_answer_content = None
            was_answered = False

            # Inner loop for the in-quiz menu
            while True:
                print(f"\n{Fore.YELLOW}Question {i}/{total_to_ask} (Category: {category}){Style.RESET_ALL}")
                print(f"{Fore.MAGENTA}{q['prompt']}{Style.RESET_ALL}")

                is_flagged = q.get('review', False)
                flag_option_text = "Unflag" if is_flagged else "Flag"

                choices = [
                    questionary.Choice("1. Answer (Open Editor)", value="answer"),
                    questionary.Choice("2. Check Answer", value="check"),
                    questionary.Choice(f"3. {flag_option_text} for Review", value="flag"),
                    questionary.Choice("4. Skip", value="skip"),
                    questionary.Choice("5. Back to Quiz Menu", value="back")
                ]
                
                try:
                    action = questionary.select("Action:", choices=choices, use_indicator=False).ask()
                    if action is None: raise KeyboardInterrupt
                except (EOFError, KeyboardInterrupt):
                    print(f"\n{Fore.YELLOW}Quiz interrupted.{Style.RESET_ALL}")
                    return

                if action == "back":
                    quiz_backed_out = True
                    break
                
                if action == "skip":
                    if not was_answered:
                        asked_count += 1
                    skipped_questions.append(q)
                    self.logger.info(f"CKAD CSV Question {i}/{total_to_ask}: SKIPPED prompt=\"{q['prompt']}\"")
                    current_question_index += 1
                    break

                if action == "flag":
                    if is_flagged:
                        q['review'] = False
                        print(Fore.MAGENTA + "Question unflagged (for this session only)." + Style.RESET_ALL)
                    else:
                        q['review'] = True
                        print(Fore.MAGENTA + "Question flagged for review (for this session only)." + Style.RESET_ALL)
                    continue

                if action == "answer":
                    if not was_answered:
                        asked_count += 1
                    was_answered = True
                    tmp = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yaml')
                    tmp_path = tmp.name
                    tmp.close()
                    try:
                        with open(tmp_path, 'w', encoding='utf-8') as tf:
                            tf.write("# Enter your YAML manifest below, without quotes.\n---\n")
                        editor = os.environ.get('EDITOR', 'vim')
                        cmd = [editor, '-c', 'set tabstop=2 shiftwidth=2 expandtab', '--noplugin', tmp_path]
                        subprocess.call(cmd)
                        lines = []
                        with open(tmp_path, encoding='utf-8') as uf:
                            for line in uf:
                                if line.lstrip().startswith('#') or line.strip() == '---':
                                    continue
                                lines.append(line)
                        user_answer_content = ''.join(lines).strip()
                    except Exception as e:
                        print(f"{Fore.RED}An error occurred: {e}{Style.RESET_ALL}")
                    finally:
                        os.unlink(tmp_path)
                    continue

                if action == "check":
                    if not was_answered:
                        print(f"{Fore.RED}You must select 'Answer' first.{Style.RESET_ALL}")
                        continue
                    
                    exp = q['answer'].strip()
                    ans = user_answer_content.strip()
                    is_correct = ans == exp or ans.replace("'", '').replace('"', '') == exp.replace("'", '').replace('"', '')
                    
                    self.logger.info(
                        f"CKAD CSV {i}/{total_to_ask}: prompt=\"{q['prompt']}\" expected=\"{exp}\" "
                        f"answer=\"{ans}\" result=\"{'correct' if is_correct else 'incorrect'}\""
                    )

                    if is_correct:
                        correct_count += 1
                        print(f"{Fore.GREEN}Correct!{Style.RESET_ALL}")
                        current_question_index += 1
                        break
                    else:
                        print(f"{Fore.RED}Incorrect.{Style.RESET_ALL}")
                        print(f"{Fore.GREEN}Expected answer:\n{exp}{Style.RESET_ALL}")
                        continue

            if quiz_backed_out:
                break
        
        duration = str(datetime.now() - start_time).split('.')[0]
        
        if skipped_questions:
            print(f"\n{Fore.CYAN}--- Reviewing {len(skipped_questions)} Skipped Questions ---{Style.RESET_ALL}")
            for q in skipped_questions:
                print(f"\n{Fore.YELLOW}Skipped: {q['prompt']}{Style.RESET_ALL}")
                print(f"{Fore.GREEN}Correct answer: {q.get('answer', 'Not available.')}{Style.RESET_ALL}")

        print(f"\n{Fore.CYAN}=== Quiz Complete ==={Style.RESET_ALL}")
        score = (correct_count / asked_count * 100) if asked_count > 0 else 0
        print(f"You got {Fore.GREEN}{correct_count}{Style.RESET_ALL} out of {Fore.YELLOW}{asked_count}{Style.RESET_ALL} correct ({Fore.CYAN}{score:.1f}%{Style.RESET_ALL}).")
        print(f"Time taken: {Fore.CYAN}{duration}{Style.RESET_ALL}")

    def _run_live_mode(self, args):
        """Handles setup and execution of live Kubernetes exercises."""
        if not self._initialize_live_session():
            return

        all_questions = load_questions(args.file)
        live_qs = [q for q in all_questions if q.get('type') in ('live_k8s_edit', 'live_k8s')]
        if not live_qs:
            print(Fore.YELLOW + "No live Kubernetes exercises found in data file." + Style.RESET_ALL)
            return

        from kubelingo.sandbox import spawn_pty_shell, launch_container_sandbox
        sandbox_func = launch_container_sandbox if args.docker else spawn_pty_shell

        total_questions = len(live_qs)
        questions_to_ask = random.sample(live_qs, total_questions)

        quiz_backed_out = False
        current_question_index = 0
        while current_question_index < len(questions_to_ask):
            q = questions_to_ask[current_question_index]
            i = current_question_index + 1
            was_answered = False

            # Inner loop for the in-quiz menu
            while True:
                # We reprint the question each time to keep it visible
                print(f"\n{Fore.YELLOW}Cloud Exercise {i}/{total_questions} (Category: {q.get('category', 'Live')}){Style.RESET_ALL}")
                print(f"{Fore.MAGENTA}Q: {q['prompt']}{Style.RESET_ALL}")

                is_flagged = q.get('review', False)
                flag_option_text = "Unflag for Review" if is_flagged else "Flag for Review"

                choices = [
                    questionary.Choice("1. Open Sandbox Shell", value="answer"),
                    questionary.Choice("2. Check Answer", value="check"),
                    questionary.Choice(f"3. {flag_option_text}", value="flag"),
                    questionary.Choice("4. Skip", value="skip"),
                    questionary.Choice("5. Exit Live Mode", value="back")
                ]

                try:
                    action = questionary.select("Action:", choices=choices, use_indicator=False).ask()
                    if action is None: raise KeyboardInterrupt
                except (EOFError, KeyboardInterrupt):
                    print(f"\n{Fore.YELLOW}Quiz interrupted.{Style.RESET_ALL}")
                    return

                if action == "back":
                    quiz_backed_out = True
                    break

                if action == "skip":
                    self.logger.info(f"Live Question {i}/{total_questions}: SKIPPED prompt=\"{q['prompt']}\"")
                    # Could add to a skipped list to review at the end
                    current_question_index += 1
                    break

                if action == "flag":
                    data_file_path = q.get('data_file', args.file)
                    if is_flagged:
                        self.session_manager.unmark_question_for_review(data_file_path, q['category'], q['prompt'])
                        q['review'] = False
                        print(Fore.MAGENTA + "Question un-flagged." + Style.RESET_ALL)
                    else:
                        self.session_manager.mark_question_for_review(data_file_path, q['category'], q['prompt'])
                        q['review'] = True
                        print(Fore.MAGENTA + "Question flagged for review." + Style.RESET_ALL)
                    continue

                if action == "answer":
                    was_answered = True
                    print(Fore.GREEN + "\nA sandbox shell will be opened for you to complete the exercise." + Style.RESET_ALL)
                    print(Fore.GREEN + "Type 'exit' or press Ctrl-D to return to this menu and check your answer." + Style.RESET_ALL)
                    sandbox_func()
                    continue

                if action == "check":
                    if not was_answered:
                        print(f"{Fore.RED}You must open the sandbox shell first.{Style.RESET_ALL}")
                        continue

                    is_correct = self._run_one_exercise(q)
                    self.logger.info(f"Live Question {i}/{total_questions}: prompt=\"{q['prompt']}\" result=\"{'correct' if is_correct else 'incorrect'}\"")

                    if is_correct:
                        print(f"{Fore.GREEN}Correct!{Style.RESET_ALL}")
                        if q.get('explanation'):
                            print(f"{Fore.CYAN}Explanation: {q['explanation']}{Style.RESET_ALL}")
                        current_question_index += 1
                        break # to next question
                    else:
                        print(f"{Fore.RED}Incorrect. Try again, skip, or exit.{Style.RESET_ALL}")
                        continue # back to menu for this question

            if quiz_backed_out:
                print(f"\n{Fore.YELLOW}Exiting live exercise mode.{Style.RESET_ALL}")
                break

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
    
    def _run_one_exercise(self, q, is_check_only=False):
        """
        Handles a single live Kubernetes question. For this refactoring, it only
        performs the validation step, since the interactive shell is now launched
        directly from the quiz menu.
        """
        is_correct = False
        # Interactive input of kubectl commands before validation
        if not is_check_only:
            # Prompt user for commands until they enter 'done'
            if PromptSession:
                prompt_session = PromptSession()
            else:
                prompt_session = None
            while True:
                if prompt_session:
                    user_cmd = prompt_session.prompt(f"{Fore.CYAN}Your command: {Style.RESET_ALL}").strip()
                else:
                    user_cmd = input(f"{Fore.CYAN}Your command: {Style.RESET_ALL}").strip()
                if user_cmd.lower() == 'done':
                    break
                if not user_cmd:
                    continue
                try:
                    subprocess.run(user_cmd.split(), capture_output=True, text=True, check=False)
                except Exception as e:
                    print(f"{Fore.RED}Error running command '{user_cmd}': {e}{Style.RESET_ALL}")
        print("\nValidating your solution...")
        try:
            with tempfile.NamedTemporaryFile(mode='w+', suffix=".sh", delete=False, encoding='utf-8') as tmp_assert:
                tmp_assert.write(q.get('assert_script', 'exit 1'))
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
                print(assert_proc.stdout or assert_proc.stderr)
        except Exception as e:
            print(Fore.RED + f"An unexpected error occurred during validation: {e}" + Style.RESET_ALL)
        # Record result in logger
        try:
            result_str = 'correct' if is_correct else 'incorrect'
            self.logger.info(f'Live exercise: prompt="{q.get("prompt","")}" result="{result_str}"')
        except Exception:
            pass
        return is_correct

    def cleanup(self):
        """Deletes the EKS cluster if one was created for a live session."""
        if not self.live_session_active or not self.cluster_name or self.cluster_name == "pre-configured":
            return
        # ... cleanup logic from the original file ...



