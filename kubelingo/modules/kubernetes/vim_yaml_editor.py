import os
import subprocess
import tempfile
import shlex
import difflib
import time

from kubelingo.utils.validation import validate_yaml_structure, is_yaml_subset
from kubelingo.utils.ui import Fore, Style, yaml
from kubelingo.modules.kubernetes.answer_checker import check_answer, save_transcript


class VimrunnerException(Exception):
    pass

class Client(object):
    """Client to control a Vim server instance."""
    def __init__(self, server):
        self.server = server

    def type(self, keys):
        """Send keystrokes to the Vim server."""
        cmd = self.server.executable + ['--servername', self.server.name, '--remote-send', keys]
        subprocess.check_call(cmd)
        # Allow Vim time to process the keys.
        time.sleep(0.1)

    def command(self, command):
        """Execute an Ex command in Vim."""
        # Use --remote-expr to execute a command and get output.
        remote_expr = f"execute('{command}')"
        cmd = self.server.executable + ['--servername', self.server.name, '--remote-expr', remote_expr]
        return subprocess.check_output(cmd, universal_newlines=True)

    def write(self):
        """Write the current buffer to file."""
        self.type('<Esc>:w<CR>')


class Server(object):
    """Starts and manages a Vim server process."""
    def __init__(self, executable='vim'):
        self.executable = [executable]
        # Generate a unique server name to avoid conflicts
        self.name = f"KUBELINGO-TEST-{os.getpid()}"
        self.process = None

    def start(self, file_to_edit=None):
        """Starts the Vim server in the background."""
        # Use --nofork to keep gvim process in the foreground for Popen to manage
        cmd = self.executable + ['--servername', self.name]

        # Configure vim for 2-space tabs
        if 'vim' in os.path.basename(self.executable[0]):
            cmd.extend(['-c', 'set tabstop=2 shiftwidth=2 expandtab'])

        # --nofork is a gvim-specific flag, not applicable to terminal vim
        if 'gvim' in self.executable[0] or 'mvim' in self.executable[0]:
            cmd.append('--nofork')
            
        if file_to_edit:
            cmd.append(file_to_edit)

        self.process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Wait for the server to initialize by polling --serverlist.
        for _ in range(20):  # Try for 2 seconds
            time.sleep(0.1)
            try:
                serverlist = subprocess.check_output(self.executable + ['--serverlist'], text=True, stderr=subprocess.DEVNULL)
                if self.name in serverlist.splitlines():
                    return Client(self)
            except (subprocess.CalledProcessError, FileNotFoundError):
                # This can happen if vim is starting up.
                continue

        # If server did not start, clean up and raise error.
        self.kill()
        raise VimrunnerException(f"Failed to start Vim server '{self.name}'.")

    def kill(self):
        """Stops the Vim server process."""
        if self.process:
            # First, try a graceful shutdown using a remote command
            try:
                cmd = self.executable + ['--servername', self.name, '--remote-expr', 'execute("qa!")']
                subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except (subprocess.CalledProcessError, FileNotFoundError):
                # If graceful shutdown fails, terminate the process
                self.process.terminate()

            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()  # Force kill if it doesn't terminate


class VimYamlEditor:
    """
    Provides functionality to create, edit, and validate Kubernetes YAML manifests
    interactively using Vim.
    """
    def create_yaml_exercise(self, exercise_type, template_data=None):
        """Creates a YAML exercise template for a given resource type."""
        data = template_data or {}
        if exercise_type == "pod":
            name = data.get("name", "nginx-pod")
            labels = data.get("labels", {"app": "nginx"})
            container_name = data.get("container_name", "nginx")
            image = data.get("image", "nginx:1.20")
            ports = data.get("ports", [{"containerPort": 80}])
            return {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {"name": name, "labels": labels},
                "spec": {"containers": [{"name": container_name, "image": image, "ports": ports}]}
            }
        if exercise_type == "deployment":
            name = data.get("name", "nginx-deployment")
            labels = data.get("labels", {"app": "nginx"})
            container_name = data.get("container_name", "nginx")
            image = data.get("image", "nginx:1.14.2")
            replicas = data.get("replicas", 1)
            return {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": name, "labels": labels},
                "spec": {
                    "replicas": replicas,
                    "selector": {"matchLabels": labels},
                    "template": {
                        "metadata": {"labels": labels},
                        "spec": {
                            "containers": [{
                                "name": container_name,
                                "image": image,
                                "ports": [{"containerPort": 80}]
                            }]
                        }
                    }
                }
            }
        if exercise_type == "service":
            name = data.get("name", "my-service")
            selector = data.get("selector", {"app": "MyApp"})
            ports = data.get("ports", [{"protocol": "TCP", "port": 80, "targetPort": 80}])
            svc_type = data.get("type", "ClusterIP")
            return {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {"name": name},
                "spec": {"type": svc_type, "selector": selector, "ports": ports}
            }
        if exercise_type == "configmap":
            name = data.get("name", "my-configmap")
            cm_data = data.get("data", {"key": "value"})
            return {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {"name": name},
                "data": cm_data
            }
        if exercise_type == "secret":
            name = data.get("name", "my-secret")
            secret_type = data.get("type", "Opaque")
            sec_data = data.get("data", {"key": "value"})
            return {
                "apiVersion": "v1",
                "kind": "Secret",
                "metadata": {"name": name},
                "type": secret_type,
                "data": sec_data
            }
        if exercise_type == "ingress":
            name = data.get("name", "my-ingress")
            rules = data.get("rules", [{"host": "example.com", "http": {"paths": [{"path": "/", "backend": {"serviceName": "my-service", "servicePort": 80}}]}}])
            return {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "Ingress",
                "metadata": {"name": name},
                "spec": {"rules": rules}
            }
        raise ValueError(f"Unknown exercise type: {exercise_type}")
    
    def edit_yaml_with_vim(self, yaml_content, filename="exercise.yaml", prompt=None, _vim_args=None, _timeout=300):
        """
        Opens YAML content in Vim for interactive editing.
        After editing, parses and returns the YAML as a Python dict, or None on error.
        """
        if prompt:
            print(f"\n{Fore.CYAN}--- Task ---{Style.RESET_ALL}")
            print(prompt)
            print(f"{Fore.CYAN}------------{Style.RESET_ALL}")
            try:
                input("Press Enter to open the editor...")
            except (EOFError, KeyboardInterrupt):
                print("\nEditor launch cancelled.")
                return None

        # Write to a temporary YAML file, injecting the prompt as comments if provided
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode='w', encoding='utf-8') as tmp:
            # Inject prompt at the top of the file as comments for context
            if prompt:
                for line in prompt.splitlines():
                    tmp.write(f"# {line}\n")
                tmp.write("\n")
            # Write the YAML content
            if isinstance(yaml_content, str):
                tmp.write(yaml_content)
            else:
                yaml.dump(yaml_content, tmp, default_flow_style=False)
            tmp_filename = tmp.name
        vimrc_file = None
        try:
            editor_env = os.environ.get('EDITOR', 'vim')
            editor_list = shlex.split(editor_env)
            editor_name = os.path.basename(editor_list[0])

            vim_args = _vim_args or []
            flags = [arg for arg in vim_args if arg != '-S' and not os.path.isfile(arg)]
            scripts = [arg for arg in vim_args if os.path.isfile(arg)]

            # Base command
            cmd = editor_list + flags

            # If using Vim, provide a temp vimrc for consistent settings.
            if 'vim' in editor_name:
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.vimrc', encoding='utf-8') as f:
                    # Ensure Vim is not in 'compatible' mode and backspace works across indents, line breaks, and start of insert
                    f.write("set nocompatible\n")
                    f.write("set backspace=indent,eol,start\n")
                    # Use spaces for tabs and configure indentation
                    f.write("set expandtab\n")
                    f.write("set tabstop=2\n")
                    f.write("set shiftwidth=2\n")
                    f.write("filetype plugin indent on\n")
                    f.write("syntax on\n")
                    vimrc_file = f.name
                # More robustly construct command to ensure -u is in the right place
                cmd = [editor_list[0], '-u', vimrc_file] + editor_list[1:] + flags

            cmd.append(tmp_filename)

            for script in scripts:
                cmd.extend(['-S', script])

            used_fallback = False
            try:
                # Launch editor
                result = subprocess.run(cmd, timeout=_timeout)
            except TypeError:
                used_fallback = True
                result = subprocess.run(cmd)
            except FileNotFoundError as e:
                print(f"\033[31mError launching editor '{editor_env}': {e}\033[0m")
                return None
            except subprocess.TimeoutExpired:
                print(f"\033[31mEditor session timed out after {_timeout} seconds.\033[0m")
                return None
            except KeyboardInterrupt:
                print("\033[33mEditor session interrupted by user.\033[0m")
                return None
            # Warn on non-zero exit
            if result.returncode != 0:
                print(f"{Fore.YELLOW}Warning: Editor '{editor_name}' exited with status {result.returncode}.{Style.RESET_ALL}")
            # Read back edited content
            with open(tmp_filename, 'r', encoding='utf-8') as f:
                content = f.read()
            # Parse YAML if PyYAML is available and timeout fallback not used
            if (not used_fallback) and yaml and hasattr(yaml, 'safe_load'):
                try:
                    parsed = yaml.safe_load(content)
                    if parsed is None:
                        parsed = {}
                except Exception as e:
                    print(f"\03-31mFailed to parse YAML: {e}\033[0m")
                    return None
                # Only accept mappings or sequences
                if not isinstance(parsed, (dict, list)):
                    print(f"\033[31mFailed to parse YAML: invalid content type {type(parsed).__name__}\033[0m")
                    return None
                return parsed
            # Fallback simple parser when PyYAML is not available
            data = {}
            for line in content.splitlines():
                s = line.split('#', 1)[0]
                if not s.strip():
                    continue
                if ':' in s:
                    k, v = s.split(':', 1)
                    data[k.strip()] = v.strip()
            return data
        finally:
            if vimrc_file:
                try:
                    os.unlink(vimrc_file)
                except Exception:
                    pass
            try:
                os.unlink(tmp_filename)
            except Exception:
                pass
    
    def run_progressive_yaml_exercises(self, steps):
        """
        Runs a multi-step YAML editing exercise.
        Each step: prompt, edit in Vim, validate via provided function.
        steps: list of dicts with 'prompt', optional 'starting_yaml', and 'validation_func'.
        Returns True if all steps pass, False on first failure.
        """
        previous = None
        for idx, step in enumerate(steps, start=1):
            prompt = step.get('prompt', '')
            content = step.get('starting_yaml') if idx == 1 else previous
            filename = f"step-{idx}.yaml"
            print(f"\n=== Step {idx}: {prompt} ===")
            result = self.edit_yaml_with_vim(content, filename, prompt=prompt)
            if result is None:
                return False
            # Validate
            validator = step.get('validation_func')
            try:
                valid, _ = validator(result)
            except Exception:
                return False
            if not valid:
                return False
            previous = result
        return True
    
    def run_yaml_edit_question(self, question, index=None):
        """
        Runs a single YAML editing exercise with retry logic.
        question should have 'prompt', 'starting_yaml', 'correct_yaml' or 'validation_steps', and 'explanation'.
        Returns True if the user produces expected YAML, False otherwise.
        """
        prompt = question.get('prompt', '')
        starting = question.get('starting_yaml')
        expected_raw = question.get('correct_yaml', '') or question.get('answer', '')
        validation_steps = question.get('validation_steps') or question.get('validations')

        if starting is None or (isinstance(starting, str) and not starting.strip()):
            prompt_lower = prompt.lower()
            if 'deployment' in prompt_lower:
                starting = self.create_yaml_exercise('deployment')
            elif 'pod' in prompt_lower:
                starting = self.create_yaml_exercise('pod')
            elif 'service' in prompt_lower:
                starting = self.create_yaml_exercise('service')
            elif 'configmap' in prompt_lower:
                starting = self.create_yaml_exercise('configmap')
            elif 'secret' in prompt_lower:
                starting = self.create_yaml_exercise('secret')
            elif 'ingress' in prompt_lower:
                starting = self.create_yaml_exercise('ingress')
            else:
                starting = {}

        while True:
            print(f"\n=== Exercise {index}: {prompt} ===")
            result_obj = self.edit_yaml_with_vim(starting, f"exercise-{index}.yaml", prompt=prompt)
            if result_obj is None:
                return False

            try:
                user_yaml_str = yaml.safe_dump(result_obj, default_flow_style=False)
            except Exception:
                user_yaml_str = str(result_obj)

            validation = validate_yaml_structure(user_yaml_str)
            for err in validation.get('errors', []):
                print(f"{Fore.RED}YAML validation error: {err}{Style.RESET_ALL}")
            for warn in validation.get('warnings', []):
                print(f"{Fore.YELLOW}YAML validation warning: {warn}{Style.RESET_ALL}")
            if not validation.get('valid'):
                print(f"{Fore.RED}YAML structure invalid. Please correct errors in Vim and retry.{Style.RESET_ALL}")
                starting = user_yaml_str
                continue

            is_correct = False
            details = []
            if question.get('id'):
                save_transcript(question['id'], user_yaml_str)

            if validation_steps:
                is_correct, details = check_answer(question)
            elif expected_raw:
                is_correct = is_yaml_subset(subset_yaml_str=expected_raw, superset_yaml_str=user_yaml_str)
            else:
                print(f"{Fore.YELLOW}Warning: No correct answer defined. Skipping check.{Style.RESET_ALL}")
                is_correct = True

            if is_correct:
                print("✅ Correct!")
                if question.get('explanation'):
                    print(f"{Fore.CYAN}Explanation: {question['explanation']}{Style.RESET_ALL}")
                if details:
                    print(f"\n{Fore.CYAN}--- Validation Details ---{Style.RESET_ALL}")
                    for detail in details:
                        color = Fore.GREEN if detail.startswith("PASS") else Fore.YELLOW
                        print(f"{color}{detail}{Style.RESET_ALL}")
                return True

            # Incorrect: show diff or validation errors and retry
            if details:
                print("❌ Validation checks failed.")
                print(f"\n{Fore.CYAN}--- Validation Failures ---{Style.RESET_ALL}")
                for detail in details:
                    if detail.startswith("FAIL"):
                        print(f"{Fore.RED}{detail}{Style.RESET_ALL}")
            elif expected_raw:
                print("❌ YAML does not match expected output.")
                diff = difflib.unified_diff(
                    expected_raw.strip().splitlines(keepends=True),
                    user_yaml_str.strip().splitlines(keepends=True),
                    fromfile='expected.yaml', tofile='your-answer.yaml'
                )
                diff_text = ''.join(diff)
                if diff_text:
                    print(f"{Fore.CYAN}Differences (-expected, +yours):{Style.RESET_ALL}")
                    for line in diff_text.splitlines():
                        if line.startswith('+'):
                            print(f"{Fore.GREEN}{line}{Style.RESET_ALL}")
                        elif line.startswith('-'):
                            print(f"{Fore.RED}{line}{Style.RESET_ALL}")
                        elif line.startswith('@@'):
                            print(f"{Fore.CYAN}{line}{Style.RESET_ALL}")
                        else:
                            print(line)
            else:
                 print("❌ YAML does not match expected output.")

            try:
                retry = input("Try again? (y/N): ").strip().lower().startswith('y')
            except (EOFError, KeyboardInterrupt):
                retry = False

            if not retry:
                if expected_raw:
                    print("\nExpected solution:")
                    print(expected_raw)
                return False
            starting = user_yaml_str


def vim_commands_quiz():
    """Placeholder for a Vim commands quiz."""
    print("Vim commands quiz is not yet implemented.")
