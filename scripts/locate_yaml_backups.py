#!/usr/bin/env python3
"""
List YAML backup files in the backups directory.
"""
import argparse
import glob
import os
import sys

def main():
    parser = argparse.ArgumentParser(description='Locate YAML backup files')
    parser.add_argument('directory', nargs='?', default='backups', help='Directory to scan for YAML backups')
    args = parser.parse_args()
    pattern = os.path.join(args.directory, '*.yaml')
    files = glob.glob(pattern)
    if not files:
        print('No YAML backups found in', args.directory)
        sys.exit(0)
    for path in sorted(files):
        size = os.path.getsize(path)
        mtime = os.path.getmtime(path)
        print(f"{path}  {size} bytes  modified={mtime}")

if __name__ == '__main__':
    main()
