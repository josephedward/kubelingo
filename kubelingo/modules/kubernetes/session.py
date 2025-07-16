import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta

try:
    import questionary
except ImportError:
    questionary = None

try:
    import yaml
except ImportError:
    yaml = None

from kubelingo.modules.base.session import StudySession
from kubelingo.modules.k8s_quiz import commands_equivalent

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
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
DATA_DIR = os.path.join(ROOT, 'data')
DEFAULT_DATA_FILE = os.path.join(DATA_DIR, 'ckad_quiz_data.json')
# History file for storing past quiz performance
HISTORY_FILE = os.path.join(os.path.expanduser('~'), '.cli_quiz_history.json')


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
        print(f"Error loading quiz data from {data_file}: {e}")
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
            for item in section.get('prompts', []):
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
            for item in section.get('prompts', []):
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

class KubernetesSession(StudySession):
    """A study session for all Kubernetes-related quizzes."""

    def __init__(self, logger):
        super().__init__(logger)
        self.mode = None
        self.cluster_name = None
        self.kubeconfig_path = None
        self.region = None
        self.creds_acquired = False

    def initialize(self):
        """Initializes the Kubernetes module, selecting command-line or live exercises."""
        print("Kubernetes module loaded. Select quiz type:")
        print("  1) kubectl command-line quiz")
        print("  2) Live Kubernetes exercises (requires go, eksctl, kubectl)")
        try:
            choice = input("Enter choice [1/2]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nInitialization cancelled.")
            return False
        if choice == '1':
            self.mode = 'cli'
            return True
        if choice == '2':
            self.mode = 'live'
            deps = check_dependencies('go', 'eksctl', 'kubectl')
            if deps:
                print(Fore.RED + f"Missing dependencies for live exercises: {', '.join(deps)}. Aborting." + Style.RESET_ALL)
                return False
            # Provision EKS cluster
            self.cluster_name = f"kubelingo-quiz-{random.randint(1000, 9999)}"
            self.kubeconfig_path = os.path.join(tempfile.gettempdir(), f"{self.cluster_name}.kubeconfig")
            try:
                from kubelingo.tools.gosandbox_integration import GoSandboxIntegration
                print(Fore.YELLOW + "Acquiring AWS sandbox credentials via gosandbox..." + Style.RESET_ALL)
                gs = GoSandboxIntegration()
                creds = gs.acquire_credentials()
                if not creds:
                    print(Fore.RED + "Failed to acquire AWS credentials. Cannot proceed with live exercises." + Style.RESET_ALL)
                    return False
                gs.export_to_environment()
                self.creds_acquired = True
            except ImportError:
                print(Fore.RED + "Could not import GoSandboxIntegration. Live exercises unavailable." + Style.RESET_ALL)
                return False
            except Exception as e:
                print(Fore.RED + f"Error acquiring credentials: {e}" + Style.RESET_ALL)
                return False
            self.region = os.environ.get('AWS_REGION', 'us-west-2')
            node_type = os.environ.get('CLUSTER_INSTANCE_TYPE', 't3.medium')
            node_count = os.environ.get('NODE_COUNT', '2')
            print(Fore.YELLOW + f"Provisioning EKS cluster '{self.cluster_name}' (region={self.region}, nodes={node_count}, type={node_type})..." + Style.RESET_ALL)
            try:
                subprocess.run([
                    'eksctl', 'create', 'cluster',
                    '--name', self.cluster_name,
                    '--region', self.region,
                    '--nodegroup-name', 'worker-nodes',
                    '--node-type', node_type,
                    '--nodes', node_count
                ], check=True)
            except subprocess.CalledProcessError as e:
                print(Fore.RED + f"Failed to provision EKS cluster: {e}" + Style.RESET_ALL)
                return False
            # Write kubeconfig
            os.environ['KUBECONFIG'] = self.kubeconfig_path
            with open(self.kubeconfig_path, 'w') as kc:
                subprocess.run(['kubectl', 'config', 'view', '--raw'], stdout=kc, check=True)
            print(Fore.GREEN + "Cluster is ready." + Style.RESET_ALL)
            return True
        print(Fore.RED + "Invalid choice. Aborting." + Style.RESET_ALL)
        return False

    def run_exercises(self, cli_args):
        """Runs a quiz session, handling command, YAML, and live Kubernetes questions."""
        data_file = cli_args.file
        max_q = cli_args.num
        category_filter = cli_args.category
        review_only = cli_args.review_only

        questions = load_questions(data_file)
        # Get all categories for interactive selection if no filter is provided
        all_categories = sorted(list(set(q['category'] for q in questions if q['category'])))
        # If a filter is provided, validate it
        if category_filter and category_filter not in all_categories:
            print(f"Category '{category_filter}' not found. Available categories: {', '.join(all_categories)}")
            return
        # If no filter, but there are categories, let the user choose
        if not category_filter and all_categories and questionary is not None:
            try:
                choices = ['ALL'] + all_categories
                category_filter = questionary.select(
                    "Which category do you want to be quizzed on?",
                    choices=choices
                ).ask()
                if category_filter is None:
                    print("\nExiting.")
                    return
                if category_filter == 'ALL':
                    category_filter = None
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                return

        # Filter questions by category if a filter is set
        if category_filter:
            questions = [q for q in questions if q['category'] == category_filter]

        if review_only:
            questions = [q for q in questions if q.get('review')]
            if not questions:
                print(Fore.YELLOW + "No questions flagged for review found." + Style.RESET_ALL)
                return
            print(Fore.MAGENTA + f"Starting review session for {len(questions)} flagged questions." + Style.RESET_ALL)

        random.shuffle(questions)
        
        if max_q == 0:
            max_q = len(questions)

        if len(questions) < max_q:
            max_q = len(questions)
            if max_q == 0:
                print("No questions found for the selected category.")
                return
            print(f"Not enough questions, setting quiz length to {max_q}")
        
        quiz_questions = questions[:max_q]
        
        category_stats = {cat: {'asked': 0, 'correct': 0} for cat in all_categories}
        
        start_time = datetime.now()
        print(f"\nStarting quiz with {len(quiz_questions)} questions... (press Ctrl+D to exit anytime)")
        
        correct = 0
        asked = 0
        for i, q in enumerate(quiz_questions):
            asked += 1
            cat = q['category']
            if cat:
                category_stats.setdefault(cat, {'asked': 0, 'correct': 0})['asked'] += 1
            
            if i > 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                avg_time = elapsed / i
                remaining_q = len(quiz_questions) - i
                remaining_time = timedelta(seconds=int(avg_time * remaining_q))
                remaining_str = str(remaining_time)
            else:
                remaining_str = "..."
            
            print(Fore.CYAN + f"[{asked}/{len(quiz_questions)}] Remaining: {remaining_str} Category: {q['category']}" + Style.RESET_ALL)
            print(Fore.YELLOW + f"Q: {q['prompt']}" + Style.RESET_ALL)
            
            q_type = q.get('type', 'command')
            is_correct = False
            user_answer_str = ""

            if q_type == 'live_k8s_edit':
                if not self.cluster_name:
                    print(Fore.RED + "Cannot run live exercise: session not initialized for a cluster." + Style.RESET_ALL)
                    continue
                is_correct, user_answer_str = self._run_one_exercise(q)
            elif q_type == 'yaml_edit':
                if not yaml:
                    print(Fore.RED + "YAML questions require 'PyYAML'. Skipping." + Style.RESET_ALL)
                    continue
                with tempfile.NamedTemporaryFile(mode='w+', suffix=".yaml", delete=False, encoding='utf-8') as tmp:
                    tmp.write(q.get('starting_yaml', ''))
                    tmp_path = tmp.name
                
                editor = os.environ.get('EDITOR', 'vim')
                print(f"Opening a temp file in '{editor}' for you to edit...")
                try:
                    subprocess.run([editor, tmp_path], check=True)
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    print(Fore.RED + f"Error opening editor '{editor}': {e}. Skipping." + Style.RESET_ALL)
                    os.remove(tmp_path)
                    continue
                
                with open(tmp_path, 'r', encoding='utf-8') as f:
                    user_answer_str = f.read()
                os.remove(tmp_path)

                try:
                    user_data = yaml.safe_load(user_answer_str) or {}
                    correct_data = yaml.safe_load(q.get('correct_yaml', ''))
                    is_correct = (user_data == correct_data)
                except yaml.YAMLError as e:
                    print(Fore.RED + f"Your response was not valid YAML: {e}" + Style.RESET_ALL)
                
                if not is_correct:
                    print(Fore.RED + "Incorrect. Correct YAML:" + Style.RESET_ALL)
                    print(Fore.GREEN + q.get('correct_yaml', '') + Style.RESET_ALL)
                
                log_expected_answer = (q.get('correct_yaml', '')[:200] + '...') if len(q.get('correct_yaml', '')) > 200 else q.get('correct_yaml', '')
                self.logger.info(f"Question {asked}/{len(quiz_questions)}: type={q_type} prompt=\"{q['prompt']}\" expected=\"{log_expected_answer}\" answer=\"{user_answer_str}\" result=\"{'correct' if is_correct else 'incorrect'}\"")

            else: # command
                try:
                    user_answer_str = input('Your answer: ').strip()
                except EOFError:
                    print()
                    break
                is_correct = commands_equivalent(user_answer_str, q['response'])
                if not is_correct:
                    print(Fore.RED + "Incorrect. Correct answer: " + Style.RESET_ALL + Fore.GREEN + q['response'] + Style.RESET_ALL)
                self.logger.info(f"Question {asked}/{len(quiz_questions)}: prompt=\"{q['prompt']}\" expected=\"{q['response']}\" answer=\"{user_answer_str}\" result=\"{'correct' if is_correct else 'incorrect'}\"")

            if is_correct:
                print(Fore.GREEN + 'Correct!' + Style.RESET_ALL)
                correct += 1
                if cat:
                    category_stats.setdefault(cat, {'asked': 0, 'correct': 0})['correct'] += 1
            
            if q.get('explanation'):
                level = Fore.GREEN if is_correct else Fore.RED
                print(level + f"Explanation: {q['explanation']}" + Style.RESET_ALL)
            
            print() # newline after explanation

            try:
                if review_only:
                    review = input("Un-flag this question? [y/N]: ").strip().lower()
                    if review.startswith('y'):
                        unmark_question_for_review(data_file, q['category'], q['prompt'])
                        print(Fore.MAGENTA + "Question un-flagged." + Style.RESET_ALL)
                else:
                    review = input("Flag this question for review? [y/N]: ").strip().lower()
                    if review.startswith('y'):
                        mark_question_for_review(data_file, q['category'], q['prompt'])
                        print(Fore.MAGENTA + "Question flagged for review." + Style.RESET_ALL)
            except (EOFError, KeyboardInterrupt):
                print()
                break
            print() # newline

        end_time = datetime.now()
        duration = end_time - start_time
        duration_fmt = str(duration).split('.')[0]
        
        print('--- Quiz Finished ---')
        print(f'Score: {correct}/{asked}')
        if asked > 0:
            pct = (correct / asked) * 100
            print(f'Percentage: {pct:.1f}%')
        print(f'Time taken: {duration_fmt}')
        
        history_entry = {
            'timestamp': datetime.now().isoformat(),
            'num_questions': asked,
            'num_correct': correct,
            'duration': duration_fmt,
            'data_file': data_file,
            'category_filter': category_filter,
            'per_category': category_stats
        }
        
        try:
            history = []
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, 'r') as f:
                    history = json.load(f)
            history.append(history_entry)
            with open(HISTORY_FILE, 'w') as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            print(f"Error saving quiz history: {e}")

    def _run_one_exercise(self, q):
        """Handles a single live Kubernetes question."""
        is_correct = False
        user_yaml_str = ''
        editor = os.environ.get('EDITOR', 'vim')
        
        while True:
            with tempfile.NamedTemporaryFile(mode='w+', suffix=".yaml", delete=False, encoding='utf-8') as tmp_yaml:
                tmp_yaml.write(q.get('starting_yaml', ''))
                tmp_yaml_path = tmp_yaml.name

            print(f"Opening a temp file in '{editor}' for you to edit...")
            try:
                subprocess.run([editor, tmp_yaml_path], check=True)
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                print(Fore.RED + f"Error opening editor '{editor}': {e}. Skipping question." + Style.RESET_ALL)
                os.remove(tmp_yaml_path)
                break 

            with open(tmp_yaml_path, 'r', encoding='utf-8') as f:
                user_yaml_str = f.read()
            os.remove(tmp_yaml_path)

            print("Applying your YAML to the cluster...")
            apply_proc = subprocess.run(
                ['kubectl', 'apply', '-f', '-'],
                input=user_yaml_str, text=True, capture_output=True
            )
            if apply_proc.returncode != 0:
                print(Fore.RED + "Error applying YAML:" + Style.RESET_ALL)
                print(apply_proc.stderr)
            else:
                print("Running validation script...")
                with tempfile.NamedTemporaryFile(mode='w+', suffix=".sh", delete=False, encoding='utf-8') as tmp_assert:
                    tmp_assert.write(q.get('assert_script', 'exit 1'))
                    tmp_assert_path = tmp_assert.name
                
                os.chmod(tmp_assert_path, 0o755)
                assert_proc = subprocess.run(['bash', tmp_assert_path], capture_output=True, text=True)
                os.remove(tmp_assert_path)

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
        
        return is_correct, user_yaml_str

    def cleanup(self):
        """Deletes the EKS cluster and cleans up local files."""
        if not self.cluster_name or self.cluster_name == "pre-configured":
            return  # Nothing to cleanup

        print(Fore.YELLOW + f"Deleting EKS cluster '{self.cluster_name}'..." + Style.RESET_ALL)
        try:
            # Hide verbose output
            subprocess.run([
                'eksctl', 'delete', 'cluster',
                '--name', self.cluster_name,
                '--region', self.region
            ], check=True, capture_output=True, text=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(Fore.RED + f"Failed to delete EKS cluster '{self.cluster_name}': {e}" + Style.RESET_ALL)

        if self.kubeconfig_path and os.path.exists(self.kubeconfig_path):
            os.remove(self.kubeconfig_path)
        if 'KUBECONFIG' in os.environ and os.environ.get('KUBECONFIG') == self.kubeconfig_path:
            del os.environ['KUBECONFIG']
        
        self.cluster_name = None

