import os
from pathlib import Path

def main():
    """
    Scans the question-data-backup/ directory for any YAML files (.yaml or .yml)
    and reports their presence or absence.
    """
    backup_dir = Path("question-data-backup")
    
    if not backup_dir.is_dir():
        print(f"Backup directory not found: {backup_dir}")
        return

    yaml_files = list(backup_dir.glob('*.yaml')) + list(backup_dir.glob('*.yml'))

    if yaml_files:
        print("Found YAML backup files:")
        for f in yaml_files:
            print(f" - {f}")
    else:
        print("No YAML backup files found in question-data-backup/.")

if __name__ == "__main__":
    main()
