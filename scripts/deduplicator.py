import hashlib
import sys
from collections import defaultdict
from pathlib import Path


def sha256_checksum(file_path: Path, block_size=65536) -> str:
    """Calculates the SHA256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(block_size), b""):
            sha256.update(block)
    return sha256.hexdigest()


def find_duplicates(file_paths: list[str]) -> dict[str, list[Path]]:
    """Finds duplicate files from a list of path strings based on their content."""
    checksums = defaultdict(list)
    for file_path_str in file_paths:
        file_path = Path(file_path_str)
        if file_path.is_file():
            try:
                checksum = sha256_checksum(file_path)
                checksums[checksum].append(file_path)
            except IOError as e:
                print(f"Warning: Could not read file {file_path_str}: {e}", file=sys.stderr)

    return {k: v for k, v in checksums.items() if len(v) > 1}


def main():
    """
    Finds and reports duplicate files from a list of command-line arguments.
    Example: python scripts/deduplicator.py questions/ai_generated/*
    """
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <file1> <file2> ...", file=sys.stderr)
        sys.exit(1)

    file_paths = sys.argv[1:]
    duplicates = find_duplicates(file_paths)

    if not duplicates:
        print("No duplicate files found.", file=sys.stderr)
        return

    print("# Found duplicate files. Run the following commands to remove them:")
    print("# This will remove the files from your git tracking and the filesystem.")

    total_removed = 0
    for checksum, paths in duplicates.items():
        # Sort by path to have a deterministic file to keep.
        paths.sort()
        # Keep the first file, mark the rest for deletion.
        paths_to_delete = paths[1:]

        print(f"\n# Duplicates with checksum {checksum} (keeping '{paths[0]}')")
        for p in paths_to_delete:
            print(f"git rm '{p}'")
            total_removed += 1

    print(f"\n# Total files to be removed: {total_removed}", file=sys.stderr)


if __name__ == "__main__":
    main()
