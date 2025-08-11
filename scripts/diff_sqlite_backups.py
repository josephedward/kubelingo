#!/usr/bin/env python3
"""Diffs the two most recent SQLite backups."""

import subprocess
import sys
from pathlib import Path

def get_two_most_recent_backups(backup_dir: Path):
    """Finds the two most recent .db files in the backup directory."""
    if not backup_dir.is_dir():
        return None, None
    
    db_files = list(backup_dir.glob('*.db'))
    if len(db_files) < 2:
        return None, None

    sorted_files = sorted(db_files, key=lambda p: p.stat().st_mtime, reverse=True)
    return sorted_files[0], sorted_files[1]

def diff_databases(db1: Path, db2: Path):
    """Dumps two SQLite databases and prints the diff."""
    print(f"Comparing {db1.name} (newer) and {db2.name} (older)...")
    
    f_old_name, f_new_name = None, None
    try:
        import tempfile

        with tempfile.NamedTemporaryFile(mode='w', suffix=".sql", delete=False) as f_old:
            f_old_name = f_old.name
            subprocess.run(["sqlite3", str(db2), ".dump"], stdout=f_old, check=True, text=True)
            
        with tempfile.NamedTemporaryFile(mode='w', suffix=".sql", delete=False) as f_new:
            f_new_name = f_new.name
            subprocess.run(["sqlite3", str(db1), ".dump"], stdout=f_new, check=True, text=True)

        print("-" * 40)
        print(f"--- {db2.name}")
        print(f"+++ {db1.name}")
        subprocess.run(["diff", "-u", f_old_name, f_new_name], text=True)
        print("-" * 40)

    except FileNotFoundError:
        print("Error: 'sqlite3' or 'diff' command not found. Please ensure they are in your PATH.")
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        if e.stderr:
            print(e.stderr)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        # Clean up temp files
        if f_old_name:
            Path(f_old_name).unlink(missing_ok=True)
        if f_new_name:
            Path(f_new_name).unlink(missing_ok=True)

def main():
    """Finds the two most recent SQLite backups and diffs them."""
    repo_root = Path(__file__).resolve().parent.parent
    backup_dir = repo_root / 'backups' / 'sqlite'
    
    newest, second_newest = get_two_most_recent_backups(backup_dir)

    if not newest or not second_newest:
        print(f"Need at least two SQLite backup files in {backup_dir} to compare.")
        return
        
    diff_databases(newest, second_newest)

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Compares the two most recent SQLite backups.
"""
import sqlite3
import sys
from pathlib import Path
from typing import List, Optional, Tuple, Set

# Ensure the project root is in the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    from kubelingo.utils.path_utils import find_sqlite_files_from_paths
    from kubelingo.utils.config import SQLITE_BACKUP_DIRS
except ImportError as e:
    print(f"Error: A required kubelingo module is not available: {e}. "
          "Ensure you run this from the project root.", file=sys.stderr)
    sys.exit(1)


def find_most_recent_backups(files: List[Path]) -> Optional[Tuple[Path, Path]]:
    """Finds the two most recent files in a list."""
    if len(files) < 2:
        return None
    sorted_files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
    return (sorted_files[0], sorted_files[1])

def get_table_names(conn: sqlite3.Connection) -> Set[str]:
    """Gets all table names from a database."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    return {row[0] for row in cursor.fetchall()}

def get_table_row_count(conn: sqlite3.Connection, table_name: str) -> int:
    """Gets the row count of a table."""
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
    return cursor.fetchone()[0]

def main():
    """Finds and diffs the two most recent SQLite backup files."""
    backup_dirs = SQLITE_BACKUP_DIRS
    if not backup_dirs:
        print("No SQLite backup directories are configured.", file=sys.stderr)
        sys.exit(1)

    try:
        backup_files = find_sqlite_files_from_paths(backup_dirs)
    except Exception as e:
        print(f"Error scanning directories: {e}", file=sys.stderr)
        sys.exit(1)

    recent_pair = find_most_recent_backups(backup_files)

    if not recent_pair:
        print("Fewer than two SQLite backup files found. Cannot perform a diff.", file=sys.stderr)
        sys.exit(1)

    new_db_path, old_db_path = recent_pair
    print(f"Comparing newest backup: {new_db_path.name}")
    print(f"With older backup:   {old_db_path.name}\n")

    try:
        new_conn = sqlite3.connect(f"file:{new_db_path}?mode=ro", uri=True)
        old_conn = sqlite3.connect(f"file:{old_db_path}?mode=ro", uri=True)

        new_tables = get_table_names(new_conn)
        old_tables = get_table_names(old_conn)

        added_tables = new_tables - old_tables
        removed_tables = old_tables - new_tables
        common_tables = new_tables.intersection(old_tables)

        if added_tables:
            print(f"Tables added: {', '.join(added_tables)}")
        if removed_tables:
            print(f"Tables removed: {', '.join(removed_tables)}")
        
        print("\nRow count comparison for common tables:")
        for table in sorted(list(common_tables)):
            new_count = get_table_row_count(new_conn, table)
            old_count = get_table_row_count(old_conn, table)
            if new_count != old_count:
                print(f"  - {table}: {old_count} -> {new_count} (Change: {new_count - old_count:+d})")
            else:
                print(f"  - {table}: {new_count} (no change)")

        new_conn.close()
        old_conn.close()

    except sqlite3.Error as e:
        print(f"Error during database comparison: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Compares the two most recent SQLite backups and reports the differences.
"""
import sqlite3
import sys
from pathlib import Path

# Ensure the project root is in the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    from kubelingo.utils.path_utils import find_and_sort_files_by_mtime
    from kubelingo.utils.config import SQLITE_BACKUP_DIRS
except ImportError as e:
    print(f"Error: A required kubelingo module is not available: {e}. "
          "Ensure you run this from the project root.", file=sys.stderr)
    sys.exit(1)

def get_db_schema(conn: sqlite3.Connection) -> dict:
    """Extracts schema for all tables in the database."""
    cursor = conn.cursor()
    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
    return {name: sql for name, sql in cursor.fetchall()}

def get_table_row_counts(conn: sqlite3.Connection) -> dict:
    """Gets row counts for all tables."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    counts = {}
    for table in tables:
        # Using f-string is safe here since table names come from sqlite_master
        cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
        counts[table] = cursor.fetchone()[0]
    return counts

def main():
    """Compares the two most recent SQLite backups."""
    backup_dirs = SQLITE_BACKUP_DIRS
    if not backup_dirs:
        print("No SQLite backup directories are configured.", file=sys.stderr)
        sys.exit(1)

    try:
        backup_files = find_and_sort_files_by_mtime(backup_dirs, [".db", ".sqlite", ".sqlite3"])
    except Exception as e:
        print(f"Error scanning directories: {e}", file=sys.stderr)
        sys.exit(1)

    if len(backup_files) < 2:
        print("Need at least two SQLite backup files to perform a diff.", file=sys.stderr)
        sys.exit(1)
    
    db_newest, db_older = backup_files[0], backup_files[1]
    print(f"Comparing newest backup: {db_newest.name}")
    print(f"With older backup   : {db_older.name}\n")

    try:
        conn_new = sqlite3.connect(f"file:{db_newest}?mode=ro", uri=True)
        conn_old = sqlite3.connect(f"file:{db_older}?mode=ro", uri=True)

        schema_new = get_db_schema(conn_new)
        schema_old = get_db_schema(conn_old)

        # Compare schemas
        print("--- Schema Differences ---")
        all_tables = set(schema_new.keys()) | set(schema_old.keys())
        schema_diff_found = False
        for table in sorted(list(all_tables)):
            if table not in schema_old:
                print(f"+ Added table: {table}")
                schema_diff_found = True
            elif table not in schema_new:
                print(f"- Removed table: {table}")
                schema_diff_found = True
            elif schema_new[table] != schema_old[table]:
                print(f"~ Modified table schema: {table}")
                schema_diff_found = True
        if not schema_diff_found:
            print("No schema differences found.")

        # Compare row counts
        print("\n--- Row Count Differences ---")
        counts_new = get_table_row_counts(conn_new)
        counts_old = get_table_row_counts(conn_old)
        
        all_tables_for_counts = set(counts_new.keys()) | set(counts_old.keys())
        count_diff_found = False
        for table in sorted(list(all_tables_for_counts)):
            count_new = counts_new.get(table, 'N/A')
            count_old = counts_old.get(table, 'N/A')
            if count_new != count_old:
                print(f"~ {table}: {count_old} -> {count_new}")
                count_diff_found = True
        
        if not count_diff_found:
            print("No row count differences found.")

    except sqlite3.Error as e:
        print(f"Error during database comparison: {e}", file=sys.stderr)
    finally:
        if 'conn_new' in locals() and conn_new:
            conn_new.close()
        if 'conn_old' in locals() and conn_old:
            conn_old.close()

if __name__ == "__main__":
    main()
