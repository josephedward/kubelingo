#!/usr/bin/env python3
"""
modules/vim_yaml_editor.py: Interactive Vim YAML editing and validation for kubelingo
"""
import os
import subprocess
import tempfile
try:
    import yaml
except ImportError:
    yaml = None

class VimYamlEditor:
    def __init__(self):
        pass

    def create_yaml_exercise(self, exercise_type, template_data=None):
        exercises = {
            "pod": self._pod_exercise,
            "configmap": self._configmap_exercise,
            "deployment": self._deployment_exercise,
            "service": self._service_exercise
        }
        if exercise_type in exercises:
            return exercises[exercise_type](template_data or {})
        raise ValueError(f"Unknown exercise type: {exercise_type}")

    def _pod_exercise(self, data):
        template = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {"name": data.get("name", "nginx-pod"),
                         "labels": data.get("labels", {"app": "nginx"})},
            "spec": {"containers": [{
                "name": data.get("container_name", "nginx"),
                "image": data.get("image", "nginx:1.20"),
                "ports": data.get("ports", [{"containerPort": 80}])
            }]}
        }
        if data.get("env_vars"):
            template["spec"]["containers"][0]["env"] = data["env_vars"]
        if data.get("volume_mounts"):
            template["spec"]["containers"][0]["volumeMounts"] = data["volume_mounts"]
            template["spec"]["volumes"] = data.get("volumes", [])
        return template

    def _configmap_exercise(self, data):
        return {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": data.get("name", "app-config")},
            "data": data.get("data", {"database_url": "mysql://localhost:3306/app",
                                          "debug": "true"})
        }

    def edit_yaml_with_vim(self, yaml_content, filename="exercise.yaml"):
        # The filename parameter is now ignored, but kept for compatibility.
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode='w', encoding='utf-8') as tmp:
            # If yaml_content is a raw YAML string, write it directly; otherwise dump the Python object
            if isinstance(yaml_content, str):
                tmp.write(yaml_content)
            else:
                yaml.dump(yaml_content, tmp, default_flow_style=False)
            tmp_filename = tmp.name

        # Launch editor
        editor = os.environ.get('EDITOR', 'vim')
        try:
            subprocess.run([editor, tmp_filename], check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Error launching editor. Ensure EDITOR is set and available.")
            os.unlink(tmp_filename)
            return None

        # Read edited content
        try:
            with open(tmp_filename, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Failed to parse YAML: {e}")
            return None
        finally:
            os.unlink(tmp_filename)

    def validate_yaml(self, yaml_content, expected_fields=None):
        if not yaml_content:
            return False, "Empty YAML content"
        required = expected_fields or ["apiVersion", "kind", "metadata"]
        missing = [f for f in required if f not in yaml_content]
        if missing:
            return False, f"Missing required fields: {', '.join(missing)}"
        return True, "YAML is valid"

    def run_yaml_edit_question(self, question, index=None):
        prompt = question.get('prompt') or question.get('requirements', '')
        print(f"\n=== Exercise {index}: {prompt} ===")
        starting = question.get('starting_yaml', {})
        expected = question.get('correct_yaml', {})
        edited = self.edit_yaml_with_vim(starting, f"exercise-{index}.yaml")
        if edited is None:
            return False
        valid, msg = self.validate_yaml(edited)
        print(f"Validation: {msg}")
        # For full correctness, compare edited to expected
        if expected and edited == expected:
            print("✅ Correct!")
            return True
        if expected:
            print("❌ YAML does not match expected output.")
            return False
        return valid

def vim_commands_quiz():
    vim_commands = [
        {"prompt": "Enter insert mode", "answer": "i"},
        {"prompt": "Save and quit", "answer": ":wq"},
        {"prompt": "Delete current line", "answer": "dd"},
        {"prompt": "Copy current line", "answer": "yy"},
        {"prompt": "Paste after cursor", "answer": "p"},
        {"prompt": "Undo last change", "answer": "u"},
        {"prompt": "Search forward for 'pattern'", "answer": "/pattern"},
        {"prompt": "Go to line 10", "answer": ":10"},
        {"prompt": "Exit without saving", "answer": ":q!"}
    ]
    print("\n=== Vim Commands Quiz ===")
    score = 0
    for cmd in vim_commands:
        ans = input(f"\nHow do you: {cmd['prompt']}? ")
        if ans.strip() == cmd['answer']:
            print("✅ Correct!")
            score += 1
        else:
            print(f"❌ Incorrect. Answer: {cmd['answer']}")
    print(f"\nFinal Score: {score}/{len(vim_commands)}")
    return score / len(vim_commands)
