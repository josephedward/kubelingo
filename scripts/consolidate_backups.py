import os
import shutil
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
EXTENSIONS = [".db", ".sqlite3", ".yaml"]
ARCHIVE_DIR = PROJECT_ROOT / "archive"
# Directories to exclude from search. We resolve them to handle symlinks etc.
EXCLUDE_DIRS = [
    ARCHIVE_DIR.resolve(),
    (PROJECT_ROOT / ".git").resolve(),
    (PROJECT_ROOT / ".idea").resolve(),
    (PROJECT_ROOT / ".vscode").resolve(),
    (PROJECT_ROOT / "venv").resolve(),
    (PROJECT_ROOT / ".venv").resolve(),
    (PROJECT_ROOT / "__pycache__").resolve(),
]


def consolidate_backups():
    """
    Consolidates data files from the project into a single archive directory.
    Files are renamed using their creation timestamp to avoid name conflicts and
    provide a clear history.
    """
    ARCHIVE_DIR.mkdir(exist_ok=True)
    print(f"Archive directory: {ARCHIVE_DIR}")

    found_files = []
    for ext in EXTENSIONS:
        for file_path in PROJECT_ROOT.rglob(f"*{ext}"):
            resolved_path = file_path.resolve()

            # Skip the script file itself.
            if resolved_path == Path(__file__).resolve():
                continue

            # Check if the file is within an excluded directory.
            in_excluded = False
            for excluded_dir in EXCLUDE_DIRS:
                if not excluded_dir.is_dir():
                    continue
                try:
                    # This will throw ValueError if it's not a subpath.
                    resolved_path.relative_to(excluded_dir)
                    in_excluded = True
                    break
                except ValueError:
                    continue  # Not in this excluded dir.
            if in_excluded:
                continue

            found_files.append(file_path)

    for file_path in sorted(list(set(found_files))):
        try:
            # Use birthtime for creation time if available (macOS, some Linux),
            # otherwise fall back to modification time.
            try:
                stat_result = os.stat(file_path)
                creation_time = getattr(stat_result, "st_birthtime", stat_result.st_mtime)
            except AttributeError:
                creation_time = file_path.stat().st_mtime

            dt_object = datetime.fromtimestamp(creation_time)
            new_name = f"{dt_object.strftime('%Y%m%d_%H%M%S_%f')}{file_path.suffix}"
            new_path = ARCHIVE_DIR / new_name

            # Handle potential filename collisions (highly unlikely but robust).
            counter = 1
            while new_path.exists():
                new_name = f"{dt_object.strftime('%Y%m%d_%H%M%S_%f')}_{counter}{file_path.suffix}"
                new_path = ARCHIVE_DIR / new_name
                counter += 1

            print(f"Moving {file_path.relative_to(PROJECT_ROOT)} to {new_path.relative_to(PROJECT_ROOT)}")
            shutil.move(file_path, new_path)

        except Exception as e:
            print(f"Error processing {file_path}: {e}")


if __name__ == "__main__":
    consolidate_backups()
