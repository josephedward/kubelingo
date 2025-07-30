import os
import pty
import re
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any

from kubelingo.modules.kubernetes.answer_checker import save_transcript, evaluate_transcript
from kubelingo.question import Question, ValidationStep
from kubelingo.utils.config import LOGS_DIR, ROOT
from kubelingo.utils.ui import Fore, Style


@dataclass
class StepResult:
    """Holds the result of a single validation step."""
    step: ValidationStep
    success: bool
    stdout: str
    stderr: str


@dataclass
class ShellResult:
    """Encapsulates all outcomes of a shell-based exercise."""
    success: bool
    step_results: List[StepResult] = field(default_factory=list)
    transcript_path: Path = None
 
# Matcher evaluation helper
def _evaluate_matcher(matcher: Dict[str, Any], stdout: str, stderr: str, exit_code: int) -> bool:
    """
    Evaluate a matcher dict against process output.
    Supported matcher keys: exit_code, contains (str or list), regex (str), regex_flags (list), jsonpath (dot.notation), value.
    Returns True if all specified criteria are met.
    """
    # Default to exit code success if no matcher specified
    if not matcher:
        return exit_code == 0
    # exit_code
    if 'exit_code' in matcher and exit_code != matcher['exit_code']:
        return False
    # contains
    if 'contains' in matcher:
        needles = matcher['contains']
        if isinstance(needles, (list, tuple)):
            for sub in needles:
                if sub not in stdout:
                    return False
        else:
            if needles not in stdout:
                return False
    # regex
    if 'regex' in matcher:
        flags = 0
        for flag in matcher.get('regex_flags', []):
            if flag.upper() == 'IGNORECASE':
                flags |= re.IGNORECASE
        if not re.search(matcher['regex'], stdout, flags):
            return False
    # simple JSONPath-like support
    if 'jsonpath' in matcher:
        try:
            data = json.loads(stdout)
            expr = matcher['jsonpath'].lstrip('.')
            val = data
            for part in expr.split('.'):
                if isinstance(val, list):
                    val = val[int(part)]
                else:
                    val = val.get(part)
            if 'value' in matcher:
                if val != matcher['value']:
                    return False
            else:
                if val is None:
                    return False
        except Exception:
            return False
    return True


def spawn_pty_shell():
    """Spawn an embedded PTY shell sandbox (bash) on the host."""
    try:
        from kubelingo.bridge import rust_bridge
    except ImportError:
        rust_bridge = None
    # Use Rust PTY shell if available
    if rust_bridge and rust_bridge.is_available():
        if rust_bridge.run_pty_shell():
            return
        else:
            print(f"{Fore.YELLOW}Rust PTY shell failed, falling back to Python implementation.{Style.RESET_ALL}")
    if not sys.stdout.isatty():
        print(f"{Fore.RED}No TTY available for PTY shell. Aborting.{Style.RESET_ALL}")
        return
    print(f"\n{Fore.CYAN}--- Starting Embedded PTY Shell ---{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}This is a native shell on your machine.{Style.RESET_ALL}")
    print(f"{Fore.GREEN}Type 'exit' or press Ctrl-D to end.{Style.RESET_ALL}")
    print(f"{Fore.GREEN}Inside the shell, use '-h' or '--help' (e.g. 'kubectl get pods -h') to view usage tips.{Style.RESET_ALL}")
    init_script_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".sh") as f:
            # Silence the zsh deprecation warning on macOS
            f.write("export BASH_SILENCE_DEPRECATION_WARNING=1\n")
            # Set the custom prompt
            f.write("export PS1='(kubelingo-sandbox)$ '\n")
            # Add common aliases
            f.write("alias k='kubectl'\n")
            # Source user's .bash_profile if it exists, to not break their setup.
            bash_profile = Path.home() / ".bash_profile"
            if bash_profile.exists():
                f.write(f"source {bash_profile}\n")
            init_script_path = f.name
        
        # Use --init-file to load our custom config for the login shell.
        pty.spawn(['bash', '--login', '--init-file', init_script_path])
    except Exception as e:
        print(f"{Fore.RED}Error launching PTY shell: {e}{Style.RESET_ALL}")
    finally:
        if init_script_path and os.path.exists(init_script_path):
            os.unlink(init_script_path)
    print(f"\n{Fore.CYAN}--- PTY Shell Session Ended ---{Style.RESET_ALL}\n")

def launch_container_sandbox():
    """Build and launch a Docker container sandbox for Kubelingo."""
    docker = shutil.which('docker')
    if not docker:
        print(f"❌ {Fore.RED}Docker not found.{Style.RESET_ALL} Please install Docker and ensure it is running.")
        return
    if subprocess.run(['docker','info'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        print(f"❌ {Fore.RED}Cannot connect to Docker daemon.{Style.RESET_ALL}")
        print("Please ensure the Docker daemon is running before launching the container sandbox.")
        return
    dockerfile = os.path.join(ROOT, 'docker', 'sandbox', 'Dockerfile')
    if not os.path.exists(dockerfile):
        print(f"❌ Dockerfile not found at {dockerfile}. Ensure docker/sandbox/Dockerfile exists.")
        return
    image = 'kubelingo/sandbox:latest'
    # Build image if missing
    if subprocess.run(['docker','image','inspect', image], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        print("🛠️  Building sandbox Docker image (this may take a minute)...")
        build = subprocess.run(['docker','build','-t', image, '-f', dockerfile, ROOT], capture_output=True, text=True)
        if build.returncode != 0:
            print(f"❌ {Fore.RED}Failed to build sandbox image.{Style.RESET_ALL}")
            print(build.stderr)
            return
    print(f"\n📦 {Fore.CYAN}--- Launching Docker Container Sandbox ---{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}This is an isolated container. Your current directory is mounted at /workspace.{Style.RESET_ALL}")
    print(f"{Fore.GREEN}Type 'exit' or press Ctrl-D to end.{Style.RESET_ALL}")
    print(f"{Fore.GREEN}Inside the container, use '-h' or '--help' (e.g. 'kubectl get pods -h') for command help.{Style.RESET_ALL}")
    cwd = os.getcwd()
    try:
        subprocess.run([
            'docker', 'run', '--rm', '-it', '--network', 'none',
            '-v', f'{cwd}:/workspace',
            '-w', '/workspace',
            image
        ], check=True)
    except subprocess.CalledProcessError:
        print(f"📦 {Fore.RED}Failed to start Docker container.{Style.RESET_ALL}")
    except KeyboardInterrupt:
        pass
    finally:
        print(f"\n📦 {Fore.CYAN}--- Docker Container Session Ended ---{Style.RESET_ALL}\n")

def run_shell_with_setup(question: Question, use_docker=False, ai_eval=False):
    """
    Runs a complete, isolated exercise in a temporary workspace.

    - Sets up initial files and prerequisite commands.
    - Spawns a shell (PTY or Docker).
    - Runs validation steps upon exit.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        original_dir = os.getcwd()
        os.chdir(workspace)

        try:
            # 1. Setup initial files (handles legacy 'initial_yaml' for compatibility)
            initial_files = question.initial_files
            if not initial_files and question.initial_yaml:
                initial_files = {'exercise.yaml': question.initial_yaml}
            
            for filename, content in initial_files.items():
                (workspace / filename).write_text(content)

            # 2. Run pre-shell commands (handles legacy 'initial_cmds')
            pre_shell_cmds = question.pre_shell_cmds or question.initial_cmds
            for cmd in pre_shell_cmds:
                subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)

            # 3. Spawn shell for user interaction
            sandbox_func = launch_container_sandbox if use_docker else spawn_pty_shell
            # Always capture full terminal transcript and Vim commands log
            transcript_file = workspace / "transcript.log"
            os.environ['KUBELINGO_TRANSCRIPT_FILE'] = str(transcript_file)
            vim_log_file = workspace / "vim.log"
            os.environ['KUBELINGO_VIM_LOG'] = str(vim_log_file)

            # Launch the sandbox shell
            sandbox_func()
            # Clear sandbox logging env vars
            if 'KUBELINGO_TRANSCRIPT_FILE' in os.environ:
                del os.environ['KUBELINGO_TRANSCRIPT_FILE']
            if 'KUBELINGO_VIM_LOG' in os.environ:
                del os.environ['KUBELINGO_VIM_LOG']
            # Persist the transcript for this question
            transcript_path = None
            try:
                if transcript_file.exists():
                    content = transcript_file.read_text(encoding='utf-8')
                    transcript_path = save_transcript(question.id, content)
                    if transcript_path:
                        print(f"{Fore.CYAN}Transcript saved to {transcript_path}{Style.RESET_ALL}")
            except Exception:
                transcript_path = None

            # 4. Run validation steps (handles legacy 'validations')
            validation_steps = question.validation_steps or question.validations
            step_results: List[StepResult] = []
            if not validation_steps:
                print(f"{Fore.YELLOW}Warning: No validation steps found for this question.{Style.RESET_ALL}")
            else:
                step_result_dicts = evaluate_transcript(validation_steps)
                step_results = [StepResult(**d) for d in step_result_dicts]

            # Determine overall success by deterministic steps
            overall_success = all(r.success for r in step_results) if step_results else True

            # 5. AI Evaluation (optional, as a "second opinion" if deterministic checks fail)
            if ai_eval and not overall_success and transcript_file.exists():
                print(f"{Fore.YELLOW}Deterministic checks failed. Getting a second opinion from AI...{Style.RESET_ALL}")
                from kubelingo.modules.ai_evaluator import AIEvaluator
                transcript = transcript_file.read_text(encoding='utf-8')
                vim_log = vim_log_file.read_text(encoding='utf-8') if vim_log_file.exists() else None

                evaluator = AIEvaluator()
                from dataclasses import asdict
                q_dict = asdict(question)
                ai_result = evaluator.evaluate(q_dict, transcript, vim_log)
                print(f"{Fore.CYAN}AI Evaluator says: {ai_result.get('reasoning', 'No reasoning.')}{Style.RESET_ALL}")
                
                # AI result can override the deterministic failure.
                if ai_result.get('correct', False):
                    overall_success = True

            return ShellResult(success=overall_success, step_results=step_results, transcript_path=transcript_path)

        except subprocess.CalledProcessError as e:
            print(f"{Fore.RED}A setup command failed: {e.cmd}{Style.RESET_ALL}")
            print(e.stdout or e.stderr)
            return ShellResult(success=False, step_results=[], transcript_path=None)
        except Exception as e:
            print(f"{Fore.RED}An unexpected error occurred: {e}{Style.RESET_ALL}")
            return ShellResult(success=False, step_results=[], transcript_path=None)
        finally:
            os.chdir(original_dir)
