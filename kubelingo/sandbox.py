import os
import pty
import shutil
import subprocess
import sys

from kubelingo.utils.ui import Fore, Style

# Project root imported from centralized config
from kubelingo.utils.config import ROOT
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict

from kubelingo.question import ValidationStep

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
@dataclass
class StepResult:
    step: ValidationStep
    success: bool
    stdout: str
    stderr: str

@dataclass
class ShellResult:
    success: bool
    step_results: List[StepResult]
    transcript_path: str

def run_shell_with_setup(
    pre_shell_cmds: List[str],
    initial_files: Dict[str, str],
    validation_steps: List[ValidationStep],
    use_container: bool = False,
) -> ShellResult:
    """
    Provision a workspace, run pre-shell commands, launch an interactive shell (PTY or container),
    record the session transcript, execute validation steps, and cleanup.
    Returns a ShellResult indicating overall success and per-step details.
    """
    # Create isolated workspace
    workspace = Path(tempfile.mkdtemp(prefix="kubelingo-sandbox-"))
    try:
        # Seed initial files
        for rel_path, content in initial_files.items():
            file_path = workspace / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)
        # Execute pre-shell commands
        for cmd in pre_shell_cmds:
            proc = subprocess.run(cmd, shell=True, cwd=workspace,
                                  capture_output=True, text=True)
            if proc.returncode != 0:
                return ShellResult(False, [], "")
        # Prepare transcript
        transcript = workspace / "session.log"
        # Launch shell session
        if use_container:
            launch_container_sandbox()
        else:
            script_cmd = f'script -q -c "bash --login" {transcript}'
            subprocess.run(script_cmd, shell=True, cwd=workspace)
        # Run validation steps
        results: List[StepResult] = []
        for step in validation_steps:
            res = subprocess.run(step.cmd, shell=True, cwd=workspace,
                                 capture_output=True, text=True)
            ok = res.returncode == 0
            results.append(StepResult(step=step, success=ok,
                                       stdout=res.stdout, stderr=res.stderr))
        overall = all(r.success for r in results)
        return ShellResult(overall, results, str(transcript))
    finally:
        shutil.rmtree(workspace)
