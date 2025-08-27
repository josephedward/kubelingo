import os
import sys
import requests
import yaml
import subprocess
from dotenv import dotenv_values
from colorama import Fore, Style

try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    import openai
except ImportError:
    openai = None

from kubelingo.utils import _get_llm_model, manifests_equivalent

def validate_manifest_with_llm(question_dict, user_manifest, verbose=True):
    """
    Validates a user-submitted manifest using the LLM."""
    # Extract solution manifest
    solution_manifest = None
    if isinstance(question_dict, dict):
        if isinstance(question_dict.get('suggestion'), list) and question_dict['suggestion']:
            solution_manifest = question_dict['suggestion'][0]
        elif 'solution' in question_dict:
            solution_manifest = question_dict['solution']
    # Local structural check for dict/list solutions
    if isinstance(solution_manifest, (dict, list)):
        try:
            user_obj = yaml.safe_load(user_manifest)
            is_correct = manifests_equivalent(solution_manifest, user_obj)
            return {'correct': is_correct, 'feedback': ''}
        except Exception:
            pass
    # Fallback to AI-powered validation
    llm_type, model = _get_llm_model(skip_prompt=True)
    if not model:
        return {'correct': False, 'feedback': "INFO: Set GEMINI_API_KEY or OPENAI_API_KEY for AI-powered manifest validation."}

    solution_manifest = None
    if isinstance(question_dict, dict):
        # Try to get from 'suggestion' first
        suggestion_list = question_dict.get('suggestion')
        if isinstance(suggestion_list, list) and suggestion_list:
            solution_manifest = suggestion_list[0]
        # If not found in 'suggestion', try 'solution'
        elif 'solution' in question_dict:
            solution_manifest = question_dict.get('solution')

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
    Student Manifest:\n{user_manifest}
    ---
    The canonical solution is:
    ---
    Solution Manifest:\n{solution_manifest}
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
    """Placeholder function for validating a kubectl command with dry-run."""
    # Implement the actual logic here
    return True, "kubectl dry-run successful!", "Details of the dry-run"
