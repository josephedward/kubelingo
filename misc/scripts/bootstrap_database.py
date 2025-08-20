#!/usr/bin/env python3
"""
Bootstraps the Kubelingo database from the single source YAML file.

This script creates a new, timestamped SQLite database in the .kubelingo
directory and populates it with question metadata from the canonical YAML source.
The application will automatically use the most recently created database.
"""
import os
import sys

# Add project root to sys.path to allow imports from kubelingo package
if __name__ == '__main__':
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)

from kubelingo.database import build_from_yaml
from kubelingo.utils.config import SINGLE_SOURCE_YAML_FILE

def main():
    """Main function to run the database bootstrap process."""
    print("--- Kubelingo Database Bootstrap ---")
    print(f"Using source YAML: {SINGLE_SOURCE_YAML_FILE}")
    print("This will create a new, timestamped database with all questions.")
    print("-" * 34)

    try:
        build_from_yaml(SINGLE_SOURCE_YAML_FILE, verbose=True)
        print("\nBootstrap complete. The application will now use the new database.")
    except Exception as e:
        print(f"\nAn error occurred during bootstrap: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
