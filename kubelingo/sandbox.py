import os
import pty
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict

from kubelingo.modules.kubernetes.answer_checker import save_transcript
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
    os.environ['PS1'] = '(kubelingo-sandbox)$ '
    try:
        pty.spawn(['bash', '--login'])
    except Exception as e:
        print(f"{Fore.RED}Error launching PTY shell: {e}{Style.RESET_ALL}")
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
            transcript_path = ''
            try:
                if transcript_file.exists():
                    content = transcript_file.read_text(encoding='utf-8')
                    transcript_path = save_transcript(question.id, content) or ''
                    print(f"{Fore.CYAN}Transcript saved to {transcript_path}{Style.RESET_ALL}")
            except Exception:
                transcript_path = ''

            # 4. Run validation steps (handles legacy 'validations')
            validation_steps = question.validation_steps or question.validations
            step_results: List[StepResult] = []
            if not validation_steps:
                print(f"{Fore.YELLOW}Warning: No validation steps found for this question.{Style.RESET_ALL}")
            else:
                for step in validation_steps:
                    proc = subprocess.run(step.cmd, shell=True, check=False, capture_output=True, text=True)
                    expected_code = step.matcher.get('exit_code', 0)
                    success = (proc.returncode == expected_code)
                    step_results.append(StepResult(step=step, success=success, stdout=proc.stdout or '', stderr=proc.stderr or ''))

            # 5. AI Evaluation (optional, if enabled and deterministic checks passed)
            if ai_eval and transcript_file.exists():
                from kubelingo.modules.ai_evaluator import AIEvaluator
                transcript = transcript_file.read_text(encoding='utf-8')
                evaluator = AIEvaluator()
                from dataclasses import asdict
                q_dict = asdict(question)
                ai_result = evaluator.evaluate(q_dict, transcript)
                print(f"{Fore.CYAN}AI Evaluator says: {ai_result.get('reasoning', 'No reasoning.')}{Style.RESET_ALL}")
                success = ai_result.get('correct', False)
                return ShellResult(success=success, step_results=step_results, transcript_path=transcript_path)

            # Determine overall success by deterministic steps
            overall_success = all(r.success for r in step_results) if step_results else True
            return ShellResult(success=overall_success, step_results=step_results, transcript_path=transcript_path)

        except subprocess.CalledProcessError as e:
            print(f"{Fore.RED}A setup command failed: {e.cmd}{Style.RESET_ALL}")
            print(e.stdout or e.stderr)
            return ShellResult(success=False, step_results=[], transcript_path='')
        except Exception as e:
            print(f"{Fore.RED}An unexpected error occurred: {e}{Style.RESET_ALL}")
            return ShellResult(success=False, step_results=[], transcript_path='')
        finally:
            os.chdir(original_dir)
