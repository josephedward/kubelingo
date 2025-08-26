#!/usr/bin/env python3
"""
Script to convert single-quoted YAML manifest solutions in question files
to block literal format with proper indentation.
"""
import os
import re
import sys

def convert_text(text):
    # Match single-quoted multi-line manifest solutions
    # Pattern: indent, - 'apiVersion... until closing quote
    pattern = re.compile(
        r"(?P<indent>^[ ]*)- '(?P<content>[\s\S]*?)'", re.MULTILINE
    )
    def repl(m):
        indent = m.group('indent')
        content = m.group('content')
        # Split into lines and remove leading/trailing whitespace
        lines = content.splitlines()
        trimmed = [line.strip() for line in lines if line.strip()]
        # Build block literal
        block = f"{indent}- |-\n"
        for line in trimmed:
            block += f"{indent}  {line}\n"
        return block.rstrip("\n")
    return re.sub(pattern, repl, text)

def process_file(path):
    try:
        text = open(path, 'r', encoding='utf-8').read()
    except Exception:
        return
    new_text = convert_text(text)
    if new_text != text:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_text)
        print(f"Updated: {path}")

def main():
    # Directories to scan (default 'questions')
    targets = sys.argv[1:] or ['questions']
    for target in targets:
        for root, _, files in os.walk(target):
            for fname in files:
                if fname.endswith(('.yaml', '.yml')):
                    process_file(os.path.join(root, fname))

if __name__ == '__main__':
    main()