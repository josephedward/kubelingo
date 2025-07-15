#!/usr/bin/env python3
"""
verify_quiz_data.py: Identify quiz prompts that omit details used in their answers.
"""
import json
import re
import yaml

def load_data(path):
    with open(path, 'r') as f:
        return json.load(f)

def extract_name_and_image(response):
    '''Extracts the pod name (from 'run <name>') and image (from '--image=') from a kubectl command.'''
    name = None
    image = None
    # match 'run <name>'
    m = re.search(r'\brun\s+([^\s]+)', response)
    if m:
        name = m.group(1)
    # match '--image=<image>'
    m2 = re.search(r'--image=([^\s]+)', response)
    if m2:
        image = m2.group(1)
    return name, image

def extract_namespace(response):
    '''Extracts the namespace from '-n <ns>' or '--namespace=<ns>'.'''
    # match only '-n' or '--namespace' flags, not '--name'
    m = re.search(r'(?:(?:^|\s)-n\s*=?|(?:^|\s)--namespace\s*=?)([^\s]+)', response)
    if m:
        return m.group(1)
    return None

def check_prompt_item(item):
    question_type = item.get('type', 'command')
    issues = []

    if question_type == 'yaml_edit':
        if 'starting_yaml' not in item:
            issues.append("missing 'starting_yaml' key")
        else:
            try:
                yaml.safe_load(item['starting_yaml'])
            except yaml.YAMLError as e:
                issues.append(f"invalid YAML in 'starting_yaml': {e}")
        
        if 'correct_yaml' not in item:
            issues.append("missing 'correct_yaml' key")
        else:
            try:
                yaml.safe_load(item['correct_yaml'])
            except yaml.YAMLError as e:
                issues.append(f"invalid YAML in 'correct_yaml': {e}")

    else: # command-based question
        prompt = item.get('prompt', '')
        response = item.get('response', '')
        name, image = extract_name_and_image(response)
        ns = extract_namespace(response)
        # Skip namespace check for echo commands (e.g., base64 encode/decode)
        if response.lstrip().startswith('echo '):
            ns = None
        # Check that any extracted elements appear in the prompt
        if name and name not in prompt:
            issues.append(f"pod name '{name}' not in prompt")
        if image and image not in prompt:
            issues.append(f"image '{image}' not in prompt")
        if ns and ns not in prompt:
            issues.append(f"namespace '{ns}' not in prompt")

    return issues

def main():
    data_file = 'ckad_quiz_data_combined.json'
    try:
        data = load_data(data_file)
    except Exception as e:
        print(f"Error loading combined data from {data_file}: {e}")
        return
    flagged = []
    for section in data:
        for item in section.get('prompts', []):
            issues = check_prompt_item(item)
            if issues:
                flagged.append((item['prompt'], item['response'], issues))
    if not flagged:
        print("No prompts found that omit details used in their answers.")
        return
    print(f"Found {len(flagged)} prompts with potential issues:\n")
    for prompt, response, issues in flagged:
        print(f"Prompt: {prompt}")
        print(f"Answer: {response}")
        print(f"Issues: {', '.join(issues)}\n")

if __name__ == '__main__':
    main()
