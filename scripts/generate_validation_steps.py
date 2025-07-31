#!/usr/bin/env python3
"""
Generate validation_steps for Kubernetes questions by parsing the 'answer' field
and adding JSONPath checks for metadata and spec fields.
"""
import argparse
import json
import sys
from pathlib import Path

import yaml

def generate_steps(answer_yaml: str):
    try:
        obj = yaml.safe_load(answer_yaml)
    except Exception:
        return []
    kind = obj.get('kind')
    metadata = obj.get('metadata', {})
    name = metadata.get('name')
    namespace = metadata.get('namespace')
    if not kind or not name:
        return []
    steps = []
    base = kind.lower()

    def add(cmd, matcher):
        steps.append({'cmd': cmd, 'matcher': matcher})

    # metadata.name
    cmd = f"kubectl get {base} {name}"
    if namespace:
        cmd += f" -n {namespace}"
    cmd += " -o jsonpath='{.metadata.name}'"
    add(cmd, {'value': name})

    # metadata.namespace
    if namespace:
        cmd = f"kubectl get {base} {name} -n {namespace} -o jsonpath='{{.metadata.namespace}}'"
        add(cmd, {'value': namespace})

    spec = obj.get('spec', {}) or {}
    # replicas
    replicas = spec.get('replicas')
    if replicas is not None:
        cmd = f"kubectl get {base} {name}"
        if namespace:
            cmd += f" -n {namespace}"
        cmd += " -o jsonpath='{.spec.replicas}'"
        add(cmd, {'value': replicas})

    # containers: Pod vs other resources
    containers = None
    if base == 'pod':
        containers = spec.get('containers', [])
        path = '.spec.containers[0]'
    else:
        tmpl = spec.get('template', {}) or {}
        containers = tmpl.get('spec', {}).get('containers', []) or []
        path = '.spec.template.spec.containers[0]'
    if containers:
        # container image
        image = containers[0].get('image')
        if image:
            cmd = f"kubectl get {base} {name}"
            if namespace:
                cmd += f" -n {namespace}"
            cmd += f" -o jsonpath='{{{path}.image}}'"
            add(cmd, {'value': image})
        # resource requests/limits
        resources = containers[0].get('resources', {}) or {}
        for kind_res in ('requests', 'limits'):
            part = resources.get(kind_res, {}) or {}
            for key, val in part.items():
                jsonpath = f"{{{path}.resources.{kind_res}.{key}}}"
                cmd = f"kubectl get {base} {name}"
                if namespace:
                    cmd += f" -n {namespace}"
                cmd += f" -o jsonpath='{jsonpath}'"
                add(cmd, {'value': val})
        # probes
        for probe in ('readinessProbe', 'livenessProbe'):
            pr = containers[0].get(probe, {}) or {}
            exec_block = pr.get('exec') or {}
            if isinstance(exec_block, dict):
                cm = exec_block.get('command') or []
                if cm:
                    cmd = f"kubectl get {base} {name}"
                    if namespace:
                        cmd += f" -n {namespace}"
                    cmd += f" -o jsonpath='{{{path}.{probe}.exec.command}}'"
                    add(cmd, {'contains': cm[0]})
            for attr in ('initialDelaySeconds', 'periodSeconds', 'timeoutSeconds', 'failureThreshold'):
                val = pr.get(attr)
                if val is not None:
                    cmd = f"kubectl get {base} {name}"
                    if namespace:
                        cmd += f" -n {namespace}"
                    cmd += f" -o jsonpath='{{{path}.{probe}.{attr}}}'"
                    add(cmd, {'value': val})

    return steps

def process_file(path: Path, overwrite: bool):
    data = json.loads(path.read_text(encoding='utf-8'))
    changed = False
    for q in data:
        steps = generate_steps(q.get('answer', ''))
        if steps:
            q['validation_steps'] = steps
            changed = True
    if not changed:
        print(f"No validation_steps generated for {path}")
        return
    dest = path if overwrite else path.with_suffix('.validated.json')
    dest.write_text(json.dumps(data, indent=2), encoding='utf-8')
    print(f"Wrote updated questions to {dest}")

def main():
    parser = argparse.ArgumentParser(description="Generate validation_steps for Kubernetes questions")
    parser.add_argument('in_path', type=Path, help="JSON file or directory to process")
    parser.add_argument('--overwrite', action='store_true', help="Overwrite original files")
    args = parser.parse_args()
    paths = []
    if args.in_path.is_dir():
        paths = list(args.in_path.glob('*.json'))
    else:
        paths = [args.in_path]
    for p in paths:
        process_file(p, args.overwrite)

if __name__ == '__main__':
    main()