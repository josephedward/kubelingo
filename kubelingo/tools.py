import sqlite3
import sys
from pathlib import Path
import datetime

try:
    import questionary
    from questionary import Choice, Separator
except ImportError:
    questionary = None

from kubelingo.database import get_db_connection
from kubelingo.utils.path_utils import get_live_db_path, find_sqlite_files
from kubelingo.utils.config import SQLITE_BACKUP_DIRS
from kubelingo.utils.ui import Fore, Style

def _print_schema(db_path: Path):
    """Connects to a SQLite DB and prints its schema."""
    if not db_path or not db_path.exists():
        print(f"{Fore.RED}Database file not found: {db_path}{Style.RESET_ALL}")
        return

    print(f"\n{Fore.CYAN}Schema for {db_path}:{Style.RESET_ALL}\n")
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        if not tables:
            print(f"{Fore.YELLOW}No tables found in the database.{Style.RESET_ALL}")
        else:
            for table_name, schema in tables:
                print(f"-- Schema for table: {table_name}")
                print(f"{schema};\n")

        conn.close()
    except sqlite3.Error as e:
        print(f"{Fore.RED}Error reading database schema: {e}{Style.RESET_ALL}")

def view_database_schema():
    """Interactively select a database and view its schema."""
    if not questionary:
        print("`questionary` is needed for this feature.")
        return

    live_db_path_str = get_live_db_path()
    live_db_path = Path(live_db_path_str) if live_db_path_str else None

    backup_files = find_sqlite_files(SQLITE_BACKUP_DIRS)
    sorted_backups = sorted(backup_files, key=lambda p: p.stat().st_mtime, reverse=True)

    choices = []
    if live_db_path and live_db_path.exists():
        choices.append(Choice(f"Live Database ({live_db_path.name})", value=live_db_path))

    if sorted_backups:
        choices.append(Choice(f"Most Recent Backup ({sorted_backups[0].name})", value=sorted_backups[0]))
        choices.append(Separator("--- All Backups ---"))
        for backup in sorted_backups:
            # Using relative path for cleaner display if possible
            try:
                display_name = backup.relative_to(Path.cwd())
            except ValueError:
                display_name = backup
            choices.append(Choice(str(display_name), value=backup))

    if not choices:
        print(f"{Fore.YELLOW}No databases found (live or backups).{Style.RESET_ALL}")
        return

    choices.append(Separator())
    choices.append(Choice("Cancel", value="cancel"))

    try:
        selected_path = questionary.select(
            "Which database schema would you like to view?",
            choices=choices
        ).ask()

        if selected_path and selected_path != "cancel":
            _print_schema(selected_path)
    except (KeyboardInterrupt, EOFError):
        print(f"\n{Fore.YELLOW}Operation cancelled.{Style.RESET_ALL}")
        return

def list_database_backups():
    """Lists all SQLite backup files."""
    backup_files = find_sqlite_files(SQLITE_BACKUP_DIRS)
    if not backup_files:
        print(f"{Fore.YELLOW}No SQLite backup files found.{Style.RESET_ALL}")
        return

    sorted_files = sorted(backup_files, key=lambda p: p.stat().st_mtime, reverse=True)

    print(f"\n{Fore.CYAN}Found {len(sorted_files)} backup file(s), sorted by most recent:{Style.RESET_ALL}\n")
    for f in sorted_files:
        mod_time = f.stat().st_mtime
        mod_time_str = datetime.datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
        print(f"  - {f} (Last modified: {mod_time_str})")

def show_db_tools_menu():
    """Shows an interactive menu for database tools."""
    if not questionary:
        print("`questionary` is needed for this feature.")
        return

    try:
        while True:
            action = questionary.select(
                "Select a database tool:",
                choices=[
                    Choice("View database schema", "schema"),
                    Choice("List database backups", "list"),
                    Separator(),
                    Choice("Back to main tools menu", "back")
                ]
            ).ask()

            if action == "schema":
                view_database_schema()
            elif action == "list":
                list_database_backups()
            elif action == "back" or action is None:
                break
    except (KeyboardInterrupt, EOFError):
        print(f"\n{Fore.YELLOW}Operation cancelled.{Style.RESET_ALL}")
