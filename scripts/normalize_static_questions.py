#!/usr/bin/env python3
"""
Normalize static questions from data/questions into kubelingo/questions,
adhering to the canonical schema.
Usage:
  python scripts/normalize_static_questions.py --src data/questions --dst kubelingo/questions
"""
import os
import sys
import yaml
import hashlib

BASE_CRITERIA = [
    "YAML syntax is valid",
    "Required Kubernetes resources are defined",
    "Resource specifications are complete"
]

def generate_id(text: str) -> str:
    """Generate a short MD5-based ID from the question text"""
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:8]

def normalize_question(q: dict) -> dict:
    """Normalize a single question dict to the canonical schema"""
    # Required fields
    question_text = q.get('question', '').strip()
    new_q = {
        'id': generate_id(question_text),
        'question': question_text,
        'success_criteria': BASE_CRITERIA.copy(),
    }
    # Suggestions: normalize singular or plural key
    suggestions_raw = q.get('suggestion') if 'suggestion' in q else q.get('suggestions')
    normalized = []
    if isinstance(suggestions_raw, list):
        for item in suggestions_raw:
            if isinstance(item, (dict, list)):
                # Keep as structured data
                normalized.append(item)
            else:
                # Plain string entries
                s = str(item).strip()
                # Attempt to parse YAML into structured data
                try:
                    parsed = yaml.safe_load(s)
                    if isinstance(parsed, (dict, list)):
                        normalized.append(parsed)
                        continue
                except Exception:
                    pass
                normalized.append(s)
    elif isinstance(suggestions_raw, dict):
        # Single dict suggestion: keep as structured data
        normalized.append(suggestions_raw)
    elif isinstance(suggestions_raw, str):
        s = suggestions_raw
        # Unescape JSON-style literal \n and \t
        if '\\n' in s or '\\t' in s:
            try:
                s = s.encode('utf-8').decode('unicode_escape')
            except Exception:
                pass
        # Attempt to parse as multi-line YAML
        block = None
        if '\n' in s and ('apiVersion:' in s or 'kind:' in s):
            try:
                data = yaml.safe_load(s)
                block = yaml.safe_dump(
                    data, sort_keys=False, default_flow_style=False
                ).strip()
            except Exception:
                block = None
        # Append either the parsed block or the raw string
        if block is not None:
            normalized.append(block)
        else:
            normalized.append(s.strip())
    # Assign suggestions list
    new_q['suggestions'] = normalized
    # Source if present
    if 'source' in q:
        new_q['source'] = q['source']
    # Optional difficulty and requirements forwarded if present
    if 'difficulty' in q:
        new_q['difficulty'] = q['difficulty']
    # Preserve existing structured requirements, or auto-derive from the first YAML suggestion
    if 'requirements' in q and isinstance(q['requirements'], dict):
        new_q['requirements'] = q['requirements']
    else:
        # Attempt to parse requirements from YAML suggestion
        derived = {}
        for item in normalized:
            # Determine if this suggestion is structured data or YAML string
            data = None
            if isinstance(item, dict) or isinstance(item, list):
                data = item
            elif isinstance(item, str):
                # Only parse strings that look like YAML manifests
                if item.strip().startswith(('apiVersion:', 'kind:')):
                    try:
                        data = yaml.safe_load(item)
                    except Exception:
                        continue
            if not isinstance(data, dict):
                continue
                # Top-level kind
                if 'kind' in data:
                    derived['kind'] = data['kind']
                # Metadata.name
                meta = data.get('metadata', {})
                if 'name' in meta:
                    derived.setdefault('metadata', {})['name'] = meta['name']
                # spec
                spec = data.get('spec', {})
                # replicas
                if 'replicas' in spec:
                    derived['replicas'] = spec['replicas']
                # containers (first)
                containers = spec.get('containers', [])
                if containers:
                    c = containers[0]
                    derived.setdefault('container', {})['name'] = c.get('name')
                    if 'image' in c:
                        derived['container']['image'] = c.get('image')
                    # resources
                    res = c.get('resources', {})
                    if 'requests' in res:
                        derived['requests'] = res.get('requests', {})
                    if 'limits' in res:
                        derived['limits'] = res.get('limits', {})
                # Service-specific
                if data.get('kind') == 'Service':
                    ports = spec.get('ports', [])
                    if ports:
                        p0 = ports[0]
                        derived.setdefault('ports', {})['port'] = p0.get('port')
                        if 'targetPort' in p0:
                            derived['ports']['targetPort'] = p0.get('targetPort')
                    if 'selector' in spec:
                        derived['selector'] = spec.get('selector')
                # ConfigMap-specific
                if data.get('kind') == 'ConfigMap' and 'data' in data:
                    derived['data'] = data.get('data')
                break
        if derived:
            new_q['requirements'] = derived
    # Return normalized question
    return new_q

def normalize_all(src_dir: str, dst_dir: str):
    """Normalize all YAML files under src_dir into dst_dir"""
    for filename in os.listdir(src_dir):
        if not filename.endswith('.yaml') and not filename.endswith('.yml'):
            continue
        src_path = os.path.join(src_dir, filename)
        data = yaml.safe_load(open(src_path, encoding='utf-8')) or {}
        questions = data.get('questions', [])
        if not questions:
            continue
        norm_list = []
        for q in questions:
            norm_q = normalize_question(q)
            norm_list.append(norm_q)
        # Write output
        out = {'questions': norm_list}
        dst_path = os.path.join(dst_dir, filename)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        with open(dst_path, 'w', encoding='utf-8') as f:
            # Use yaml.dump to leverage custom multiline string representer
            yaml.dump(out, f, sort_keys=False)
        print(f"Normalized {src_path} → {dst_path}")

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Normalize static questions into canonical schema"
    )
    parser.add_argument('--src', required=True, help='Source directory of raw YAML questions')
    parser.add_argument('--dst', required=True, help='Destination directory for normalized questions')
    args = parser.parse_args()
    normalize_all(args.src, args.dst)

if __name__ == '__main__':
    main()