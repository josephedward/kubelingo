"""
sandbox.py: Manages the creation of sandboxed environments (PTY shell, Docker container) for exercises.
"""
import os
import pty
import shutil
import subprocess
import sys

try:
    from colorama import Fore, Style
except ImportError:
    # Fallback if colorama is not available
    class Fore:
        RED = GREEN = YELLOW = CYAN = MAGENTA = ""
    class Style:
        RESET_ALL = ""
        DIM = ""

# Project root
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

def spawn_pty_shell():
    """Spawn a real bash shell in a PTY sandbox, preferring Rust implementation if available."""
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
    # Fallback: Python pty.spawn
    if not sys.stdout.isatty():
        print(f"{Fore.RED}No TTY available for PTY shell. Aborting.{Style.RESET_ALL}")
        return
    print(f"{Fore.CYAN}Starting PTY shell (native, no isolation)...{Style.RESET_ALL}")
    os.environ['PS1'] = '(kubelingo-sandbox)$ '
    try:
        pty.spawn(['bash', '--login'])
    except Exception as e:
        print(f"{Fore.RED}Error launching PTY shell: {e}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}PTY shell session ended.{Style.RESET_ALL}")

def launch_container_sandbox():
    """Build and launch a Docker container sandbox for Kubelingo."""
    docker = shutil.which('docker')
    if not docker:
        print("❌ Docker not found. Please install Docker to use container sandbox mode.")
        return
    dockerfile = os.path.join(ROOT, 'docker', 'sandbox', 'Dockerfile')
    if not os.path.exists(dockerfile):
        print(f"❌ Dockerfile not found at {dockerfile}. Ensure docker/sandbox/Dockerfile exists.")
        return
    image = 'kubelingo/sandbox:latest'
    # Check if image exists locally
    if subprocess.run(['docker','image','inspect', image], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        print("🛠️  Building sandbox Docker image (this may take a minute)...")
        if subprocess.run(['docker','build','-t', image, '-f', dockerfile, ROOT]).returncode != 0:
            print("❌ Failed to build sandbox image. Please run:")
            print(f"    docker build -t kubelingo/sandbox:latest -f {dockerfile} {ROOT}")
            return
    print("📦 Launching container sandbox environment. Press Ctrl-D or type 'exit' to exit.")
    print("- Isolation: Full network isolation, fixed toolset (bash, vim, kubectl).")
    print("- Requirements: Docker installed and running.")
    cwd = os.getcwd()
    try:
        subprocess.run([
            'docker', 'run', '--rm', '-it', '--network', 'none',
            '-v', f'{cwd}:/workspace',
            '-w', '/workspace',
            image
        ])
    except KeyboardInterrupt:
        pass
    return
