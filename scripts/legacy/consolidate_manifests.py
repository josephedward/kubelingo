#!/usr/bin/env python3
"""
Consolidate all manifest-based YAML quizzes into a single file.

Scans question-data/archive/manifests/*.yaml for quiz definitions,
flattens their question lists, and writes to question-data/yaml/manifests_quiz.yaml.
"""
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("PyYAML is required: pip install PyYAML\n")
    sys.exit(1)

def main():
    repo_root = Path(__file__).resolve().parents[1]
    archive_dir = repo_root / 'question-data' / 'archive' / 'manifests'
    if not archive_dir.exists():
        sys.stderr.write(f"Archive manifests dir not found: {archive_dir}\n")
        sys.exit(1)
    all_questions = []
    for manifest_file in sorted(archive_dir.glob('*.yaml')):
        try:
            docs = list(yaml.safe_load_all(manifest_file.read_text(encoding='utf-8')))
        except Exception as e:
            sys.stderr.write(f"Failed to parse {manifest_file}: {e}\n")
            continue
        for doc in docs:
            if isinstance(doc, list):
                all_questions.extend(doc)
            elif isinstance(doc, dict) and 'questions' in doc:
                all_questions.extend(doc['questions'])
            elif isinstance(doc, dict) and 'id' in doc:
                all_questions.append(doc)
    if not all_questions:
        print("No manifest quizzes found to consolidate.")
        return
    dest_dir = repo_root / 'question-data' / 'yaml'
    dest_dir.mkdir(parents=True, exist_ok=True)
    out_file = dest_dir / 'manifests_quiz.yaml'
    try:
        with open(out_file, 'w', encoding='utf-8') as f:
            yaml.safe_dump(all_questions, f, sort_keys=False)
        print(f"Consolidated {len(all_questions)} manifest questions into {out_file.relative_to(repo_root)}")
    except Exception as e:
        sys.stderr.write(f"Failed to write {out_file}: {e}\n")

if __name__ == '__main__':
    main()