#!/usr/bin/env python3
"""
Script to check links in docs/ directory for HTTP errors.
"""
import sys
import requests
import re
from pathlib import Path

# Directory containing documentation files
DOCS_DIR = Path(__file__).resolve().parent.parent / 'docs'

# Regex for extracting URLs
URL_REGEX = re.compile(r'https?://[^\s\)"\']+')

def extract_links(text):
    return set(URL_REGEX.findall(text))

def main():
    errors = []
    session = requests.Session()
    session.headers.update({'User-Agent': 'kubelingo-doc-link-checker/1.0'})
    for file_path in sorted(DOCS_DIR.rglob('*.md')):
        if file_path.name.startswith('.'):
            continue
        text = file_path.read_text(encoding='utf-8')
        links = extract_links(text)
        for link in sorted(links):
            try:
                resp = session.head(link, allow_redirects=True, timeout=20)
                if resp.status_code >= 400:
                    resp = session.get(link, allow_redirects=True, timeout=20)
                resp.raise_for_status()
            except Exception as e:
                errors.append(f"{file_path}: broken link {link} ({e})")
    if errors:
        print('Broken documentation links found:')
        for err in errors:
            print(' -', err)
        sys.exit(1)
    print('All documentation links are valid.')
    sys.exit(0)

if __name__ == '__main__':
    main()