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
        Choice('Write DB to YAML Backup Version', value='qm_export_yaml'),
        Choice('Restore DB from YAML Backup Version', value='restore_yaml_to_db.py'),
        Choice('Create Sqlite DB from YAML Backup Version', value='create_sqlite_db_from_yaml.py'),
        Separator('=== SQLite ==='),
        Choice('Index all SQLite Files in Dir', value='sqlite_index'),
        Choice('View Database Schema', value='sqlite_schema'),
        Choice('Locate Previous SQLite Backup', value='sqlite_list'),
        Choice('Diff with Backup SQLite DB', value='sqlite_diff'),
        Choice('Unarchive and Prune SQLite Backups', value='sqlite_unarchive'),
        Choice('Restore from SQLite Backup Version', value='sqlite_restore'),
        Choice('Create DB from YAML', value='sqlite_create_from_yaml'),
        Choice('Create DB from YAML with AI Categorization', value='import_yaml_ai'),
        Separator('=== Questions ==='),
        Choice('Deduplicate Questions', value='qm_deduplicate'),
        Choice('Fix Question Categorization', value='qm_categorize'),
        Choice('Fix Documentation Links', value='qm_fix_links'),
        Choice('Fix Question Formatting', value='qm_format'),
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
    elif answer == 'qm_export_yaml':
        run_script('question_manager.py', 'export-to-yaml')
    elif answer == 'restore_yaml_to_db.py':
        backups = get_all_yaml_backups()
        choice = questionary.select('Select YAML backup to restore:', [str(p) for p in backups]).ask()
        if choice:
            run_script('restore_yaml_to_db.py', choice, '--clear')
    elif answer == 'sqlite_create_from_yaml':
        run_script('sqlite_manager.py', 'create-from-yaml', '--clear')
    elif answer == 'sqlite_index':
        run_script('sqlite_manager.py', 'index')
    elif answer == 'sqlite_schema':
        db_path = questionary.path("Enter path to DB file (or press Enter for default):").ask()
        if db_path:
             run_script('sqlite_manager.py', 'schema', db_path)
        else:
             run_script('sqlite_manager.py', 'schema')
    elif answer == 'sqlite_list':
        run_script('sqlite_manager.py', 'list')
    elif answer == 'sqlite_diff':
        run_script('sqlite_manager.py', 'diff')
    elif answer == 'create_sqlite_backup.py':
        run_script('create_sqlite_backup.py')
    elif answer == 'sqlite_unarchive':
        run_script('sqlite_manager.py', 'unarchive')
    elif answer == 'sqlite_restore':
        run_script('sqlite_manager.py', 'restore')
    elif answer == 'import_yaml_ai':
        db_path = questionary.text(
            'Enter the path for the new AI-categorized SQLite database file:',
            default='.kubelingo/kubelingo-ai.db'
        ).ask()
        if db_path:
            run_script('import_from_yaml_with_ai.py', db_path)
    elif answer == 'qm_deduplicate':
        run_script('question_manager.py', 'deduplicate')
    elif answer == 'qm_categorize':
        run_script('question_manager.py', 'categorize')
    elif answer == 'qm_fix_links':
        run_script('question_manager.py', 'fix-links')
    elif answer == 'qm_format':
        run_script('question_manager.py', 'format')
    else:
        print(f'Unknown task: {answer}')
        sys.exit(1)

if __name__ == '__main__':
    main()
