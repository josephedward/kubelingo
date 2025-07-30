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
from pathlib import Path
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

    def initialize(self):
        """Basic initialization. Live session initialization is deferred."""
        return True

    def run_exercises(self, args):
        """
        Router for running exercises. It decides which quiz to run.
        """
        # When run without arguments, args.file may be defaulted.
        # Force interactive quiz selection by clearing the file if no other
        # filters like category, review-only, or number of questions are active.
        if (args.file and os.path.basename(args.file) == os.path.basename(DEFAULT_DATA_FILE) and
                not args.category and not args.review_only and not (args.num and args.num > 0)):
            args.file = None

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
        start_time = datetime.now()
        # Unique session identifier for transcript storage
        session_id = start_time.strftime('%Y%m%dT%H%M%S')
        os.environ['KUBELINGO_SESSION_ID'] = session_id
        questions = []

        is_interactive = questionary and not args.file and not args.category and not args.review_only

        if is_interactive:
            choices, flagged_questions = self._build_interactive_menu_choices()
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
                return self._run_unified_quiz(args)

            if selected == 'review':
                args.review_only = True
                questions = flagged_questions
                args.file = 'review_session'
            else:
                args.file = selected
                questions = load_questions(args.file)
        else:
            if args.review_only:
                questions = get_all_flagged_questions()
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

        num_to_ask = args.num if args.num > 0 else len(questions)
        questions_to_ask = random.sample(questions, min(num_to_ask, len(questions)))

        if not questions_to_ask:
            print(Fore.YELLOW + "No questions to ask." + Style.RESET_ALL)
            return

        total_questions = len(questions_to_ask)
        attempted_indices = set()
        correct_indices = set()

        print(f"\n{Fore.CYAN}=== Starting Kubelingo Quiz ==={Style.RESET_ALL}")
        print(f"File: {Fore.CYAN}{os.path.basename(args.file)}{Style.RESET_ALL}, Questions: {Fore.CYAN}{total_questions}{Style.RESET_ALL}")
        self._initialize_live_session()

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
                choices.append({"name": "Work on Answer (in Shell)", "value": "answer"})
                choices.append({"name": "Check Answer", "value": "check"})
                # Toggle flag for review
                choices.append({"name": flag_option_text if 'Unflag' in flag_option_text else "Flag for Review", "value": "flag"})
                choices.append({"name": "Next Question", "value": "next"})
                choices.append({"name": "Previous Question", "value": "prev"})
                choices.append({"name": "Exit Quiz.", "value": "back"})

                try:
                    # Ensure visual separation between previous output and the menu
                    # Visual separation before menu
                    print()
                    action = questionary.select(
                        "Action:",
                        choices=choices,
                        use_indicator=True
                    ).ask()
                    if action is None: raise KeyboardInterrupt
                except (EOFError, KeyboardInterrupt):
                    print(f"\n{Fore.YELLOW}Quiz interrupted.{Style.RESET_ALL}")
                    # Recompute stats before saving history on interrupt
                    asked_count = len(attempted_indices)
                    correct_count = len(correct_indices)
                    per_category_stats = self._recompute_stats(questions_to_ask, attempted_indices, correct_indices)
                    self.session_manager.save_history(start_time, asked_count, correct_count, str(datetime.now() - start_time).split('.')[0], args, per_category_stats)
                    return

                if action == "back":
                    quiz_backed_out = True
                    break
                
                if action == "next":
                    current_question_index = min(current_question_index + 1, total_questions - 1)
                    break

                if action == "prev":
                    current_question_index = max(current_question_index - 1, 0)
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
                    from kubelingo.sandbox import run_shell_with_setup
                    from kubelingo.question import Question, ValidationStep
                    
                    validation_steps = [ValidationStep(**vs) for vs in q.get('validation_steps', [])]
                    if not validation_steps and q.get('type') == 'command' and q.get('response'):
                        validation_steps.append(ValidationStep(cmd=q['response'], matcher={'exit_code': 0}))

                    question_obj = Question(
                        id=q.get('id', ''),
                        prompt=q.get('prompt', ''),
                        pre_shell_cmds=q.get('pre_shell_cmds', []),
                        initial_files=q.get('initial_files', {}),
                        validation_steps=validation_steps,
                        explanation=q.get('explanation'),
                        categories=q.get('categories', [q.get('category', 'General')]),
                        difficulty=q.get('difficulty'),
                        metadata=q.get('metadata', {})
                    )
                    
                    result = run_shell_with_setup(
                        question_obj,
                        use_docker=args.docker,
                        ai_eval=getattr(args, 'ai_eval', False)
                    )
                    transcripts_by_index[current_question_index] = result
                    
                    # Re-print question header after shell.
                    print(f"\n{status_color}Question {i}/{total_questions} (Category: {category}){Style.RESET_ALL}")
                    print(f"{Fore.MAGENTA}{q['prompt']}{Style.RESET_ALL}")

                    # Immediately process the result
                    is_correct = self._check_and_process_answer(args, q, result, current_question_index, attempted_indices, correct_indices)
                    if is_correct:
                        current_question_index += 1
                        break # Move to next question
                    else:
                        continue # Stay on current question to retry
                
                if action == "check":
                    result = transcripts_by_index.get(current_question_index)
                    if not result or not result.transcript_path:
                        print(f"{Fore.YELLOW}No attempt recorded for this question. Please use 'Work on Answer' first.{Style.RESET_ALL}")
                        continue

                    from kubelingo.question import ValidationStep
                    validation_steps = [ValidationStep(**vs) for vs in q.get('validation_steps', [])]
                    if not validation_steps and q.get('type') == 'command' and q.get('response'):
                        validation_steps.append(ValidationStep(cmd=q['response'], matcher={'contains': q['response']}))

                    print(f"{Fore.CYAN}Re-evaluating answer from transcript...{Style.RESET_ALL}")
                    is_correct_re_eval, details = evaluate_transcript(result.transcript_path, validation_steps)
                    
                    # Update the result, but since we don't have per-step results from this evaluator, just update success.
                    result.success = is_correct_re_eval
                    
                    # This check is now just for displaying feedback and moving on
                    is_correct = self._check_and_process_answer(args, q, result, current_question_index, attempted_indices, correct_indices)
                    if is_correct:
                        current_question_index = min(current_question_index + 1, total_questions - 1)
                        break
                    else:
                        continue
            
            if quiz_backed_out:
                break
        
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

    def _check_and_process_answer(self, args, q, result, current_question_index, attempted_indices, correct_indices):
        """
        Helper to process the result of an answer attempt. It uses AI evaluation
        if available and requested, otherwise falls back to deterministic checks.
        """
        attempted_indices.add(current_question_index)
        is_correct = False  # Default to incorrect
        ai_eval_used = False
        ai_eval_active = getattr(args, 'ai_eval', False)

        # AI-First Evaluation: if --ai-eval is on, use transcript with LLM.
        if ai_eval_active and os.getenv('OPENAI_API_KEY') and result.transcript_path:
            try:
                from kubelingo.modules.ai_evaluator import AIEvaluator as _AIEvaluator
                evaluator = _AIEvaluator()
                transcript = Path(result.transcript_path).read_text(encoding='utf-8')
                ai_result = evaluator.evaluate(q, transcript)
                is_correct = ai_result.get('correct', False)
                reasoning = ai_result.get('reasoning', '')
                status = 'Correct' if is_correct else 'Incorrect'
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
            # Fallback to deterministic validation.
            is_correct = result.success

            # An answer cannot be correct if there are no validation steps defined in the question data.
            # This prevents questions from being marked correct just because a shell was exited cleanly.
            has_validation_data = bool(q.get('validation_steps') or (q.get('type') == 'command' and q.get('response')))
            if not has_validation_data:
                print(f"{Fore.YELLOW}Warning: No validation steps found for this question.{Style.RESET_ALL}")
                is_correct = False

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
        all_quiz_files = sorted(
            _get_quiz_files() + _get_md_quiz_files() + _get_yaml_quiz_files() +
            ([VIM_QUESTIONS_FILE] if os.path.exists(VIM_QUESTIONS_FILE) else [])
        )
        all_flagged = get_all_flagged_questions()

        choices = []
        if all_flagged:
            choices.append({"name": f"Review {len(all_flagged)} Flagged Questions", "value": "review"})
        
        if all_quiz_files:
            choices.append(questionary.Separator("Standard Quizzes"))
            for file_path in all_quiz_files:
                base = os.path.basename(file_path)
                name = os.path.splitext(base)[0]
                subject = humanize_module(name).strip()
                title = f"{subject} ({base})"
                choices.append({"name": title, "value": file_path})
        
        if all_flagged:
            choices.append(questionary.Separator())
            choices.append({"name": f"Clear All {len(all_flagged)} Review Flags", "value": "clear_flags"})

        choices.append(questionary.Separator())
        choices.append({"name": "Back to Main Menu", "value": "back"})

        return choices, all_flagged

    def _run_live_mode(self, args):
        """DEPRECATED: Handles setup and execution of live Kubernetes exercises."""
        # This method is no longer used by the unified quiz runner.
        pass

    def _initialize_live_session(self):
        """
        Checks for dependencies. This is now mostly handled by the sandbox runner.
        """
        deps = check_dependencies('kubectl', 'docker')
        if 'docker' in deps:
            print(f"{Fore.YELLOW}Warning: Docker not found. Containerized sandboxes will not be available.{Style.RESET_ALL}")
        
        if 'kubectl' in deps:
            print(f"{Fore.YELLOW}Warning: kubectl not found. Cluster interactions will not be available.{Style.RESET_ALL}")

        self.live_session_active = True
        return True

    def _run_one_exercise(self, q):
        """
        Handles validation for a single live Kubernetes exercise.
        Prompts user for commands until 'done' and then runs an assertion script.
        """
        prompt_session = PromptSession() if PromptSession else None
        while True:
            try:
                if prompt_session:
                    cmd = prompt_session.prompt(f"{Fore.CYAN}Your command: {Style.RESET_ALL}").strip()
                else:
                    cmd = input("Your command: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if cmd.lower() == "done":
                break
            parts = cmd.split()
            try:
                proc = subprocess.run(parts, capture_output=True, text=True, check=False)
                if proc.stdout:
                    print(proc.stdout, end="")
                if proc.stderr:
                    print(proc.stderr, end="")
            except Exception as e:
                print(f"{Fore.RED}Error running command: {e}{Style.RESET_ALL}")
        # Assertion script
        script = q.get('assert_script') or q.get('response')
        if not script:
            self.logger.info(f"Live exercise: prompt=\"{q.get('prompt')}\" result=\"incorrect\"")
            return
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sh') as f:
            f.write(script)
            script_path = f.name
        os.chmod(script_path, 0o755)
        try:
            result = subprocess.run(["bash", script_path], capture_output=True, text=True)
            success = (result.returncode == 0)
            self.logger.info(f"Live exercise: prompt=\"{q.get('prompt')}\" result=\"{'correct' if success else 'incorrect'}\"")
        except Exception as e:
            print(f"{Fore.RED}Error executing assertion script: {e}{Style.RESET_ALL}")
        finally:
            os.remove(script_path)
        return

    
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
        """Deletes the EKS cluster if one was created for a live session."""
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



