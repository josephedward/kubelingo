import hashlib
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
ARCHIVE_DIR = PROJECT_ROOT / "archive"
SQLITE_EXTENSIONS = [".db", ".sqlite3"]
DEST_DIR = PROJECT_ROOT / ".kubelingo"


def sha256_checksum(file_path: Path, block_size=65536) -> str:
    """Calculates the SHA256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(block_size), b""):
            sha256.update(block)
    return sha256.hexdigest()


def unarchive_sqlite_files():
    """
    Moves SQLite database files from the archive directory to .kubelingo.
    Identical files that already exist in the destination are deleted from the archive.
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


if __name__ == "__main__":
    unarchive_sqlite_files()
