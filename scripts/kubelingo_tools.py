#!/usr/bin/env python3
"""Kubelingo Tools: Unified script for question-data management, quiz manifest generation,
CKAD spec management, and interactive CLI quiz runner."""

import argparse
import sys
import subprocess
import shutil
import json
import re
import os
import sqlite3
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

def _get_most_recent_backup(backup_dir: Path):
    """Finds the most recent .db file in the backup directory."""
    if not backup_dir.is_dir():
        return None
    
    db_files = list(backup_dir.glob('*.db'))
    if not db_files:
        return None

    return max(db_files, key=lambda p: p.stat().st_mtime)


def _get_schema_text(db_path: Path) -> str:
    """Connects to a SQLite DB and returns its schema as CREATE statements."""
    if not db_path or not db_path.exists():
        return f"Database file not found at: {db_path}"

    try:
        # Use a file URI with mode=ro for read-only connection
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.cursor()

        # Query schema entries for tables, indexes, etc.
        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type, name"
        )
        rows = cursor.fetchall()
        conn.close()

        statements = [row[0] + ';' for row in rows if row[0]]

        if not statements:
            return f"No schema information found in {db_path}."
            
        return '\n\n'.join(statements)
    except sqlite3.Error as e:
        return f"Error reading database schema: {e}"


def _run_script(script_name: str):
    """Helper to run a script from the scripts directory."""
    script_path = scripts_dir / script_name
    if not script_path.exists():
        print(f"Error: Script '{script_path}' not found.")
        return
    command = [sys.executable, str(script_path)]
    print(f"Running: {' '.join(command)}")
    subprocess.run(command, check=False)

def task_index_yaml():
    """Index all Yaml Files in Dir"""
    _run_script("index_yaml_files.py")

def task_consolidate_yaml():
    """Consolidate Unique Yaml Questions"""
    _run_script("consolidate_unique_yaml_questions.py")

def task_show_yaml_backups():
    """Show Previous YAML backup(s)"""
    backup_dir = repo_root / 'backups' / 'yaml'
    if not backup_dir.is_dir():
        print(f"Backup directory not found: {backup_dir}")
        return

    yaml_files = sorted(
        list(backup_dir.glob('*.yaml')) + list(backup_dir.glob('*.yml')),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if not yaml_files:
        print(f"No YAML backups found in {backup_dir}")
        return

    print("\nAvailable YAML backups (newest first):")
    for f in yaml_files:
        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        print(f"  - {f.name} ({mtime})")
    print()

def task_diff_yaml_backups():
    """Diff YAML Backups"""
    _run_script("diff_yaml_backups.py")

def task_yaml_stats():
    """YAML Statistics"""
    _run_script("yaml_backup_stats.py")

def task_create_db_from_yaml():
    """Create Sqlite DB from YAML Backup Version"""
    _run_script("create_sqlite_db_from_yaml.py")

def task_index_sqlite():
    """Index Sqlite Files"""
    _run_script("index_sqlite_files.py")

def task_view_db_schema():
    """View Database Schema"""
    try:
        import questionary
    except ImportError:
        print("Error: 'questionary' library not found. Please install it with:")
        print("pip install questionary")
        sys.exit(1)

    # Need to import this late, after sys.path is adjusted
    from kubelingo.utils.path_utils import get_live_db_path

    backup_dir = repo_root / 'backups' / 'sqlite'
    most_recent_backup = _get_most_recent_backup(backup_dir)

    choices = [
        questionary.Choice("Live Database", value="live"),
    ]
    if most_recent_backup:
        choices.append(questionary.Choice(f"Most Recent Backup ({most_recent_backup.name})", value="backup"))
    
    choices.extend([
        questionary.Choice("Specific DB file path", value="path"),
        questionary.Separator(),
        questionary.Choice("Cancel", value="cancel")
    ])

    choice = questionary.select(
        "Which database schema do you want to view?",
        choices=choices,
        use_indicator=True
    ).ask()

    db_path_str = None
    if choice == "live":
        try:
            db_path_str = get_live_db_path()
            if not db_path_str:
                print("Live database path not found.", file=sys.stderr)
                return
        except Exception as e:
            print(f"Error finding live database: {e}", file=sys.stderr)
            return
    elif choice == "backup":
        db_path_str = most_recent_backup
    elif choice == "path":
        db_path_str = questionary.path("Enter the path to the SQLite database file:").ask()
    
    if not choice or choice == "cancel" or not db_path_str:
        print("Operation cancelled.")
        return

    db_path = Path(db_path_str)
    print(f"\nDisplaying schema for: {db_path}\n")
    schema_text = _get_schema_text(db_path)
    print(schema_text)

def task_show_sqlite_backups():
    """Show Previous Sqlite Backup(s)"""
    backup_dir = repo_root / 'backups' / 'sqlite'
    if not backup_dir.is_dir():
        print(f"Backup directory not found: {backup_dir}")
        return

    db_files = sorted(list(backup_dir.glob('*.db')), key=lambda p: p.stat().st_mtime, reverse=True)

    if not db_files:
        print(f"No SQLite backups found in {backup_dir}")
        return

    print("\nAvailable SQLite backups (newest first):")
    for f in db_files:
        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        print(f"  - {f.name} ({mtime})")
    print()

def task_diff_sqlite_backups():
    """Diff with Backup Sqlite Db"""
    _run_script("diff_sqlite_backups.py")

def task_create_sqlite_backup():
    """Create Sqlite Backup Version"""
    _run_script("create_sqlite_backup.py")

def task_restore_from_sqlite_backup():
    """Restore from Sqlite Backup Version"""
    _run_script("restore_sqlite_from_backup.py")

def task_deduplicate_questions():
    """Deduplicate Questions"""
    _run_script("legacy/find_duplicate_questions.py")

def task_fix_question_categorization():
    """Fix Question Categorization"""
    _run_script("reorganize_questions.py")

def task_fix_doc_links():
    """Fix Documentation Links"""
    _run_script("legacy/check_docs_links.py")

def task_fix_question_formatting():
    """Fix Question Formatting"""
    _run_script("legacy/check_quiz_formatting.py")

def task_bug_ticket():
    """Bug Ticket"""
    print("Creating a bug ticket is not yet implemented.")

def run_interactive_menu():
    """Display an interactive menu for maintenance tasks."""
    try:
        import questionary
        from questionary import Separator
    except ImportError:
        print("Error: 'questionary' library not found. Please install it with:")
        print("pip install questionary")
        sys.exit(1)

    tasks = {
        "Index all Yaml Files in Dir": task_index_yaml,
        "Consolidate Unique Yaml Questions": task_consolidate_yaml,
        "Show Previous YAML backup(s)": task_show_yaml_backups,
        "Diff YAML Backups": task_diff_yaml_backups,
        "YAML Statistics": task_yaml_stats,
        "Index Sqlite Files": task_index_sqlite,
        "Create Sqlite DB from YAML Backup Version": task_create_db_from_yaml,
        "View Database Schema": task_view_db_schema,
        "Show Previous Sqlite Backup(s)": task_show_sqlite_backups,
        "Diff with Backup Sqlite Db": task_diff_sqlite_backups,
        "Create Sqlite Backup Version": task_create_sqlite_backup,
        "Restore from Sqlite Backup Version": task_restore_from_sqlite_backup,
        "Deduplicate Questions": task_deduplicate_questions,
        "Fix Question Categorization": task_fix_question_categorization,
        "Fix Documentation Links": task_fix_doc_links,
        "Fix Question Formatting": task_fix_question_formatting,
        "Bug Ticket": task_bug_ticket,
    }

    while True:
        choice = questionary.select(
            "Select a maintenance task:",
            choices=[
                Separator("=== YAML ==="),
                "Index all Yaml Files in Dir",
                "Consolidate Unique Yaml Questions",
                "Show Previous YAML backup(s)",
                "Diff YAML Backups",
                "YAML Statistics",
                Separator("=== Sqlite ==="),
                "Index Sqlite Files",
                "Create Sqlite DB from YAML Backup Version",
                "View Database Schema",
                "Show Previous Sqlite Backup(s)",
                "Diff with Backup Sqlite Db",
                "Create Sqlite Backup Version",
                "Restore from Sqlite Backup Version",
                Separator("=== Questions ==="),
                "Deduplicate Questions",
                "Fix Question Categorization",
                "Fix Documentation Links",
                "Fix Question Formatting",
                Separator("=== System ==="),
                "Bug Ticket",
                "Cancel"
            ],
            use_indicator=True
        ).ask()

        if choice is None or choice == "Cancel":
            print("Operation cancelled.")
            break

        if choice in tasks:
            tasks[choice]()

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
    script = scripts_dir / 'generate_kubectl_operations_quiz.py'
    subprocess.run([sys.executable, str(script)], check=True)

def generate_reference(args):
    """Generate the Resource Reference quiz manifest (delegates to existing script)."""
    script = scripts_dir / 'generate_resource_reference_quiz.py'
    subprocess.run([sys.executable, str(script)], check=True)

def generate_manifests(args):
    """Generate quiz manifests and solutions from JSON quiz data (delegates to existing script)."""
    script = scripts_dir / 'generate_manifests.py'
    subprocess.run([sys.executable, str(script)], check=True)

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

def main():
    if len(sys.argv) == 1:
        run_interactive_menu()
        return

    parser = argparse.ArgumentParser(description='Kubelingo umbrella tools')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # quiz
    quiz_parser = subparsers.add_parser('quiz', help='Run the interactive CLI quiz')
    quiz_parser.add_argument('quiz_args', nargs=argparse.REMAINDER, help='Arguments forwarded to kubelingo CLI')
    quiz_parser.set_defaults(func=run_quiz)

    # manage
    manage_parser = subparsers.add_parser('manage', help='Manage question-data')
    manage_sub = manage_parser.add_subparsers(dest='subcommand', required=True)
    org_p = manage_sub.add_parser('organize', help='Archive and rename question-data files')
    org_p.add_argument('--dry-run', action='store_true', help='Preview changes without writing files')
    org_p.set_defaults(func=manage_organize)

    # generate
    gen_parser = subparsers.add_parser('generate', help='Generate quiz manifests')
    gen_sub = gen_parser.add_subparsers(dest='subcommand', required=True)
    gen_ops = gen_sub.add_parser('operations', help='Generate Kubectl operations quiz')
    gen_ops.set_defaults(func=generate_operations)
    gen_ref = gen_sub.add_parser('reference', help='Generate Resource Reference quiz')
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

    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()
