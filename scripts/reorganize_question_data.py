#!/usr/bin/env python3
"""
Utility script to reorganize the legacy question-data directory:
  - Archives redundant folders (json, md, yaml-bak, manifests) into question-data/archive
  - Consolidates all quiz YAML and solution scripts under question-data/yaml
  - Copies unified.json as a single YAML backup (all_questions.yaml)
  - Leaves all original content intact under archive and yaml/solutions
"""
import shutil
import os
from pathlib import Path

def main():
    root = Path(__file__).resolve().parents[1]
    qd = root / 'question-data'
    # Create archive directory
    archive = qd / 'archive'
    archive.mkdir(exist_ok=True)
    # Move redundant folders into archive
    for sub in ('json', 'md', 'yaml-bak', 'manifests'):
        src = qd / sub
        if src.exists():
            dest = archive / sub
            if dest.exists():
                # skip if already archived
                continue
            shutil.move(str(src), str(dest))
            print(f"Archived '{sub}' to 'question-data/archive/{sub}'")
    # Consolidate unified.json into a single YAML backup
    unified = qd / 'unified.json'
    yaml_dir = qd / 'yaml'
    if unified.exists() and yaml_dir.exists():
        all_yaml = yaml_dir / 'all_questions.yaml'
        if not all_yaml.exists():
            shutil.copy2(str(unified), str(all_yaml))
            print(f"Copied unified.json to '{all_yaml.name}' in yaml directory")
    # Copy solution scripts into yaml/solutions
    sol_src = qd / 'solutions'
    sol_dst = yaml_dir / 'solutions'
    if sol_src.exists():
        for category in sol_src.iterdir():
            if category.is_dir():
                dst_cat = sol_dst / category.name
                dst_cat.mkdir(parents=True, exist_ok=True)
                for item in category.iterdir():
                    dst_file = dst_cat / item.name
                    if not dst_file.exists():
                        shutil.copy2(str(item), str(dst_file))
                print(f"Copied solutions category '{category.name}' into yaml/solutions/{category.name}")
    print("Reorganization complete. Original content moved to question-data/archive, YAML backup and solutions consolidated under question-data/yaml.")

if __name__ == '__main__':
    main()