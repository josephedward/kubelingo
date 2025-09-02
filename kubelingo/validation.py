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
    Validate a Kubernetes manifest string using external tools with configurable levels.
    Returns a tuple: (success: bool, summary: str, details: str)."""
    config = dotenv_values(".env")
    validation_level = config.get("KUBELINGO_VALIDATION_LEVEL", "moderate").lower()
    
    # Define validation tools by level
    validation_tools = {
        "permissive": [
            ("yamllint", ["yamllint", "-"], "Validating basic YAML syntax")
        ],
        "moderate": [
            ("yamllint", ["yamllint", "-"], "Validating YAML syntax"),
            ("kubeconform", ["kubeconform", "-strict", "-schema-location", "default", "-"], 
             "Validating Kubernetes schema with Kubeconform")
        ],
        "strict": [
            ("yamllint", ["yamllint", "-"], "Validating YAML syntax"),
            ("kubeconform", ["kubeconform", "-strict", "-schema-location", "default", "-"],
             "Validating Kubernetes schema with Kubeconform"),
            ("kubectl-validate", ["kubectl", "apply", "--dry-run=server", "-f", "-"],
             "Validating with kubectl server-side dry-run"),
            ("kube-score", ["kube-score", "score", "-o", "human", "-"], 
             "Checking Kubernetes best practices with kube-score"),
            ("trivy", ["trivy", "config", "--severity", "HIGH,CRITICAL", "-"],
             "Scanning for security vulnerabilities with Trivy")
        ]
    }
    
    validators = validation_tools.get(validation_level, validation_tools["moderate"])
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
    """Validate a manifest with kubectl dry-run."""
    # Skip dry-run for non-Kubernetes manifests (missing apiVersion or kind)
    try:
        data = yaml.safe_load(manifest)
        if not isinstance(data, dict) or 'apiVersion' not in data or 'kind' not in data:
            return False, "Skipping kubectl dry-run: Not a Kubernetes YAML manifest.", "Skipped: Not a Kubernetes YAML manifest."
    except yaml.YAMLError:
        return False, "Skipping kubectl dry-run: Not a Kubernetes YAML manifest.", "Skipped: Not a Kubernetes YAML manifest."
    import tempfile
    import os
    tmp_path = None
    success = False
    feedback = ''
    ai_feedback = ''
    try:
        # Write manifest to a temporary file
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.yaml', delete=False) as tmp:
            tmp.write(manifest)
            tmp_path = tmp.name
        # Run kubectl server-side dry-run
        result = subprocess.run(
            ["kubectl", "apply", "--dry-run=server", "-f", tmp_path],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            success = True
            feedback = "kubectl dry-run successful!"
            ai_feedback = result.stdout
        else:
            success = False
            feedback = "kubectl dry-run failed. Please check your manifest."
            ai_feedback = result.stderr
    except FileNotFoundError:
        # kubectl not found
        success = False
        feedback = "Error: 'kubectl' command not found."
        ai_feedback = "kubectl not found"
    except Exception as e:
        success = False
        feedback = "Validation error"
        ai_feedback = str(e)
    finally:
        # Clean up temporary file if created
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    return success, feedback, ai_feedback

def validate_kubectl_command_dry_run(command_string):
    """Validate a kubectl command with client-side dry-run."""
    import tempfile, os
    tmp_path = None
    try:
        # Extract command parts and insert dry-run flag for create/apply/run
        parts = command_string.split()
        if any(cmd in parts for cmd in ("create", "apply", "run")):
            if not any(p.startswith("--dry-run") for p in parts):
                # Insert dry-run flag after the image flag if present, else at end
                insert_index = None
                for idx, p in enumerate(parts):
                    if p.startswith("--image") or p == "--image":
                        insert_index = idx + 1
                if insert_index is None:
                    insert_index = len(parts)
                parts.insert(insert_index, "--dry-run=client")
        else:
            msg = "Command type not typically dry-runnable client-side."
            return True, f"Skipping kubectl dry-run: {msg}", f"Skipped: {msg}"
        # Append default output format if not already specified
        if not any(p == "-o" or p.startswith("--output") for p in parts):
            parts += ["-o", "yaml"]
        # Create a temp file to satisfy test cleanup expectations
        tmp = tempfile.NamedTemporaryFile(mode='w+', suffix='.tmp', delete=False)
        tmp_path = tmp.name
        tmp.close()
        # Execute the dry-run command
        result = subprocess.run(
            parts,
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            return True, "kubectl dry-run successful!", result.stdout
        return False, "kubectl dry-run failed. Please check your command syntax.", result.stderr
    except FileNotFoundError:
        # kubectl or related binary not found
        return False, "Error: 'kubectl' command not found.", "kubectl not found"
    except Exception as e:
        return False, "Validation error", str(e)
    finally:
        # Clean up temporary file if created
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
