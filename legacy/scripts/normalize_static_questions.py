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

def derive_from_kubectl(cmd: str) -> dict:
    """Parse a kubectl command string into a requirements dict."""
    parts = cmd.split()
    if len(parts) < 3 or parts[0] != 'kubectl':
        return {}
    action = parts[1]
    req = {}
    if action == 'run':
        # kubectl run <name> --image=<image>
        name = parts[2]
        req['kind'] = 'Pod'
        req.setdefault('metadata', {})['name'] = name
        # parse flags
        for p in parts[3:]:
            if p.startswith('--image='):
                image = p.split('=', 1)[1]
                req.setdefault('spec', {})['containers'] = [{'name': name, 'image': image}]
        return req
    if action == 'create':
        # kubectl create <kind> <name> [--flags]
        if len(parts) < 4:
            return {}
        kind = parts[2].rstrip('s').capitalize()
        name = parts[3]
        req['kind'] = kind
        req.setdefault('metadata', {})['name'] = name
        for p in parts[4:]:
            if p.startswith('--image='):
                image = p.split('=', 1)[1]
                req.setdefault('spec', {})['containers'] = [{'name': name, 'image': image}]
            if p.startswith('--replicas='):
                try:
                    req.setdefault('spec', {})['replicas'] = int(p.split('=', 1)[1])
                except ValueError:
                    pass
        return req
    if action == 'expose':
        # kubectl expose deployment <target> --name=<svc> --port=<p> --target-port=<t> --type=<T>
        if len(parts) < 5:
            return {}
        target_kind = parts[2]
        target_name = parts[3]
        req['kind'] = 'Service'
        # parse flags
        svc_name = None
        spec = {}
        for p in parts[4:]:
            if p.startswith('--name='):
                svc_name = p.split('=', 1)[1]
            if p.startswith('--port='):
                try:
                    spec.setdefault('ports', [{}])[0].update({'port': int(p.split('=',1)[1])})
                except ValueError:
                    pass
            if p.startswith('--target-port='):
                try:
                    spec.setdefault('ports', [{}])[0].update({'targetPort': int(p.split('=',1)[1])})
                except ValueError:
                    pass
            if p.startswith('--type='):
                spec['type'] = p.split('=',1)[1]
        if svc_name:
            req.setdefault('metadata', {})['name'] = svc_name
        # infer selector from target deployment
        spec.setdefault('selector', {})['app'] = target_name
        req['spec'] = spec
        return req
    if action == 'apply':
        # kubectl apply -f <path>
        req = {'command': 'apply'}
        parts_iter = iter(parts[2:])
        for p in parts_iter:
            if p in ('-f', '--filename'):
                try:
                    fn = next(parts_iter)
                    req['filename'] = fn
                except StopIteration:
                    pass
            elif p.startswith('-f=') or p.startswith('--filename='):
                fn = p.split('=', 1)[1]
                req['filename'] = fn
        return req
    if action == 'edit':
        # kubectl edit <kind> <name>
        if len(parts) >= 4:
            kind = parts[2].rstrip('s').capitalize()
            name = parts[3]
            req = {'kind': kind, 'metadata': {'name': name}}
            return req
    return {}

def derive_from_manifest(data: dict) -> dict:
    """Extract key fields from a Kubernetes manifest dict into requirements."""
    req = {}
    # kind
    if 'kind' in data:
        req['kind'] = data['kind']
    # metadata.name
    meta = data.get('metadata', {})
    if 'name' in meta:
        req.setdefault('metadata', {})['name'] = meta['name']
    # spec
    spec = data.get('spec', {})
    s = {}
    if 'replicas' in spec:
        s['replicas'] = spec['replicas']
    # containers
    if 'containers' in spec:
        ctrs = spec['containers']
        lst = []
        for c in ctrs:
            e = {}
            if 'name' in c:
                e['name'] = c['name']
            if 'image' in c:
                e['image'] = c['image']
            lst.append(e)
        if lst:
            s['containers'] = lst
    # selector
    if 'selector' in spec:
        s['selector'] = spec['selector']
    # ports
    if 'ports' in spec:
        s['ports'] = spec['ports']
    if s:
        req['spec'] = s
    # configmap data
    if data.get('kind') == 'ConfigMap' and 'data' in data:
        req['data'] = data['data']
    return req

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
    # Preserve existing requirements, else derive from suggestions
    if 'requirements' in q and isinstance(q['requirements'], dict):
        new_q['requirements'] = q['requirements']
    else:
        # first try kubectl commands
        req = {}
        for item in normalized:
            if isinstance(item, str) and item.strip().startswith('kubectl'):
                r = derive_from_kubectl(item.strip())
                if r:
                    req = r
                    break
        # next try manifest suggestions
        if not req:
            for item in normalized:
                data = None
                if isinstance(item, dict):
                    data = item
                elif isinstance(item, str) and item.strip().startswith(('apiVersion:', 'kind:')):
                    try:
                        data = yaml.safe_load(item)
                    except Exception:
                        data = None
                if isinstance(data, dict):
                    req = derive_from_manifest(data)
                    break
        if req:
            new_q['requirements'] = req
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