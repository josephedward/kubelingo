import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
ARCHIVE_DIR = PROJECT_ROOT / "archive"
SQLITE_EXTENSIONS = [".db", ".sqlite3"]
DEST_DIR = PROJECT_ROOT / ".kubelingo" / "backups"


def unarchive_sqlite_files():
    """
    Moves SQLite database files from the archive directory to .kubelingo/backups.
    """
    if not ARCHIVE_DIR.is_dir():
        print(f"Error: Archive directory not found at '{ARCHIVE_DIR}'")
        return

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Moving SQLite files to: {DEST_DIR.relative_to(PROJECT_ROOT)}")

    found_files = []
    for ext in SQLITE_EXTENSIONS:
        found_files.extend(ARCHIVE_DIR.glob(f"*{ext}"))

    if not found_files:
        print("No SQLite files found in archive directory.")
        return

    for file_path in found_files:
        dest_path = DEST_DIR / file_path.name
        try:
            print(f"Moving {file_path.relative_to(PROJECT_ROOT)} to {dest_path.relative_to(PROJECT_ROOT)}")
            shutil.move(file_path, dest_path)
        except Exception as e:
            print(f"Error moving {file_path}: {e}")


if __name__ == "__main__":
    unarchive_sqlite_files()
