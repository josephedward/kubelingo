#!/usr/bin/env python3
"""
Add predefined Service Account questions to the Kubelingo database.

Refer to shared_context.md for full context on the unified question schema
(pre_shell_cmds, initial_files, validation_steps).

This script defines a set of Kubernetes ServiceAccount questions following the
standard quiz format (prompt, response, validation_steps) and persists them
into the local SQLite database used by Kubelingo. It uses the same schema and
format as the built-in question modules defined in question-data.

Questions are grouped under the category "Service Account Operations" and stored
with source_file "service_account_script" for easy filtering.
"""
import sys
import os

# Ensure project root on sys.path for module imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from kubelingo.database import init_db, add_question, get_questions_by_source_file

def main():
    # Override default database location to project-local to ensure writable path
    import kubelingo.utils.config as cfg
    local_app = os.path.join(PROJECT_ROOT, '.kubelingo')
    os.makedirs(local_app, exist_ok=True)
    cfg.APP_DIR = local_app
    cfg.DATABASE_FILE = os.path.join(local_app, 'kubelingo.db')
    # Override database file in database module to ensure writes go to project-local DB
    import kubelingo.database as db_mod
    db_mod.DATABASE_FILE = cfg.DATABASE_FILE
    # Initialize database and schema
    init_db()
    source_file = 'service_account_script'
    category = 'Service Account Operations'

    # Predefined questions
    questions = [
        {
            'id': f'{source_file}::1',
            'prompt': "Create a ServiceAccount named 'deployment-sa' in the 'prod' namespace.",
            'response': 'kubectl create serviceaccount deployment-sa -n prod',
            'validation_steps': [
                {'cmd': 'kubectl get serviceaccount deployment-sa -n prod', 'matcher': {'exit_code': 0}}
            ]
        },
        {
            'id': f'{source_file}::2',
            'prompt': "Create a Pod named 'sa-example' using image nginx and assign it the ServiceAccount 'deployment-sa'.",
            'response': (
                'apiVersion: v1\n'
                'kind: Pod\n'
                'metadata:\n'
                '  name: sa-example\n'
                'spec:\n'
                '  serviceAccountName: deployment-sa\n'
                '  containers:\n'
                '  - name: nginx\n'
                '    image: nginx'
            ),
            'validation_steps': [
                {'cmd': (
                    "kubectl get pod sa-example -o jsonpath='{.spec.serviceAccountName}'"
                ), 'matcher': {'exit_code': 0}}
            ]
        },
        {
            'id': f'{source_file}::3',
            'prompt': "Grant the 'edit' ClusterRole to the ServiceAccount 'deployment-sa' in namespace 'prod'.",
            'response': (
                'kubectl create rolebinding deployment-sa-edit --clusterrole=edit '
                '--serviceaccount=prod:deployment-sa -n prod'
            ),
            'validation_steps': [
                {'cmd': (
                    "kubectl get rolebinding deployment-sa-edit -n prod -o jsonpath='{.subjects[0].name}'"
                ), 'matcher': {'exit_code': 0}}
            ]
        }
    ]

    # Add or replace each question in the database
    for q in questions:
        add_question(
            id=q['id'],
            prompt=q['prompt'],
            source_file=source_file,
            response=q.get('response'),
            category=category,
            source='script',
            validation_steps=q.get('validation_steps'),
        )
        print(f"Added question {q['id']}")

    # Summarize
    entries = get_questions_by_source_file(source_file)
    print(f"Total ServiceAccount questions in DB (source={source_file}): {len(entries)}")

if __name__ == '__main__':  # noqa: E999
    main()