#!/usr/bin/env python3
"""
Kubelingo Toolbox: run all standalone scripts in the scripts directory.
"""
import argparse
import subprocess
import sys
from pathlib import Path

def main():
    scripts_dir = Path(__file__).resolve().parent
    commands = {}
    for p in scripts_dir.iterdir():
        if not p.is_file():
            continue
        if p.name in ('toolbox.py', 'kubelingo_tools.py', '__init__.py'):
            continue
        commands[p.stem] = p

    parser = argparse.ArgumentParser(
        prog='toolbox.py',
        description='Kubelingo toolbox for standalone scripts'
    )
    subparsers = parser.add_subparsers(
        dest='command', required=True, help='Available scripts'
    )
    for name, path in sorted(commands.items()):
        sp = subparsers.add_parser(name, help=f'Run script {path.name}')
        sp.add_argument(
            'script_args', nargs=argparse.REMAINDER,
            help='Arguments forwarded to the script'
        )
        sp.set_defaults(script_path=path)

    args = parser.parse_args()
    script_path = args.script_path
    if script_path.suffix == '.sh':
        cmd = ['bash', str(script_path)] + args.script_args
    else:
        cmd = [sys.executable, str(script_path)] + args.script_args
    try:
        result = subprocess.run(cmd)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        sys.exit(1)

if __name__ == '__main__':
    main()