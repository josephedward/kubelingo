#!/usr/bin/env python3
"""
Locate Previous YAML backup files in the question-data-backup directory.
"""
import os
import time
import argparse
from kubelingo.utils.config import PROJECT_ROOT

def main():
    parser = argparse.ArgumentParser(
        description="List available YAML backup files with size and timestamp."
    )
    parser.parse_args()
    backup_dir = os.path.join(PROJECT_ROOT, 'question-data-backup')
    if not os.path.isdir(backup_dir):
        print(f"No YAML backup directory found at {backup_dir}")
        return
    files = [f for f in os.listdir(backup_dir) if f.lower().endswith('.yaml')]
    if not files:
        print(f"No YAML backup files in {backup_dir}")
        return
    files.sort()
    print(f"Found {len(files)} YAML backup file(s) in {backup_dir}:\n")
    for fname in files:
        path = os.path.join(backup_dir, fname)
        try:
            size = os.path.getsize(path)
            mtime = time.localtime(os.path.getmtime(path))
            ts = time.strftime('%Y-%m-%d %H:%M:%S', mtime)
            print(f"{fname}\t{size} bytes\t{ts}")
        except OSError as e:
            print(f"{fname}\t<error: {e}>")

if __name__ == '__main__':
    main()