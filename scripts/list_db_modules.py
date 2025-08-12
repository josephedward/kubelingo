#!/usr/bin/env python3
"""
List all quiz modules currently stored in the Kubelingo SQLite DB.
"""
import os
import sys

# Add project root to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))
sys.path.insert(0, PROJECT_ROOT)

from kubelingo.modules.db_loader import DBLoader

def main():
    loader = DBLoader()
    modules = loader.discover()
    if not modules:
        print("No quiz modules found in the DB.")
        return
    print("Available DB quiz modules (module_name: question count):")
    for sf in modules:
        name, _ = os.path.splitext(sf)
        # Count questions in each module
        try:
            qs = loader.load_file(sf)
            count = len(qs)
        except Exception:
            count = 'error'
        print(f" - {name}: {count}")

if __name__ == '__main__':
    main()