import hashlib
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
ARCHIVE_DIR = PROJECT_ROOT / "archive"
SQLITE_EXTENSIONS = [".db", ".sqlite3"]
DEST_DIR = PROJECT_ROOT / ".kubelingo"
MAX_DBS_TO_KEEP = 10


def find_and_sort_files_by_mtime(search_dirs, extensions):
    """
    Scans directories for files with given extensions, sorts them by modification time (newest first).
    """
    all_files = set()
    for dir_path_str in search_dirs:
        dir_path = Path(dir_path_str)
        if dir_path.is_dir():
            for ext in extensions:
                # Ensure extension starts with a dot
                glob_pattern = f"**/*{ext}" if ext.startswith('.') else f"**/*.{ext}"
                all_files.update(dir_path.glob(glob_pattern))

    if not all_files:
        return []

    # Sort files by modification time, newest first
    return sorted(list(all_files), key=lambda p: p.stat().st_mtime, reverse=True)


def sha256_checksum(file_path: Path, block_size=65536) -> str:
    """Calculates the SHA256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(block_size), b""):
            sha256.update(block)
    return sha256.hexdigest()


def prune_old_databases():
    """
    Finds all SQLite database files across backup locations and removes the
    oldest ones, keeping only the most recent specified number of databases.
    """
    print("\nPruning old SQLite databases...")
    scan_dirs = [str(DEST_DIR), str(ARCHIVE_DIR)]
    all_db_files = find_and_sort_files_by_mtime(scan_dirs, SQLITE_EXTENSIONS)

    if len(all_db_files) <= MAX_DBS_TO_KEEP:
        print(
            f"Found {len(all_db_files)} database(s), which is within the limit of {MAX_DBS_TO_KEEP}. No pruning needed."
        )
        return

    files_to_delete = all_db_files[MAX_DBS_TO_KEEP:]
    print(f"Found {len(all_db_files)} databases. Deleting {len(files_to_delete)} oldest files to keep {MAX_DBS_TO_KEEP} newest.")

    for file_path in files_to_delete:
        try:
            print(f"  - Deleting old database: {file_path.relative_to(PROJECT_ROOT)}")
            file_path.unlink()
        except OSError as e:
            print(f"    Error deleting file {file_path}: {e}")
        except ValueError:
            print(f"  - Deleting old database: {file_path}")
            file_path.unlink()


def unarchive_sqlite_files():
    """
    Moves SQLite database files from the archive directory to .kubelingo.
    Identical files that already exist in the destination are deleted from the archive.
    After moving, it prunes old database files across all backup locations.
    """
    if not ARCHIVE_DIR.is_dir():
        print(f"Error: Archive directory not found at '{ARCHIVE_DIR}'")
        return

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Moving SQLite files to: {DEST_DIR.relative_to(PROJECT_ROOT)}")

    # Pre-calculate hashes of existing files in the destination to detect duplicates.
    existing_hashes = {
        sha256_checksum(p) for p in DEST_DIR.iterdir() if p.is_file()
    }

    found_files = []
    for ext in SQLITE_EXTENSIONS:
        found_files.extend(ARCHIVE_DIR.glob(f"*{ext}"))

    if not found_files:
        print("No SQLite files found in archive directory.")
        return

    for file_path in found_files:
        dest_path = DEST_DIR / file_path.name
        try:
            file_hash = sha256_checksum(file_path)
            if file_hash in existing_hashes:
                print(
                    f"Removing duplicate from archive: {file_path.relative_to(PROJECT_ROOT)} "
                    f"is identical to a file in {DEST_DIR.relative_to(PROJECT_ROOT)}."
                )
                file_path.unlink()
                continue

            print(f"Moving {file_path.relative_to(PROJECT_ROOT)} to {dest_path.relative_to(PROJECT_ROOT)}")
            shutil.move(file_path, dest_path)
            existing_hashes.add(file_hash)
        except Exception as e:
            print(f"Error moving {file_path}: {e}")

    # After moving files, prune the collection of databases
    prune_old_databases()


if __name__ == "__main__":
    unarchive_sqlite_files()
