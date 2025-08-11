#!/usr/bin/env python3
"""
Index all YAML question files in the configured question directories.
"""
#!/usr/bin/env python3
"""
Index all YAML question files in configured question directories.
"""
import sys
from pathlib import Path
from kubelingo.utils.path_utils import get_all_question_dirs, find_yaml_files

def main():
    dirs = get_all_question_dirs()
    print("Configured question directories:")
    for d in dirs:
        print(f" - {d}")
    print()

    files = find_yaml_files()
    if not files:
        print("No YAML question files found in any configured directories.")
        sys.exit(0)
    print("YAML question files:")
    for f in sorted(files):
        print(f)

if __name__ == '__main__':
    main()