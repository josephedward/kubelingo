#!/usr/bin/env python3
"""
Locate YAML backup files in the specified directory.
"""
import os
import time
import re
import json
import argparse
from pathlib import Path
try:
    from kubelingo.utils.config import get_api_key
except ImportError:
    get_api_key = None

def main():
    """
    Lists available YAML backup files with size and timestamp.
    """
    parser = argparse.ArgumentParser(
        description="Locate YAML backup files with optional filtering and summary."
    )
    parser.add_argument(
        'backup_dir', nargs='?', default='question-data-backup',
        help='Primary directory to scan for YAML backups (default: question-data-backup)'
    )
    parser.add_argument(
        '-d', '--dir', action='append', default=[],
        help='Additional directory to scan for YAML backups'
    )
    parser.add_argument(
        '-p', '--pattern', help='Regex pattern to filter filenames'
    )
    parser.add_argument(
        '--json', action='store_true', help='Output results in JSON format'
    )
    parser.add_argument(
        '--ai', action='store_true', help='Use AI to generate a natural-language summary'
    )
    args = parser.parse_args()
    # collect YAML files from primary and additional directories
    search_dirs = [Path(args.backup_dir)] + [Path(d) for d in args.dir]
    files = []
    for target_dir in search_dirs:
        if not target_dir.is_dir():
            print(f"Skipping non-directory: {target_dir}")
            continue
        for f in sorted(target_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in ('.yaml', '.yml'):
                if args.pattern and not re.search(args.pattern, f.name):
                    continue
                files.append(f)

    if not files:
        dirs_str = ', '.join(str(d) for d in search_dirs)
        print(f"No YAML backup files found in: {dirs_str}")
        return
    entries = []
    for f in files:
        try:
            stat = f.stat()
            mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime))
            entries.append({'file': str(f), 'size': stat.st_size, 'mtime': mtime})
        except OSError as e:
            entries.append({'file': str(f), 'error': str(e)})

    if args.json:
        print(json.dumps(entries, indent=2))
    else:
        dirs_str = ', '.join(str(d) for d in search_dirs)
        print(f"Found {len(entries)} YAML backup file(s) in {dirs_str}:\n")
        for e in entries:
            if 'error' in e:
                print(f"{e['file']}\t<error: {e['error']}>")
            else:
                print(f"{e['file']}\t{e['size']} bytes\t{e['mtime']}")

    if args.ai:
        try:
            import openai
            api_key = os.getenv('OPENAI_API_KEY') or (get_api_key() if get_api_key else None)
            if not api_key:
                print('No OpenAI API key found; skipping AI summary')
            else:
                openai.api_key = api_key
                prompt = 'Here are YAML backup files: ' + json.dumps(entries) + \
                         '\nProvide a concise summary of these backups and any notable observations.'
                resp = openai.ChatCompletion.create(
                    model='gpt-3.5-turbo',
                    messages=[{'role': 'user', 'content': prompt}]
                )
                print('\nAI Summary:\n' + resp.choices[0].message.content)
        except ImportError:
            print('OpenAI library not installed; install openai to enable AI summary')
        except Exception as e:
            print(f'Failed to generate AI summary: {e}')

if __name__ == '__main__':
    main()
