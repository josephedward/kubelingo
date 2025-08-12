#!/usr/bin/env python3
"""
Merge individual solution scripts into a single YAML file per category.

This script scans question-data/yaml/solutions/<category>/ for .sh and .yaml files,
reads their contents, and emits <category>_solutions.yaml consolidating all entries.
"""
#!/usr/bin/env python3
"""
Merge individual solution scripts into a single YAML file per category.

Scans question-data/yaml/solutions/<category>/ for .sh and .yaml files,
reads their contents, and emits <category>_solutions.yaml consolidating all entries.
"""
import sys
from pathlib import Path
from textwrap import indent

def consolidate_category(category_dir: Path):
    entries = {}
    for file_path in sorted(category_dir.iterdir()):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in ('.sh', '.yaml', '.yml'):
            continue
        key = file_path.stem
        try:
            entries[key] = file_path.read_text(encoding='utf-8')
        except Exception as e:
            sys.stderr.write(f"Failed to read {file_path}: {e}\n")
    if not entries:
        return
    out_file = category_dir / f"{category_dir.name}_solutions.yaml"
    try:
        with open(out_file, 'w', encoding='utf-8') as wf:
            for key, content in entries.items():
                wf.write(f"{key}: |-\n")
                wf.write(indent(content.rstrip('\n'), '  '))
                wf.write("\n\n")
        print(f"Consolidated {len(entries)} files into {out_file.relative_to(Path.cwd())}")
    except Exception as e:
        sys.stderr.write(f"Failed to write {out_file}: {e}\n")

def main():
    repo_root = Path(__file__).resolve().parents[1]
    sol_root = repo_root / 'question-data' / 'yaml' / 'solutions'
    if not sol_root.is_dir():
        sys.stderr.write(f"Solutions directory not found: {sol_root}\n")
        sys.exit(1)
    for category_dir in sorted(sol_root.iterdir()):
        if category_dir.is_dir():
            consolidate_category(category_dir)

if __name__ == '__main__':
    main()