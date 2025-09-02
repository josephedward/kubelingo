import yaml
import subprocess
import json
import requests
import sys
import argparse

# Static validators (assume installed)
STATIC_TOOLS = [
    {"name": "kubeconform", "cmd": ["kubeconform", "-strict"]},
    {"name": "kube-score", "cmd": ["kube-score", "score"]},
    {"name": "kube-linter", "cmd": ["kube-linter", "lint"]}
]

# LLM API config (replace with your API, e.g., https://api.x.ai/v1/chat/completions for Grok)
LLM_API_URL = "https://api.openai.com/v1/chat/completions"  # Or xAI's endpoint
LLM_API_KEY = "your-api-key-here"
LLM_MODEL = "gpt-4o"  # Or "grok-4"

def parse_args():
    parser = argparse.ArgumentParser(description="Kubernetes Manifest Grader")
    parser.add_argument("--manifest", required=True, help="Path to YAML manifest or string")
    parser.add_argument("--commands", default="", help="kubectl commands as string")
    parser.add_argument("--goal", required=True, help="Desired outcome/goal")
    return parser.parse_args()

def normalize_yaml(manifest_str):
    """Parse and normalize YAML (fixes indentation, etc.)"""
    try:
        data = yaml.safe_load(manifest_str)
        return yaml.dump(data, sort_keys=False)  # Re-dump with consistent formatting
    except yaml.YAMLError as e:
        return None, str(e)

def run_static_checks(manifest_str):
    """Run static validators via subprocess"""
    results = {}
    with open("temp.yaml", "w") as f:
        f.write(manifest_str)
    for tool in STATIC_TOOLS:
        try:
            output = subprocess.check_output(tool["cmd"] + ["temp.yaml"], stderr=subprocess.STDOUT).decode()
            results[tool["name"]] = {"status": "pass", "output": output}
        except subprocess.CalledProcessError as e:
            results[tool["name"]] = {"status": "fail", "output": e.output.decode()}
    return results

def ai_evaluate(manifest_str, commands, goal, static_results):
    """Call LLM for semantic grading"""
    prompt = f"""
    Evaluate this Kubernetes manifest and commands relative to the goal: '{goal}'.
    Manifest (normalized): {manifest_str}
    Commands: {commands}
    Static check results: {json.dumps(static_results)}
    
    Consider:
    - Aliases/equivalents (e.g., similar fields or structures).
    - Indentation/variations: Ignore minor formatting.
    - Effectiveness/simplicity: Score how well it achieves the goal without overcomplication.
    
    Output JSON: {{
        "score": 0-100,
        "explanation": "Detailed reasoning",
        "issues": ["list of problems"],
        "suggestions": ["list of fixes"],
        "rewritten_manifest": "Optional improved YAML"
    }}
    """
    headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}
    data = {
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}]
    }
    response = requests.post(LLM_API_URL, headers=headers, json=data)
    if response.status_code == 200:
        return json.loads(response.json()["choices"][0]["message"]["content"])
    else:
        return {"error": response.text}

def main():
    args = parse_args()
    with open(args.manifest, "r") if not args.manifest.startswith("{") else lambda: args.manifest as f:  # Handle file or string
        manifest_str = f.read() if hasattr(f, "read") else f()
    normalized, error = normalize_yaml(manifest_str)
    if error:
        print(json.dumps({"error": f"Invalid YAML: {error}"}))
        sys.exit(1)
    
    static_results = run_static_checks(normalized)
    ai_result = ai_evaluate(normalized, args.commands, args.goal, static_results)
    
    overall = {
        "static": static_results,
        "ai": ai_result,
        "final_score": ai_result.get("score", 0) if "error" not in ai_result else 0
    }
    print(json.dumps(overall, indent=2))

if __name__ == "__main__":
    main()