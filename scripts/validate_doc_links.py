#!/usr/bin/env python3
"""
Validate documentation URLs found in question entries (database).  
"""
import re
import sys
import argparse
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from kubelingo.database import get_all_questions

URL_PATTERN = re.compile(r'https?://[^\s)]+')

def check_url(url):
    try:
        req = Request(url, method='HEAD')
        resp = urlopen(req, timeout=5)
        return resp.getcode()
    except HTTPError as e:
        return e.code
    except URLError as e:
        return None
    except Exception:
        return None

def main():
    parser = argparse.ArgumentParser(
        description="Check all HTTP/HTTPS links in question prompts and responses."
    )
    parser.add_argument(
        '--fail-only', action='store_true', help='Show only broken links'
    )
    args = parser.parse_args()

    questions = get_all_questions()
    broken = []
    for q in questions:
        text = ' '.join(filter(None, [q.get('prompt'), q.get('response')]))
        for url in URL_PATTERN.findall(text):
            code = check_url(url)
            if code is None or code >= 400:
                broken.append((q.get('id'), url, code))
                if not args.fail_only:
                    print(f"[{q.get('id')}] {url} -> {code}")
    if args.fail_only:
        for qid, url, code in broken:
            print(f"[{qid}] {url} -> {code}")
    if not broken:
        print("No broken links detected.")

if __name__ == '__main__':
    main()