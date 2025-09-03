#!/usr/bin/env python3
"""
Auto-generate CKAD-style manifest questions using CLI tools.

This script uses kubectl dry-run, yq, and kube-score to create valid
Kubernetes manifest questions without relying on an LLM.

Other agents: This file defines a deterministic, tools-based fallback for
question generation. It reads a topic-to-command mapping, runs each
kubectl command to produce a manifest, validates it, and writes a new
question into questions/<topic>.yaml.
"""
import os
import subprocess
import yaml

# Configuration: topic -> generation parameters
TOPIC_CONFIG = {
    'app_configuration': {
        'cmd': [
            'kubectl', 'create', 'configmap', 'example-config',
            '--from-literal=LOG_LEVEL=DEBUG',
            '--dry-run=client', '-o', 'yaml'
        ],
        'source': 'https://kubernetes.io/docs/concepts/configuration/configmap/',
        'rationale': 'Tests ability to create a ConfigMap with key/value pairs using kubectl.',
        'section': 'Configuration'
    },
    'image_registry_use': {
        'cmd': [
            'kubectl', 'create', 'secret', 'docker-registry', 'regcred',
            '--docker-server=myregistry.com',
            '--docker-username=myuser',
            '--docker-password=mypassword',
            '--docker-email=myuser@example.com',
            '--dry-run=client', '-o', 'yaml'
        ],
        'source': 'https://kubernetes.io/docs/tasks/configure-pod-container/pull-image-private-registry/',
        'rationale': 'Tests ability to create a docker-registry secret for private image pulls.',
        'section': 'Security'
    },
    # Add more topic mappings as needed
}

QUESTIONS_DIR = os.path.join(os.path.dirname(__file__), os.pardir, 'questions')

def load_questions(topic):
    path = os.path.join(QUESTIONS_DIR, f"{topic}.yaml")
    if os.path.exists(path):
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return data.get('questions', []), path
    return [], path

def save_questions(topic, questions, path):
    out = {'questions': questions}
    with open(path, 'w') as f:
        yaml.safe_dump(out, f, default_flow_style=False)
    print(f"Updated {path} with {len(questions)} questions.")

def validate_manifest(manifest_yaml):
    # Validate using kube-score
    try:
        proc = subprocess.run(
            ['kube-score', 'score', '-'],
            input=manifest_yaml,
            text=True,
            capture_output=True
        )
        if proc.returncode != 0:
            print(f"kube-score validation failed:\n{proc.stdout}{proc.stderr}")
            return False
        return True
    except FileNotFoundError:
        print("kube-score not found; skipping validation.")
        return True

def generate_for_topic(topic, cfg):
    print(f"Generating question for topic '{topic}'...")
    # Run kubectl command
    try:
        proc = subprocess.run(cfg['cmd'], text=True, capture_output=True, check=True)
        manifest = proc.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running kubectl: {e.stderr}")
        return None

    # Validate manifest
    if not validate_manifest(manifest):
        return None

    # Build question dict
    q = {
        'question': f"Generate the Kubernetes manifest for topic '{topic}' using the CLI.",
        'suggestion': manifest.strip(),
        'source': cfg['source'],
        'rationale': cfg['rationale'],
        'section': cfg['section'],
    }
    return q

def main():
    for topic, cfg in TOPIC_CONFIG.items():
        questions, path = load_questions(topic)
        new_q = generate_for_topic(topic, cfg)
        if new_q:
            # Append and save
            questions.append(new_q)
            save_questions(topic, questions, path)

if __name__ == '__main__':
    main()