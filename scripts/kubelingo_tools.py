#!/usr/bin/env python3
"""
Kubelingo Tools: An interactive menu for running development and maintenance scripts.
"""

import sys
import subprocess
from pathlib import Path

try:
    import questionary
except ImportError:
    print("Error: 'questionary' library not found. Please install it with: pip install questionary", file=sys.stderr)
    sys.exit(1)

# Determine directories
scripts_dir = Path(__file__).resolve().parent
repo_root = scripts_dir.parent

# Adjust sys.path to import local helper modules
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))


def _run_script(script_name: str, *args):
    """Helper to run a script from the scripts directory."""
    script_path = scripts_dir / script_name
    if not script_path.exists():
        print(f"Error: Script '{script_path}' not found.", file=sys.stderr)
        return
    command = [sys.executable, str(script_path)] + list(args)
    print(f"Running: {' '.join(command)}")
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running script {script_name}: {e}", file=sys.stderr)
    except KeyboardInterrupt:
        print(f"\nScript {script_name} interrupted.", file=sys.stderr)


def main():
    """Display a menu to run a tool script."""
    tasks = {
        "bug_ticket.py": lambda: _run_script("bug_ticket.py"),
        "consolidator.py": lambda: _run_script("consolidator.py"),
        "generator.py": lambda: _run_script("generator.py"),
        "question_manager.py": lambda: _run_script("question_manager.py"),
        "sqlite_manager.py": lambda: _run_script("sqlite_manager.py"),
        "yaml_manager.py": lambda: _run_script("yaml_manager.py"),
    }
    
    while True:
        choice = questionary.select(
            "Select a tool script to run:",
            choices=list(tasks.keys()) + [questionary.Separator(), "Exit"],
            use_indicator=True
        ).ask()

        if not choice or choice == "Exit":
            print("Exiting tool scripts.")
            break
        
        # Run the selected script
        tasks[choice]()
        
        print() # Add a newline for better spacing
        if not questionary.confirm("Run another script?", default=True).ask():
            print("Exiting tool scripts.")
            break
        print() # Add a newline for better spacing


if __name__ == '__main__':
    main()
