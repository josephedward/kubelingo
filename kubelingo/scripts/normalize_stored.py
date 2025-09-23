#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import yaml


def is_single_question(doc):
    return isinstance(doc, dict) and 'question' in doc and not 'questions' in doc


def normalize_single_question(doc):
    # Build standardized dict with preferred key order
    ordered = {}
    # Keep optional 'type' and 'topic' first if present
    for key in ('type', 'topic'):
        if key in doc and doc[key] is not None:
            ordered[key] = doc[key]
    # Required main fields
    for key in ('question', 'source', 'id', 'suggested_answer', 'user_answer', 'ai_feedback'):
        if key in doc and doc[key] is not None:
            ordered[key] = doc[key]
        else:
            # Backfill missing known fields
            if key == 'source' and 'source' not in ordered:
                ordered['source'] = doc.get('source', '')
            elif key == 'id' and 'id' not in ordered:
                ordered['id'] = doc.get('id', '')
            elif key == 'suggested_answer' and 'suggested_answer' not in ordered:
                # Promote scalar suggestion to suggested_answer if missing
                sugg = doc.get('suggestion')
                if isinstance(sugg, str):
                    ordered['suggested_answer'] = sugg
                else:
                    ordered['suggested_answer'] = doc.get('suggested_answer', '')
            elif key == 'user_answer' and 'user_answer' not in ordered:
                ordered['user_answer'] = ''
            elif key == 'ai_feedback' and 'ai_feedback' not in ordered:
                ordered['ai_feedback'] = ''

    # Drop redundant 'suggestion' for single-question docs
    # Keep only if it carries extra info and suggested_answer is empty
    if not ordered.get('suggested_answer') and isinstance(doc.get('suggestion'), str):
        ordered['suggested_answer'] = doc['suggestion']

    return ordered


def clean_bad_path_refs(value):
    if not isinstance(value, str):
        return value
    v = value.replace('questions/stored', 'stored')
    v = v.replace('/kubelingo/stored', 'stored')
    return v


def deep_clean_paths(obj):
    if isinstance(obj, dict):
        return {k: deep_clean_paths(clean_bad_path_refs(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [deep_clean_paths(v) for v in obj]
    return clean_bad_path_refs(obj)


def main(argv):
    if len(argv) > 1:
        base = Path(argv[1])
    else:
        base = Path(__file__).resolve().parents[1] / 'stored'

    if not base.is_dir():
        print(f"stored directory not found: {base}", file=sys.stderr)
        return 1

    changed = 0
    for path in sorted(base.glob('*.yaml')):
        try:
            text = path.read_text(encoding='utf-8')
            data = yaml.safe_load(text)
        except Exception:
            continue

        if data is None:
            continue

        original = data
        # Clean path references recursively
        data = deep_clean_paths(data)

        if is_single_question(data):
            data = normalize_single_question(data)
        else:
            # For collection files, do not change schema; just ensure any dict items have consistent key ordering for readability
            if isinstance(data, dict) and 'questions' in data and isinstance(data['questions'], list):
                new_list = []
                for item in data['questions']:
                    if isinstance(item, dict):
                        # Prefer a light normalization of keys: question, suggestion/solution, source, requirements, rationale
                        ordered = {}
                        for key in ('question', 'suggestion', 'solution', 'source', 'requirements', 'rationale'):
                            if key in item:
                                ordered[key] = item[key]
                        # Append any other keys deterministically
                        for k in sorted(item.keys()):
                            if k not in ordered:
                                ordered[k] = item[k]
                        new_list.append(ordered)
                    else:
                        new_list.append(item)
                data['questions'] = new_list

        if data != original:
            # Dump with block style for multiline strings, no key sorting
            dumped = yaml.dump(data, sort_keys=False, default_flow_style=False, allow_unicode=True)
            # Ensure file ends with a newline
            if not dumped.endswith('\n'):
                dumped += '\n'
            path.write_text(dumped, encoding='utf-8')
            changed += 1

    print(f"Normalized files changed: {changed}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))

