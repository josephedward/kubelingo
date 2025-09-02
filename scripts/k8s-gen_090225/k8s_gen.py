import os
import json
import requests
import subprocess
import yaml
from difflib import unified_diff
import argparse
from dotenv import load_dotenv

# Load .env for keys
load_dotenv()

# Existing API configs (from previous script)
# ... (keep your OPENAI_API_KEY, GEMINI_API_KEY, etc.)

def parse_args():
    parser = argparse.ArgumentParser(description="AI Kubernetes Manifest Generator")
    parser.add_argument("--prompt", required=True, help="Natural language prompt for manifest")
    parser.add_argument("--backends", default="openai", help="Comma-separated: openai,gemini,grok,ollama,kubectl-ai-google,kubectl-ai-sozercan,kube-copilot,k8sgpt,kopylot")
    parser.add_argument("--flaw", default="none", help="Introduce flaw: none, missing-replicas, invalid-port, etc.")
    parser.add_argument("--compare", action="store_true", help="Compare outputs")
    return parser.parse_args()

# Existing generators (openai, gemini, grok, ollama)
# ... (keep from previous script)

def generate_with_kubectl_ai_google(prompt):
    try:
        output = subprocess.check_output(["kubectl-ai", "--quiet", prompt]).decode().strip()
        return output.split("```yaml")[1].split("```")[0].strip() if "```yaml" in output else output
    except Exception as e:
        return f"Error: {str(e)}"

def generate_with_kubectl_ai_sozercan(prompt):
    try:
        output = subprocess.check_output(["kubectl", "ai", prompt]).decode().strip()
        return output.split("```yaml")[1].split("```")[0].strip() if "```yaml" in output else output
    except Exception as e:
        return f"Error: {str(e)}"

def generate_with_kube_copilot(prompt):
    try:
        output = subprocess.check_output(["kube-copilot", "generate", "--prompt", prompt]).decode().strip()
        return output.split("```yaml")[1].split("```")[0].strip() if "```yaml" in output else output
    except Exception as e:
        return f"Error: {str(e)}"

def generate_with_k8sgpt(prompt):
    # K8sGPT is rewrite-focused; use minimal base YAML
    base_yaml = "apiVersion: v1\nkind: Pod\nmetadata:\n  name: base"
    try:
        output = subprocess.check_output(f"echo '{base_yaml}' | k8sgpt generate --prompt '{prompt}'", shell=True).decode().strip()
        return output.split("```yaml")[1].split("```")[0].strip() if "```yaml" in output else output
    except Exception as e:
        return f"Error: {str(e)}"  # Note: If no 'generate', swap to 'analyze --explain' or manual rewrite

def generate_with_kopylot(prompt):
    # KoPylot is interactive; simulate with echo (may need pexpect for full chat, but basic pipe)
    try:
        output = subprocess.check_output(f"echo '{prompt}' | kopylot chat --non-interactive", shell=True).decode().strip()  # Assumes non-interactive flag; if not, use pexpect lib
        return output.split("```yaml")[1].split("```")[0].strip() if "```yaml" in output else output
    except Exception as e:
        return f"Error: {str(e)}"

# Existing introduce_flaw, validate_yaml, score_manifest
# ... (keep from previous)

def main():
    args = parse_args()
    backends = args.backends.split(",")
    results = {}
    for backend in backends:
        try:
            generator = {
                "openai": generate_with_openai,
                "gemini": generate_with_gemini,
                "grok": generate_with_grok,
                "ollama": generate_with_ollama,
                "kubectl-ai-google": generate_with_kubectl_ai_google,
                "kubectl-ai-sozercan": generate_with_kubectl_ai_sozercan,
                "kube-copilot": generate_with_kube_copilot,
                "k8sgpt": generate_with_k8sgpt,
                "kopylot": generate_with_kopylot
            }[backend]
            raw_yaml = generator(args.prompt)
            flawed_yaml = introduce_flaw(raw_yaml, args.flaw)
            validation = validate_yaml(flawed_yaml)
            score = score_manifest(flawed_yaml, args.prompt)
            results[backend] = {"yaml": flawed_yaml, "validation": validation, "score": score}
        except KeyError:
            print(f"Backend {backend} not supported.")
    
    if args.compare:
        for i, b1 in enumerate(backends):
            for b2 in backends[i+1:]:
                diff = "\n".join(unified_diff(results.get(b1, {}).get("yaml", "").splitlines(), results.get(b2, {}).get("yaml", "").splitlines(), fromfile=b1, tofile=b2))
                results[f"diff_{b1}_{b2}"] = diff
    
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()