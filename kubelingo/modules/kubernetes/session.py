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

def check_dependencies(*commands):
    """Check if all command-line tools in `commands` are available."""
    missing = []
    for cmd in commands:
        if not shutil.which(cmd):
            missing.append(cmd)
    return missing

class NewSession(StudySession):
    """A study session for live Kubernetes exercises on a temporary EKS cluster or existing context."""

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

    def run_exercises(self, exercises):
        """Dispatch to either command-line quiz or live cluster exercises."""
        # Command-line kubectl quiz
        if self.mode == 'cli':
            print(Fore.YELLOW + "Starting kubectl command-line quiz..." + Style.RESET_ALL)
            try:
                from kubelingo.cli import run_quiz
            except ImportError:
                print(Fore.RED + "Internal error: cannot launch command-line quiz." + Style.RESET_ALL)
                return
            # exercises is the path to the JSON quiz data file
            run_quiz(exercises, 0)
            return
        # Live cluster exercises
        if self.mode == 'live':
            try:
                from kubelingo.cli import load_questions
            except ImportError:
                print(Fore.RED + "Internal error: cannot load live exercises." + Style.RESET_ALL)
                return
            # Load only live exercises
            all_qs = load_questions(exercises)
            live_qs = [q for q in all_qs if q.get('type') == 'live_k8s_edit']
            if not live_qs:
                print(Fore.YELLOW + "No live Kubernetes exercises found in data file." + Style.RESET_ALL)
                return
            for i, q in enumerate(live_qs, 1):
                print(f"\n{Fore.CYAN}=== Live Kubernetes Exercise {i}/{len(live_qs)} ==={Style.RESET_ALL}")
                print(Fore.YELLOW + f"Q: {q['prompt']}" + Style.RESET_ALL)
                is_correct, user_yaml = self._run_one_exercise(q)
                exp = q.get('assert_script', '')
                log_ans = (user_yaml[:200] + '...') if len(user_yaml) > 200 else user_yaml
                log_exp = (exp[:200] + '...') if len(exp) > 200 else exp
                self.logger.info(
                    f"Question {i}/{len(live_qs)}: prompt=\"{q['prompt']}\" expected=\"{log_exp}\""
                    f" answer=\"{log_ans}\" result=\"{'correct' if is_correct else 'incorrect'}\""
                )
            return
        print(Fore.RED + "Session mode not set. Cannot run exercises." + Style.RESET_ALL)

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

