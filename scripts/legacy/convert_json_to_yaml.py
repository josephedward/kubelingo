#!/usr/bin/env python3
"""
Convert legacy JSON quizzes into YAML files under question-data/yaml.

Each JSON file under question-data/json or question-data/archive/json
will be parsed and its questions dumped into a corresponding
YAML file (same basename) in question-data/yaml.
"""
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("PyYAML is required: pip install PyYAML\n")
    sys.exit(1)

from kubelingo.modules.json_loader import JSONLoader

def main():
    repo_root = Path(__file__).resolve().parents[1]
    json_dirs = [repo_root / 'question-data' / 'json',
                 repo_root / 'question-data' / 'archive' / 'json']
    yaml_dir = repo_root / 'question-data' / 'yaml'
    yaml_dir.mkdir(parents=True, exist_ok=True)
    loader = JSONLoader()
    for src_dir in json_dirs:
        if not src_dir.exists():
            continue
        for json_file in sorted(src_dir.glob('*.json')):
            try:
                questions = loader.load_file(str(json_file))
                if not questions:
                    continue
                # Dump list of questions as YAML
                out_file = yaml_dir / (json_file.stem + '.yaml')
                with open(out_file, 'w', encoding='utf-8') as f:
                    yaml.safe_dump([q.__dict__ for q in questions], f,
                                   sort_keys=False)
                print(f"Converted {json_file.name} to {out_file.relative_to(repo_root)}")
            except Exception as e:
                sys.stderr.write(f"Failed to convert {json_file}: {e}\n")

if __name__ == '__main__':
    main()