import os
import sys
import requests
import yaml
import subprocess
from dotenv import dotenv_values
try:
    from colorama import Fore, Style
except ImportError:
    class Fore:
        RED = YELLOW = GREEN = CYAN = ''
    class Style:
        BRIGHT = RESET_ALL = DIM = ''

try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    import openai
except ImportError:
    openai = None

import copy
from kubelingo.utils import _get_llm_model

def _normalize_manifest(obj):
    """
    Deep-copy a manifest object and remove non-essential fields (names) for equivalence comparison.
    Also sorts lists of dictionaries and recursively normalizes dictionary values.
    """
    if isinstance(obj, dict):
        m = copy.deepcopy(obj)
        # Recursively normalize dictionary values
        for k, v in m.items():
            m[k] = _normalize_manifest(v)

        # Remove top-level metadata name
        if 'metadata' in m and isinstance(m['metadata'], dict):
            m['metadata'].pop('name', None)
        
        # Remove container names and sort containers
        if 'spec' in m and isinstance(m['spec'], dict):
            spec = m['spec']
            if 'containers' in spec and isinstance(spec['containers'], list):
                for c in spec['containers']:
                    if isinstance(c, dict):
                        c.pop('name', None)
                # Sort containers by a canonical key if possible (e.g., image or a combination)
                # For simplicity, let's sort by a string representation of the container for now
                # A more robust solution might involve a custom sort key based on essential fields
                spec['containers'].sort(key=lambda x: str(x))
            
            # Sort env variables if present
            if 'containers' in spec and isinstance(spec['containers'], list):
                for c in spec['containers']:
                    if isinstance(c, dict) and 'env' in c and isinstance(c['env'], list):
                        c['env'].sort(key=lambda x: x.get('name', ''))

        return m
    elif isinstance(obj, list):
        # Recursively normalize list items
        normalized_list = [_normalize_manifest(item) for item in obj]
        # If all items are dictionaries, sort the list for canonical comparison
        if all(isinstance(item, dict) for item in normalized_list):
            # Sort by a canonical key if possible, e.g., 'name' for common Kubernetes lists
            # This needs to be robust to items without a 'name' key
            try:
                normalized_list.sort(key=lambda x: x.get('name', str(x)))
            except TypeError: # Fallback if items are not sortable by 'name' or str(x)
                normalized_list.sort(key=str) # Sort by string representation as a last resort
        return normalized_list
    else:
        return obj

def manifests_equivalent(sol_obj, user_obj):
    """
    Compare two manifest objects for structural equivalence, ignoring names and sorting lists.
    """
    normalized_sol = _normalize_manifest(sol_obj)
    normalized_user = _normalize_manifest(user_obj)
    return normalized_sol == normalized_user

def validate_manifest_with_llm(question_dict, user_input, verbose=True):
    """
    Validates a user-submitted manifest or kubectl command using the LLM and structural comparison.
    """
    # Extract solution manifest
    solution_manifest = question_dict.get('suggestion') or question_dict.get('solution')
    if isinstance(solution_manifest, list):
        solution_manifest = solution_manifest[0] if solution_manifest else None

    # If solution is a string, try to parse it as YAML
    if isinstance(solution_manifest, str):
        try:
            solution_manifest = yaml.safe_load(solution_manifest)
        except yaml.YAMLError:
            pass  # If it's not valid YAML, we'll fall through to the LLM

    user_obj = None
    is_command = False

    # Heuristic: Check if it looks like a YAML manifest
    looks_like_yaml = False
    if isinstance(user_input, str):
        # Check for common YAML manifest keywords
        if 'apiVersion:' in user_input or 'kind:' in user_input or 'metadata:' in user_input:
            looks_like_yaml = True
        
        # Also try to load it to see if it's valid YAML at all
        try:
            temp_obj = yaml.safe_load(user_input)
            if isinstance(temp_obj, (dict, list)):
                looks_like_yaml = True # Confirmed valid YAML structure
        except yaml.YAMLError:
            pass # Not valid YAML, so it's definitely not a manifest

    if looks_like_yaml:
        try:
            user_obj = yaml.safe_load(user_input)
            # If it's a scalar YAML (e.g., "hello"), it's not a valid K8s manifest
            # We still want the LLM to judge it as a manifest, not a command.
            if not isinstance(user_obj, (dict, list)):
                # If it's valid YAML but not a dict/list, set user_obj to None
                # The LLM prompt will still receive the raw user_input string.
                user_obj = None
        except yaml.YAMLError:
            # If it's not even valid YAML, then it's definitely not a manifest.
            # We'll let the LLM judge it as a malformed manifest.
            user_obj = None
    else:
        # If it doesn't look like YAML, assume it's a kubectl command
        is_command = True
        success, manifest_yaml, error_message = validate_kubectl_command_dry_run(user_input)
        if success:
            try:
                user_obj = yaml.safe_load(manifest_yaml)
            except yaml.YAMLError:
                return {'correct': False, 'feedback': f"Failed to parse manifest from kubectl dry-run output: {error_message}"}
        else:
            return {'correct': False, 'feedback': f"kubectl command dry-run failed: {error_message}"}

    # If both solution and user input are parsed manifests, compare structurally
    if isinstance(solution_manifest, (dict, list)) and isinstance(user_obj, (dict, list)):
        if manifests_equivalent(solution_manifest, user_obj):
            return {'correct': True, 'feedback': ''}
        # Otherwise fall through to AI-powered validation
    elif solution_manifest is None:
        return {'correct': False, 'feedback': 'No solution found in question data.'}

    # Compose the validation prompt and invoke the configured LLM

    # Fallback to AI-powered validation
    llm_type, model = _get_llm_model(skip_prompt=True)
    if not model:
        return {'correct': False, 'feedback': "INFO: Set GEMINI_API_KEY or OPENAI_API_KEY for AI-powered manifest validation."}

    # We need to re-extract the raw solution string for the prompt,
    # as solution_manifest might have been parsed.
    raw_solution_for_prompt = question_dict.get('suggestion') or question_dict.get('solution') or ''
    if isinstance(raw_solution_for_prompt, list):
        raw_solution_for_prompt = raw_solution_for_prompt[0] if raw_solution_for_prompt else ''
    if isinstance(raw_solution_for_prompt, dict):
        raw_solution_for_prompt = yaml.dump(raw_solution_for_prompt)


    if solution_manifest is None:
        return {'correct': False, 'feedback': 'No solution found in question data.'}

    # Compose prompt for validation
    prompt = f'''
    You are a Kubernetes expert grading a student's YAML manifest for a CKAD exam practice question.
    The student was asked:
    ---
    Question: {question_dict['question']}
    ---
    The student provided this manifest:
    ---
    Student Manifest:
{user_input}
    ---
    The canonical solution is:
    ---
    Solution Manifest:\n{raw_solution_for_prompt}
    ---
    Your task is to determine if the student's manifest is functionally correct. The manifests do not need to be textually identical. Do not penalize differences in metadata.name, container names, indentation styles (so long as a 'kubectl apply' would accept the manifest), or the order of fields; focus on correct apiVersion, kind, relevant metadata fields (except names), and spec details.
    First, on a line by itself, write "CORRECT" or "INCORRECT".
    Then, on a new line, provide a brief, one or two-sentence explanation for your decision.
    '''
    
    # Use only the configured LLM
    if llm_type == "gemini":
        try:
            response = model.generate_content(prompt)
            text = response.text.strip()
        except Exception as e:
            return {'correct': False, 'feedback': f"Error validating manifest with LLM: {e}"}
    elif llm_type == "openai":
        try:
            resp = model.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a Kubernetes expert grading a student's YAML manifest for a CKAD exam practice question."},
                    {"role": "user", "content": prompt}
                ]
            )
            text = resp.choices[0].message.content.strip()
        except Exception as e:
            return {'correct': False, 'feedback': f"Error validating manifest with LLM: {e}"}
    elif llm_type == "openrouter":
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=model["headers"],
                json={
                    "model": model["default_model"],
                    "messages": [
                        {"role": "system", "content": "You are a Kubernetes expert grading a student's YAML manifest for a CKAD exam practice question."},
                        {"role": "user", "content": prompt}
                    ]
                }
            )
            response.raise_for_status()
            text = response.json()['choices'][0]['message']['content'].strip()
        except Exception as e:
            return {'correct': False, 'feedback': f"Error validating manifest with LLM: {e}"}
    else:
        return {'correct': False, 'feedback': "No LLM configured"}
    lines = text.split('\n')
    is_correct = lines[0].strip().upper() == "CORRECT"
    feedback = "\n".join(lines[1:]).strip()
    return {'correct': is_correct, 'feedback': feedback}

def validate_manifest(manifest_content):
    """
    Validate a Kubernetes manifest string using external tools (yamllint, kubeconform, kubectl-validate).
    Returns a tuple: (success: bool, summary: str, details: str)."""
    config = dotenv_values(".env")
    validators = [
        ("yamllint", ["yamllint", "-"], "Validating YAML syntax"),
        ("kubeconform", ["kubeconform", "-strict", "-"], "Validating Kubernetes schema"),
        ("kubectl-validate", ["kubectl-validate", "-f", "-"], "Validating with kubectl-validate"),
    ]
    overall = True
    detail_lines = []
    for key, cmd, desc in validators:
        if config.get(f"KUBELINGO_VALIDATION_{key.upper()}", "True") != "True":
            continue
        detail_lines.append(f"=== {desc} ===")
        try:
            proc = subprocess.run(cmd, input=manifest_content, capture_output=True, text=True)
            out = proc.stdout.strip()
            err = proc.stderr.strip()
            if proc.returncode != 0:
                overall = False
                detail_lines.append(f"{key} failed (exit {proc.returncode}):")
                if out: detail_lines.append(out)
                if err: detail_lines.append(err)
            else:
                detail_lines.append(f"{key} passed.")
        except FileNotFoundError:
            detail_lines.append(f"{key} not found; skipping.")
        except Exception as e:
            overall = False
            detail_lines.append(f"Error running {key}: {e}")
    summary = f"{Fore.GREEN}All validations passed!{Style.RESET_ALL}" if overall else f"{Fore.RED}Validation failed.{Style.RESET_ALL}"
    return overall, summary, "\n".join(detail_lines)

def validate_manifest_with_kubectl_dry_run(manifest):
    """Placeholder function for validating a manifest with kubectl dry-run."""
    # Implement the actual logic here
    return True, "kubectl dry-run successful!", "Details of the dry-run"

def validate_kubectl_command_dry_run(command_string):
    """
    Validates a kubectl command by running it with --dry-run=client -o yaml
    and returns the generated manifest.
    Returns a tuple: (success: bool, manifest_yaml: str, error_message: str)
    """
    full_command = f"{command_string} --dry-run=client -o yaml"
    try:
        proc = subprocess.run(full_command, shell=True, capture_output=True, text=True, check=True)
        return True, proc.stdout, ""
    except subprocess.CalledProcessError as e:
        return False, "", f"Command failed with error: {e.stderr}"
    except FileNotFoundError:
        return False, "", "kubectl command not found. Is kubectl installed and in your PATH?"
    except Exception as e:
        return False, "", f"An unexpected error occurred: {e}"
