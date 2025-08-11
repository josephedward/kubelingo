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
    main()#!/usr/bin/env python3
"""
Finds and lists all YAML files within the project repository.
"""
import sys
from pathlib import Path

# Ensure the project root is on the python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kubelingo.utils.path_utils import get_all_yaml_files_in_repo
from kubelingo.utils.ui import Fore, Style


def main():
    """Prints a list of all YAML files in the repository."""
    print(f"{Fore.CYAN}--- All YAML Files in Repository ---{Style.RESET_ALL}")
    try:
        yaml_files = get_all_yaml_files_in_repo()
        if not yaml_files:
            print(f"{Fore.YELLOW}No YAML files found.{Style.RESET_ALL}")
            return

        for f in yaml_files:
            print(str(f))

        print(f"\n{Fore.GREEN}Found {len(yaml_files)} file(s).{Style.RESET_ALL}")

    except Exception as e:
        print(f"{Fore.RED}An error occurred: {e}{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
