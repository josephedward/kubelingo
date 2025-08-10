#!/usr/bin/env python3
"""
Suggest documentation citations for Kubelingo command-quiz questions based on known URL mappings.
Because there is no internet access, we use a local mapping of common kubectl subcommands to their
Kubernetes documentation URLs.
"""
import os
import json
import re
from kubelingo.modules.json_loader import JSONLoader

# Mapping of kubectl subcommand prefixes to documentation URLs
URL_MAP = {
    'kubectl get ns': 'https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#get',
    'kubectl create sa': 'https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#create-serviceaccount',
    'kubectl describe sa': 'https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#describe',
    # Add more mappings as needed
}

def suggest_citation(answer_cmd):
    """Return the first matching URL for the given command answer."""
    for prefix, url in URL_MAP.items():
        if answer_cmd.startswith(prefix):
            return url
    return None

def main():
    loader = JSONLoader()
    paths = loader.discover()
    if not paths:
        print("No JSON question files found to analyze.")
        return
    for path in paths:
        try:
            items = json.load(open(path, encoding='utf-8'))
        except Exception as e:
            print(f"Failed to load {path}: {e}")
            continue
        print(f"\nFile: {path}")
        for idx, item in enumerate(items):
            answer = item.get('response') or ''
            qtext = item.get('prompt') or item.get('question') or ''
            citation = suggest_citation(answer)
            if citation:
                print(f" {idx+1}. {qtext}\n     -> Suggest citation: {citation}")
            else:
                print(f" {idx+1}. {qtext}\n     -> No citation found.")

if __name__ == '__main__':  # noqa: E999
    main()