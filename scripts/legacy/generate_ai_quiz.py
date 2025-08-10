#!/usr/bin/env python3
"""
Generate and validate Kubernetes kubectl quiz questions using OpenAI API.
Reads shared_context.md for context, uses few-shot examples to prompt the model,
validates format and syntax, and saves valid items to question-data/json/ai_generated_quiz.json.
Supports a --mock mode for testing validation without calling the API.
"""
import os
import sys
import json
import re
import argparse

# Load real OpenAI package, avoiding local openai.py stub
cwd = os.getcwd()
sys_path_backup = sys.path.copy()
sys.path = [p for p in sys.path if p not in ('', cwd)]
try:
    import openai
except ImportError:
    print("Error: openai package not found. Please install with 'pip install openai'.")
    sys.exit(1)
finally:
    sys.path = sys_path_backup

def load_shared_context():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    path = os.path.join(root, 'shared_context.md')
    try:
        with open(path, encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Warning: shared_context.md not found at {path}. Using empty context.")
        return ''

def generate_questions(api_key, examples, n):
    openai.api_key = api_key
    shared = load_shared_context()
    system_msg = {
        'role': 'system',
        'content': shared + "\nYou are a quiz generator for Kubernetes kubectl commands."
    }
    user_prompt = (
        f"Generate {n} quiz items as a JSON array of objects with 'question' and 'answer' fields. "
        "Each answer must be a valid kubectl command. Use the same format as the examples below.\n"
        "Examples: " + json.dumps(examples)
    )
    user_msg = {'role': 'user', 'content': user_prompt}
    resp = openai.ChatCompletion.create(
        model='gpt-3.5-turbo',
        messages=[system_msg, user_msg],
        temperature=0.7,
    )
    text = resp.choices[0].message.content.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print('Failed to parse JSON from AI response:', e)
        print('Response was:', text)
        return []

def validate_item(item):
    q = item.get('question', '').strip()
    a = item.get('answer', '').strip()
    if not q or not a:
        return False, 'Missing question or answer.'
    if not a.startswith('kubectl '):
        return False, "Answer does not start with 'kubectl '."
    # Basic resource type validation
    resource_types = [
        'pod', 'service', 'deployment', 'replicaset', 'statefulset', 'daemonset',
        'configmap', 'secret', 'job', 'cronjob', 'node', 'namespace', 'ingress',
        'persistentvolume', 'persistentvolumeclaim', 'pv', 'pvc'
    ]
    if not any(rt in q.lower() for rt in resource_types):
        return False, 'Question does not mention a Kubernetes resource type.'
    return True, ''

def main():
    parser = argparse.ArgumentParser(description='Generate and validate Kubernetes quizzes via OpenAI')
    parser.add_argument('--num', type=int, default=5, help='Number of questions to generate')
    parser.add_argument('--mock', action='store_true', help='Use mock data for testing validation')
    parser.add_argument('--output', default=None, help='Output JSON file path')
    args = parser.parse_args()
    api_key = os.getenv('OPENAI_API_KEY')
    examples = [
        { 'question': 'How do you list all running pods in the default namespace?',
          'answer': 'kubectl get pods --field-selector=status.phase=Running' },
        { 'question': 'How do you delete a deployment named frontend in the prod namespace?',
          'answer': 'kubectl delete deployment frontend -n prod' }
    ]
    if args.output:
        out_path = args.output
    else:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        out_dir = os.path.join(project_root, 'question-data', 'json')
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, 'ai_generated_quiz.json')

    if args.mock:
        items = [
            { 'question': 'How do you delete a pod named my-pod in the default namespace?',
              'answer': 'kubectl delete pod my-pod' },
            { 'question': 'List services in namespace prod',
              'answer': 'kubectl get svc -n prod' },
            { 'question': 'Expose deployment my-app on port 80',
              'answer': 'expose deployment my-app --port=80' },
            { 'question': 'How to get cluster version?',
              'answer': 'kubectl version' }
        ]
    else:
        if not api_key:
            print('Error: Missing OPENAI_API_KEY environment variable.')
            sys.exit(1)
        items = generate_questions(api_key, examples, args.num)

    valid = []
    for idx, item in enumerate(items, start=1):
        ok, msg = validate_item(item)
        if ok:
            valid.append(item)
        else:
            print(f'Item {idx} invalid: {msg}')

    if not valid:
        print('No valid items to save.')
        sys.exit(0)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(valid, f, indent=2)
    print(f'Saved {len(valid)} valid items to {out_path}')

if __name__ == '__main__':  # noqa: E999
    main()