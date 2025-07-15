#!/usr/bin/env python3
"""
verify_quiz_data.py: Validate quiz data including new YAML editing questions
"""
import json
import yaml
import re

def validate_yaml_edit_question(item):
    """Validate a yaml_edit question structure"""
    issues = []
    
    required_fields = ['prompt', 'starting_yaml', 'correct_yaml']
    for field in required_fields:
        if field not in item:
            issues.append(f"Missing required field: {field}")
    
    # Validate YAML syntax
    for yaml_field in ['starting_yaml', 'correct_yaml']:
        if yaml_field in item:
            try:
                yaml.safe_load(item[yaml_field])
            except yaml.YAMLError as e:
                issues.append(f"Invalid YAML in {yaml_field}: {e}")
    
    return issues

def load_data(path):
    with open(path, 'r') as f:
        return json.load(f)

def extract_name_and_image(response):
    '''Extracts the resource name (from 'run <name>' or 'create deployment <name>') and image (from '--image=') from a kubectl command.'''
    name = None
    image = None
    # match 'run <name>' or 'create deployment <name>'
    m = re.search(r'\b(?:run|create\s+deployment)\s+([^\s]+)', response)
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
    """Enhanced validation for different question types"""
    prompt = item.get('prompt', '')
    response = item.get('response', '')
    question_type = item.get('question_type', 'standard')
    issues = []
    
    if question_type == 'yaml_edit':
        # Validate YAML editing questions
        yaml_issues = validate_yaml_edit_question(item)
        issues.extend(yaml_issues)
    else:
        # Existing validation for standard questions
        name, image = extract_name_and_image(response)
        ns = extract_namespace(response)
        
        # Skip namespace check for echo commands
        if response.lstrip().startswith('echo '):
            ns = None
        
        if name and name not in prompt:
            issues.append(f"pod name '{name}' not in prompt")
        if image and image not in prompt:
            issues.append(f"image '{image}' not in prompt")
        if ns and ns not in prompt:
            issues.append(f"namespace '{ns}' not in prompt")
    
    return issues

def main():
    data_files = [
        'ckad_quiz_data_combined.json',
        'data/yaml_edit_questions.json',
        'data/ckad_exercises_extended.json'
    ]
    
    total_flagged = 0
    
    for data_file in data_files:
        try:
            with open(data_file, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            print(f"File not found: {data_file}, skipping...")
            continue
        except Exception as e:
            print(f"Error loading {data_file}: {e}")
            continue
        
        print(f"\n=== Validating {data_file} ===")
        flagged = []
        
        for section in data:
            for item in section.get('prompts', []):
                issues = check_prompt_item(item)
                if issues:
                    flagged.append((item.get('prompt', 'No prompt'), 
                                  item.get('response', 'No response'), 
                                  issues))
        
        if not flagged:
            print("✅ No issues found")
        else:
            print(f"❌ Found {len(flagged)} items with issues:")
            for prompt, response, issues in flagged:
                print(f"\nPrompt: {prompt[:80]}...")
                print(f"Response: {response[:80]}...")
                print(f"Issues: {', '.join(issues)}")
        
        total_flagged += len(flagged)
    
    print(f"\n=== Summary ===")
    print(f"Total issues found across all files: {total_flagged}")

if __name__ == '__main__':
    main()
