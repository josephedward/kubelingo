import os
import json
import yaml
import subprocess, shutil
try:
    import _jsonnet
except ImportError:
    _jsonnet = None

# Path to Jsonnet templates directory
JSONNET_TEMPLATES = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'templates')
)

def generate_from_jsonnet(topic, ext_vars=None):
    """
    Generate a Kubernetes manifest for the given topic via a Jsonnet template.
    Falls back to an external 'jsonnet' binary if the Python binding is unavailable.
    Returns a CKAD question dict or None.
    """
    template_path = os.path.join(JSONNET_TEMPLATES, f"{topic}.jsonnet")
    if not os.path.isfile(template_path):
        return None

    ext_vars = ext_vars or {}
    json_str = None

    # 1) Try Python Jsonnet binding
    # if _jsonnet:
    #     try:
    #         json_str = _jsonnet.evaluate_file(template_path, ext_vars=ext_vars)
    #     except Exception:
    #         return None
    # else: # This else will now always execute
    # 2) Fallback to system 'jsonnet' executable
    jsonnet_bin = shutil.which('jsonnet')
    if not jsonnet_bin:
        return None
    cmd = [jsonnet_bin]
    for k, v in ext_vars.items():
        cmd.extend(['--ext-str', f"{k}={v}"])
    cmd.append(template_path)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        json_str = proc.stdout
    except Exception:
        return None

    # Parse JSON output
    try:
        manifest = json.loads(json_str)
    except Exception:
        return None

    # Convert to YAML string
    yaml_str = yaml.safe_dump(manifest, default_flow_style=False, sort_keys=False)

    # Build CKAD question dict
    return {
        'question': f"Render the `{topic}` manifest via Jsonnet template.",
        'suggestion': yaml_str,
        'solution': yaml_str,
        'source': f"template://{topic}.jsonnet",
        'rationale': f"Generated from Jsonnet template for `{topic}`.",
    }