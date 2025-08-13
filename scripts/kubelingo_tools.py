#!/usr/bin/env python3
"""
Kubelingo Tools: A unified orchestrator for development, maintenance, and data management scripts.

This script combines the functionality of several tools:
- An interactive menu for common maintenance tasks.
- A command-line interface for specific operations (e.g., quiz generation, data migration).
- A dynamic script runner to execute other standalone scripts from the `scripts/` directory.
"""

import argparse
import sys
import subprocess
import shutil
import json
import re
import os
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Determine directories
scripts_dir = Path(__file__).resolve().parent
repo_root = scripts_dir.parent

# Load shared context for AI prompts
shared_context_path = repo_root / 'shared_context.md'
if shared_context_path.exists():
    SHARED_CONTEXT = shared_context_path.read_text(encoding='utf-8')
else:
    SHARED_CONTEXT = ''

# Adjust sys.path to import local helper modules
sys.path.insert(0, str(repo_root))

try:
    from kubelingo.database import get_db_connection, get_flagged_questions
except ImportError:
    print("Could not import kubelingo modules. DB-related features might not work.", file=sys.stderr)
    get_db_connection = None
    get_flagged_questions = None


def _run_script(script_name: str, *args):
    """Helper to run a script from the scripts directory."""
    script_path = scripts_dir / script_name
    if not script_path.exists():
        print(f"Error: Script '{script_path}' not found.")
        return
    command = [sys.executable, str(script_path)] + list(args)
    print(f"Running: {' '.join(command)}")
    subprocess.run(command, check=False)


def task_run_bug_ticket():
    """Run bug_ticket.py"""
    _run_script("bug_ticket.py")

def task_run_consolidator():
    """Run consolidator.py"""
    _run_script("consolidator.py")

def task_run_generator():
    """Run generator.py"""
    _run_script("generator.py")

def task_run_question_manager():
    """Run question_manager.py"""
    _run_script("question_manager.py")

def task_run_sqlite_manager():
    """Run sqlite_manager.py"""
    _run_script("sqlite_manager.py")

def task_run_yaml_manager():
    """Run yaml_manager.py"""
    _run_script("yaml_manager.py")

def task_tool_scripts():
    """Display a menu to run a tool script."""
    try:
        import questionary
    except ImportError:
        print("Error: 'questionary' library not found. Please install it with: pip install questionary")
        sys.exit(1)

    tasks = {
        "bug_ticket.py": task_run_bug_ticket,
        "consolidator.py": task_run_consolidator,
        "generator.py": task_run_generator,
        "question_manager.py": task_run_question_manager,
        "sqlite_manager.py": task_run_sqlite_manager,
        "yaml_manager.py": task_run_yaml_manager,
    }
    
    choice = questionary.select(
        "Select a tool script to run:",
        choices=list(tasks.keys()) + [questionary.Separator(), "Back"],
        use_indicator=True
    ).ask()

    if choice and choice != "Back":
        tasks[choice]()


def task_full_migrate_and_cleanup():
    """Full migration and cleanup pipeline."""
    # 1. JSON → YAML
    _run_script('generator.py', 'manifests')
    # 2. Manifest consolidation
    _run_script('consolidate_manifests.py')
    # 3. Merge solutions
    _run_script('merge_solutions.py')
    # 4. (Optional) Convert MD → YAML: not implemented

    # 5. Migrate YAML quizzes into DB
    print("Migrating YAML quizzes into database...")
    subprocess.run(['kubelingo', 'migrate-yaml'], check=False)
    # 6. Import JSON quizzes into DB
    print("Importing JSON quizzes into database...")
    subprocess.run(['kubelingo', 'import-json'], check=False)

    # 7. Backup live DB
    print("Backing up live database...")
    try:
        # Use path from utils to be robust
        from kubelingo.utils.config import get_live_db_path
        db_src = Path(get_live_db_path())
    except (ImportError, FileNotFoundError):
        print("Could not locate live DB. Assuming default path.")
        db_src = Path.home() / '.kubelingo' / 'kubelingo.db'

    backup_dir = repo_root / 'question-data-backup'
    backup_dir.mkdir(exist_ok=True)
    db_dst = backup_dir / 'kubelingo.db.bak'
    if db_src.exists():
        try:
            shutil.copy2(db_src, db_dst)
            print(f"Copied DB to {db_dst}")
        except Exception as e:
            print(f"Failed to backup DB: {e}")
    else:
        print(f"Live DB not found at {db_src}. Skipping backup.")

    # 8. Delete legacy dirs
    print("Deleting legacy directories...")
    qd = repo_root / 'question-data'
    for sub in ['json', 'md', 'manifests', 'yaml-bak', 'solutions']:
        path = qd / sub
        if path.exists():
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                print(f"Removed {path.relative_to(repo_root)}")
            except Exception as e:
                print(f"Failed to remove {path}: {e}")

    print("Full migration and cleanup complete.")


def run_interactive_menu():
    """Display an interactive menu for the application."""
    try:
        import questionary
        from questionary import Separator
    except ImportError:
        print("Error: 'questionary' library not found. Please install it with:")
        print("pip install questionary")
        sys.exit(1)
    
    if not get_db_connection or not get_flagged_questions:
        print("Database modules not loaded. Cannot display question counts.", file=sys.stderr)
        missed_count = 'N/A'
        question_counts = defaultdict(lambda: 'N/A')
    else:
        conn = get_db_connection()
        if not conn:
            print("Could not connect to database.", file=sys.stderr)
            missed_count = 'N/A'
            question_counts = defaultdict(lambda: 'N/A')
        else:
            try:
                missed_count = len(get_flagged_questions(conn))

                cursor = conn.cursor()
                cursor.execute("SELECT category, COUNT(*) FROM questions GROUP BY category")
                rows = cursor.fetchall()
                counts_by_category = {row[0]: row[1] for row in rows}
                
                question_counts = {
                    "Open Ended Questions": counts_by_category.get('basic', 0),
                    "Basic Terminology": 0,  # NOTE: No clear way to count this yet.
                    "Command Syntax": counts_by_category.get('command', 0),
                    "YAML Manifest": counts_by_category.get('manifest', 0),
                }
            except Exception as e:
                print(f"Error querying database for question counts: {e}", file=sys.stderr)
                missed_count = 'N/A'
                question_counts = defaultdict(lambda: 'N/A')
            finally:
                if conn:
                    conn.close()

    tasks = {
        "Study Mode (Socratic Tutor)": lambda: print("Not implemented yet."),
        "Missed Questions": lambda: print("Not implemented yet."),
        "Open Ended Questions": lambda: print("Not implemented yet."),
        "Basic Terminology": lambda: print("Not implemented yet."),
        "Command Syntax": lambda: print("Not implemented yet."),
        "YAML Manifest": lambda: print("Not implemented yet."),
        "API Keys": lambda: print("Not implemented yet."),
        "Cluster Configuration": lambda: print("Not implemented yet."),
        "Tool Scripts": task_tool_scripts,
        "Triaged Questions": lambda: print("Not implemented yet."),
        "Help": lambda: print("Not implemented yet."),
        "Exit App": lambda: sys.exit(0),
    }
    
    while True:
        choice = questionary.select(
            "Select an option:",
            choices=[
                Separator("--- Learn ---"),
                "Study Mode (Socratic Tutor)",
                f"Missed Questions ({missed_count})",
                Separator("--- Drill ---"),
                f"Open Ended Questions ({question_counts['Open Ended Questions']})",
                f"Basic Terminology ({question_counts['Basic Terminology']})",
                f"Command Syntax ({question_counts['Command Syntax']})",
                f"YAML Manifest ({question_counts['YAML Manifest']})",
                Separator("--- Settings ---"),
                "API Keys",
                "Cluster Configuration",
                "Tool Scripts",
                "Triaged Questions",
                "Help",
                Separator(),
                "Exit App"
            ],
            use_indicator=True
        ).ask()

        if choice is None or choice == "Exit App":
            print("Exiting.")
            break

        base_choice = re.sub(r'\s*\([\w/]+\)$', '', choice)
        
        if base_choice in tasks:
            tasks[base_choice]()
        else:
            print("Invalid choice.")

def run_quiz(args):
    """Run the interactive CLI quiz."""
    # Forward remaining args to kubelingo CLI
    sys.argv = ['kubelingo'] + args.quiz_args
    from kubelingo.cli import main as kubelingo_main
    kubelingo_main()

def manage_organize(args):
    """Archive legacy stubs and rename core question-data files."""
    root = repo_root / 'question-data'
    dry_run = args.dry_run
    archive = root / '_archive'
    # Prepare archive subdirs
    for sub in ['json', 'yaml', 'csv', 'md']:
        (archive / sub).mkdir(parents=True, exist_ok=True)
    actions = []
    # Stubs to archive
    for name in ['ckad_questions.json', 'killercoda_ckad.json']:
        src = root / 'json' / name
        if src.exists():
            actions.append((src, archive / 'json' / name))
    for name in ['ckad_questions.yaml', 'ckad_questions.yml']:
        src = root / 'yaml' / name
        if src.exists():
            actions.append((src, archive / 'yaml' / name))
    # CSV files
    for f in (root / 'csv').glob('*'):
        if f.is_file():
            actions.append((f, archive / 'csv' / f.name))
    # Markdown: strip letter prefixes and archive Killercoda cheat sheet
    md_dir = root / 'md'
    if md_dir.is_dir():
        for p in md_dir.iterdir():
            if not p.is_file():
                continue
            if p.name.lower().startswith('killercoda'):
                actions.append((p, archive / 'md' / p.name))
            else:
                m = re.match(r'^[a-z]\.(.+)', p.name)
                if m:
                    dst = md_dir / m.group(1)
                    actions.append((p, dst))
    # Rename core JSON quizzes
    rename_map = {
        'ckad_quiz_data.json': 'kubernetes.json',
        'ckad_quiz_data_with_explanations.json': 'kubernetes_with_explanations.json',
        'yaml_edit_questions.json': 'yaml_edit.json',
        'vim_quiz_data.json': 'vim.json',
    }
    for old_name, new_name in rename_map.items():
        src = root / 'json' / old_name
        dst = root / 'json' / new_name
        if src.exists():
            actions.append((src, dst))
    # Execute actions
    for src, dst in actions:
        if dry_run:
            print(f"[DRY-RUN] Move: {src} -> {dst}")
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            print(f"Moved: {src} -> {dst}")
    # Remove empty dirs
    for sub in ['json', 'yaml', 'csv', 'md']:
        d = root / sub
        if d.is_dir() and not any(d.iterdir()):
            if dry_run:
                print(f"[DRY-RUN] Remove empty dir: {d}")
            else:
                try:
                    d.rmdir()
                    print(f"Removed empty dir: {d}")
                except OSError:
                    pass

    # (Other management commands such as 'enrich' or 'validate' have been consolidated or moved to legacy.)

def generate_operations(args):
    """Generate the Kubectl operations quiz manifest (delegates to existing script)."""
    _run_script('generator.py', 'kubectl-operations')

def generate_reference(args):
    """Generate the Resource Reference quiz manifest (delegates to existing script)."""
    _run_script('generator.py', 'resource-reference')

def generate_manifests(args):
    """Generate quiz manifests and solutions from JSON quiz data (delegates to existing script)."""
    _run_script('generator.py', 'manifests')

def ckad_export(args):
    """Export CKAD spec CSV to JSON and YAML (delegates to existing script)."""
    script = scripts_dir / 'ckad.py'
    cmd = [sys.executable, str(script), 'export', '--csv', args.csv, '--json', args.json, '--yaml', args.yaml]
    subprocess.run(cmd, check=True)

def ckad_import(args):
    """Import CKAD spec JSON/YAML to CSV (delegates to existing script)."""
    script = scripts_dir / 'ckad.py'
    cmd = [sys.executable, str(script), 'import', '--json', args.json, '--yaml', args.yaml, '--csv', args.csv]
    subprocess.run(cmd, check=True)

def ckad_normalize(args):
    """Normalize CKAD CSV (delegates to existing script)."""
    script = scripts_dir / 'ckad.py'
    cmd = [sys.executable, str(script), 'normalize', '--input', args.input, '--output', args.output]
    subprocess.run(cmd, check=True)

def run_dynamic_script(args):
    """Runs a script from the scripts/ dir based on parsed arguments."""
    script_path = args.script_path
    if script_path.suffix == '.sh':
        cmd = ['bash', str(script_path)] + args.script_args
    else:
        cmd = [sys.executable, str(script_path)] + args.script_args
    try:
        result = subprocess.run(cmd)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        sys.exit(1)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        run_interactive_menu()
        return

    parser = argparse.ArgumentParser(
        prog='kubelingo_tools.py',
        description='Kubelingo toolbox for standalone scripts and maintenance tasks.'
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    # quiz
    quiz_parser = subparsers.add_parser('quiz', help='Run the interactive CLI quiz')
    # Arguments are not defined here; they are collected by parse_known_args.
    quiz_parser.set_defaults(func=run_quiz, quiz_args=[])

    # manage
    manage_parser = subparsers.add_parser('manage', help='Manage question-data')
    manage_sub = manage_parser.add_subparsers(dest='subcommand', required=True)
    org_p = manage_sub.add_parser('organize', help='Archive and rename question-data files')
    org_p.add_argument('--dry-run', action='store_true', help='Preview changes without writing files')
    org_p.set_defaults(func=manage_organize)

    # generate
    gen_parser = subparsers.add_parser('generate', help='Generate quiz manifests')
    gen_sub = gen_parser.add_subparsers(dest='subcommand', required=True)
    gen_ops = gen_sub.add_parser('kubectl-operations', help='Generate Kubectl operations quiz')
    gen_ops.set_defaults(func=generate_operations)
    gen_ref = gen_sub.add_parser('resource-reference', help='Generate Resource Reference quiz')
    gen_ref.set_defaults(func=generate_reference)
    gen_man = gen_sub.add_parser('manifests', help='Generate manifests and solutions from JSON quiz data')
    gen_man.set_defaults(func=generate_manifests)

    # ckad
    ckad_parser = subparsers.add_parser('ckad', help='CKAD CSV/JSON/YAML spec management')
    ckad_sub = ckad_parser.add_subparsers(dest='subcommand', required=True)
    exp = ckad_sub.add_parser('export', help='Export CSV to JSON and YAML spec')
    exp.add_argument('--csv', default=str(repo_root / 'killercoda-ckad_072425.csv'), help='Input CSV path')
    exp.add_argument('--json', default=str(scripts_dir / 'ckad_questions.json'), help='Output JSON path')
    exp.add_argument('--yaml', default=str(scripts_dir / 'ckad_questions.yaml'), help='Output YAML path')
    exp.set_defaults(func=ckad_export)
    imp = ckad_sub.add_parser('import', help='Import spec to regenerate CSV')
    imp.add_argument('--json', default=str(scripts_dir / 'ckad_questions.json'), help='Input JSON path')
    imp.add_argument('--yaml', default=str(scripts_dir / 'ckad_questions.yaml'), help='Input YAML path')
    imp.add_argument('--csv', default=str(repo_root / 'killercoda-ckad_072425.csv'), help='Output CSV path')
    imp.set_defaults(func=ckad_import)
    norm = ckad_sub.add_parser('normalize', help='Normalize CSV (flatten prompts, extract YAML answers)')
    norm.add_argument('--input', default=str(repo_root / 'killercoda-ckad_072425.csv'), help='Input CSV path')
    norm.add_argument('--output', default=str(repo_root / 'killercoda-ckad_normalized.csv'), help='Output CSV path')
    norm.set_defaults(func=ckad_normalize)

    # Add `full-migrate` command
    migrate_parser = subparsers.add_parser('full-migrate', help='Run full data migration and cleanup')
    migrate_parser.set_defaults(func=lambda args: task_full_migrate_and_cleanup())

    # Dynamically add other scripts as commands (from toolbox.py)
    existing_commands = set(subparsers.choices.keys())

    # Create a 'run' command to house the dynamic scripts
    run_parser = subparsers.add_parser('run', help='Run a standalone script from the scripts/ directory')
    run_subparsers = run_parser.add_subparsers(
        dest='script_name', required=True, help='Available scripts'
    )

    for p in sorted(scripts_dir.iterdir()):
        if not p.is_file() or p.name.startswith('.') or p.name == '__init__.py':
            continue

        script_stem = p.stem.replace('_', '-') # convention for cli

        # Don't add existing commands or scripts that are being replaced
        # Exclude this script itself, and any scripts that have been superseded or
        # have dedicated top-level commands.
        if p.name in (
            'kubelingo_tools.py',
            'maintenance_menu.py',
            'full_migrate_and_cleanup.py',
            'toolbox.py',
            'ckad.py',
            'generator.py',
        ):
            continue
        if script_stem in existing_commands:
            continue

        sp = run_subparsers.add_parser(script_stem, help=f'Run script {p.name}')
        # Arguments are not defined here; they are collected by parse_known_args.
        sp.set_defaults(func=run_dynamic_script, script_path=p, script_args=[])

    # Use parse_known_args to handle passthrough arguments for 'quiz' and 'run'.
    args, remainder = parser.parse_known_args(argv)

    if hasattr(args, 'quiz_args'):
        # This command is designed to consume all following args.
        args.quiz_args.extend(remainder)
    elif hasattr(args, 'script_args'):
        # This command is designed to consume all following args.
        args.script_args.extend(remainder)
    elif remainder:
        # Some other command got unexpected arguments.
        parser.error(f"unrecognized arguments: {' '.join(remainder)}")

    args.func(args)

if __name__ == '__main__':
    main()
