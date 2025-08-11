#!/usr/bin/env python3
"""
Interactive maintenance menu for Kubelingo scripts and utilities.
"""
import sys
import subprocess
from pathlib import Path

try:
    import questionary
    from questionary import Choice, Separator
except ImportError:
    print("Error: 'questionary' package is required for interactive maintenance menu.")
    print("Install with: pip install questionary")
    sys.exit(1)

from kubelingo.utils.path_utils import (
    get_all_yaml_files,
    get_all_yaml_backups,
    get_all_sqlite_backups,
)

# Script directory
SCRIPT_DIR = Path(__file__).resolve().parent

def run_script(script_name, *args):
    """Run a maintenance script by name with optional args."""
    script_path = SCRIPT_DIR / script_name
    cmd = [sys.executable, str(script_path)] + list(args)
    subprocess.run(cmd)

def list_items(items):
    """Print a list of items and wait for user to continue."""
    for item in items:
        print(item)
    input("\nPress Enter to continue...")

def main():
    # Define menu choices
    choices = [
        Separator('=== System ==='),
        Choice('Bug Ticket', value='bug_ticket.py'),
        Separator('=== YAML ==='),
        Choice('Index all YAML Files in Dir', value='index_yaml'),
        Choice('Locate Previous YAML Backup', value='locate_yaml_backups.py'),
        Choice('View YAML Backup Statistics', value='view_yaml_stats.py'),
        Choice('Write DB to YAML Backup Version', value='export_db_to_yaml.py'),
        Choice('Restore DB from YAML Backup Version', value='restore_yaml_to_db.py'),
        Separator('=== SQLite ==='),
        Choice('Index all SQLite Files in Dir', value='index_sqlite'),
        Choice('View Database Schema', value='view_sqlite_schema.py'),
        Choice('Locate Previous SQLite Backup', value='locate_sqlite_backups.py'),
        Choice('Diff with Backup SQLite DB', value='diff_sqlite.py'),
        Choice('Create SQLite Backup Version', value='create_sqlite_backup.py'),
        Choice('Restore from SQLite Backup Version', value='restore_sqlite.py'),
        Choice('Create DB from YAML with AI Categorization', value='import_yaml_ai'),
        Separator('=== Questions ==='),
        Choice('Deduplicate Questions', value='deduplicate_questions.py'),
        Choice('Fix Question Categorization', value='categorize_questions.py'),
        Choice('Fix Documentation Links', value='fix_links.py'),
        Choice('Fix Question Formatting', value='format_questions.py'),
        Separator(),
        Choice('Cancel', value=None),
    ]
    answer = questionary.select(
        'Select a maintenance task:',
        choices=choices
    ).ask()
    if not answer:
        sys.exit(0)

    # Dispatch based on selection value
    if answer == 'bug_ticket.py':
        run_script('bug_ticket.py')
    elif answer == 'index_yaml':
        files = get_all_yaml_files()
        list_items(files)
    elif answer == 'locate_yaml_backups.py':
        run_script('locate_yaml_backups.py')
    elif answer == 'view_yaml_stats.py':
        run_script('view_yaml_stats.py')
    elif answer == 'export_db_to_yaml.py':
        run_script('export_db_to_yaml.py')
    elif answer == 'restore_yaml_to_db.py':
        backups = get_all_yaml_backups()
        choice = questionary.select('Select YAML backup to restore:', [str(p) for p in backups]).ask()
        if choice:
            run_script('restore_yaml_to_db.py', choice, '--clear')
    elif answer == 'index_sqlite':
        files = get_all_sqlite_backups()
        list_items(files)
    elif answer == 'view_sqlite_schema.py':
        run_script('view_sqlite_schema.py')
    elif answer == 'locate_sqlite_backups.py':
        run_script('locate_sqlite_backups.py')
    elif answer == 'diff_sqlite.py':
        backups = get_all_sqlite_backups()
        if len(backups) < 2:
            print('Need at least two backup databases to diff.')
        else:
            choices = [str(p) for p in backups]
            old = questionary.select('Select old DB:', choices).ask()
            new = questionary.select('Select new DB:', choices).ask()
            if old and new:
                run_script('diff_sqlite.py', old, new)
    elif answer == 'create_sqlite_backup.py':
        run_script('create_sqlite_backup.py')
    elif answer == 'restore_sqlite.py':
        backups = get_all_sqlite_backups()
        choice = questionary.select('Select SQLite backup to restore:', [str(p) for p in backups]).ask()
        if choice:
            run_script('restore_sqlite.py', choice)
    elif answer == 'import_yaml_ai':
        db_path = questionary.text(
            'Enter the path for the new AI-categorized SQLite database file:',
            default='.kubelingo/kubelingo-ai.db'
        ).ask()
        if db_path:
            run_script('import_from_yaml_with_ai.py', db_path)
    elif answer == 'deduplicate_questions.py':
        run_script('deduplicate_questions.py')
    elif answer == 'categorize_questions.py':
        run_script('categorize_questions.py')
    elif answer == 'fix_links.py':
        run_script('fix_links.py')
    elif answer == 'format_questions.py':
        run_script('format_questions.py')
    else:
        print(f'Unknown task: {answer}')
        sys.exit(1)

if __name__ == '__main__':
    main()
