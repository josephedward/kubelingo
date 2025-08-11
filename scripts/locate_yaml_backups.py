#!/usr/bin/env python3
"""
Locates YAML backup files, providing detailed information, JSON output, or an AI-generated summary.
This utility scans configured backup directories and allows for flexible filtering and reporting.
"""
import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

# Ensure the project root is in the Python path
try:
    import kubelingo
except ImportError:
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

from kubelingo.utils.config import YAML_BACKUP_DIRS

# AI summary is an optional feature
try:
    import openai
except ImportError:
    openai = None


def get_backup_files(directories: List[str], pattern: Optional[str] = None) -> List[Path]:
    """Finds all YAML backup files in the given directories, optionally filtering by a regex pattern."""
    all_files = []
    for d in directories:
        p = Path(d)
        if p.is_dir():
            all_files.extend(p.glob("**/*.yaml"))
            all_files.extend(p.glob("**/*.yml"))

    if pattern:
        regex = re.compile(pattern)
        all_files = [f for f in all_files if regex.search(str(f))]

    return sorted(list(set(all_files)))


def get_file_stats(path: Path) -> Dict[str, Any]:
    """Returns metadata for a given file path."""
    stat = path.stat()
    return {
        "path": str(path),
        "size_bytes": stat.st_size,
        "last_modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }


def generate_ai_summary(file_info_json: str, api_key: Optional[str] = None) -> str:
    """Generates a summary of the backup files using an AI model."""
    if not openai:
        return "Error: 'openai' package not found. Please run 'pip install openai' to use AI summary."
    
    api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "Error: OPENAI_API_KEY environment variable not set and no --api-key provided. Cannot use AI summary."

    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Summarize the following list of backup files. "
                               "Focus on the number of files, their total size, and the date range of modifications.",
                },
                {"role": "user", "content": f"Here is the backup file data in JSON format:\n{file_info_json}"},
            ],
            temperature=0,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error generating AI summary: {e}"


def main():
    """Main function to locate and report on YAML backup files."""
    parser = argparse.ArgumentParser(
        description="Locate YAML backup files with advanced filtering and reporting.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "primary_dir",
        nargs="?",
        default=None,
        help="Primary directory to scan. If not provided, uses all configured default backup directories.",
    )
    parser.add_argument(
        "-d",
        "--dir",
        action="append",
        dest="additional_dirs",
        default=[],
        help="Add another directory to scan. Can be specified multiple times.",
    )
    parser.add_argument("--pattern", help="Regex pattern to filter file paths.")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format.")
    parser.add_argument("--ai", action="store_true", help="Generate an AI-powered summary of the findings.")
    parser.add_argument("--api-key", help="OpenAI API key. If not provided, uses OPENAI_API_KEY env var.")
    args = parser.parse_args()

    scan_dirs = []
    if args.primary_dir:
        scan_dirs.append(args.primary_dir)
    scan_dirs.extend(args.additional_dirs)

    if not scan_dirs:
        scan_dirs = YAML_BACKUP_DIRS

    try:
        files = get_backup_files(scan_dirs, args.pattern)
    except Exception as e:
        print(f"Error scanning directories: {e}", file=sys.stderr)
        sys.exit(1)

    if not files:
        dirs_str = ', '.join(scan_dirs)
        if args.json:
            print(json.dumps([]))
        else:
            print(f"No YAML backups found in {dirs_str}")
        sys.exit(0)

    stats = [get_file_stats(f) for f in files]

    if args.json:
        print(json.dumps(stats, indent=2))
    elif args.ai:
        summary = generate_ai_summary(json.dumps(stats), api_key=args.api_key)
        print("--- AI Summary ---")
        print(summary)
    else:
        print("--- Located YAML Backups ---")
        for s in stats:
            size_kb = s['size_bytes'] / 1024
            mod_time = datetime.datetime.fromisoformat(s['last_modified']).strftime('%Y-%m-%d %H:%M:%S')
            print(f"{s['path']:<70} {size_kb:8.2f} KB   Modified: {mod_time}")
        print(f"\nFound {len(stats)} file(s).")


if __name__ == "__main__":
    main()
