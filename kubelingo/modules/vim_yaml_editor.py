#!/usr/bin/env python3
"""
modules/vim_yaml_editor.py: Interactive Vim YAML editing and validation for kubelingo
"""
import os
import subprocess
import difflib
import tempfile
try:
    import yaml
except ImportError:
    yaml = None

class VimYamlEditor:
    """
    Provides functionality to create, edit, and validate Kubernetes YAML manifests
    interactively using Vim.
    """
    def __init__(self):
        pass

    def create_yaml_exercise(self, exercise_type, template_data=None):
        """Creates a YAML exercise template for a given resource type."""
        exercises = {
            "pod": self._pod_exercise,
            "configmap": self._configmap_exercise,
            "deployment": self._deployment_exercise,
            "service": self._service_exercise,
            "secret": self._secret_exercise
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
    def _deployment_exercise(self, data):
        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": data.get("name", "example-deployment")},
            "spec": {
                "replicas": data.get("replicas", 1),
                "selector": {"matchLabels": data.get("selector", {"app": "example"})},
                "template": {
                    "metadata": {"labels": data.get("selector", {"app": "example"})},
                    "spec": {"containers": [{
                        "name": data.get("container_name", "example"),
                        "image": data.get("image", "nginx:latest"),
                        "ports": data.get("ports", [{"containerPort": 80}])
                    }]}
                }
            }
        }
    def _service_exercise(self, data):
        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": data.get("name", "example-service")},
            "spec": {
                "selector": data.get("selector", {"app": "example"}),
                "ports": data.get("ports", [{"port": 80, "targetPort": 80}]),
                "type": data.get("type", "ClusterIP")
            }
        }

    def _secret_exercise(self, data):
        return {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": data.get("name", "my-secret")},
            "type": "Opaque",
            "data": data.get("data", {})
        }

    def edit_yaml_with_vim(self, yaml_content, filename="exercise.yaml"):
        """
        Opens YAML content in Vim for interactive editing.

        This method saves the provided YAML content to a temporary file and opens it
        using the editor specified by the EDITOR environment variable, defaulting to 'vim'.
        After editing, it reads the modified content, parses it as YAML, and returns
        the resulting Python object. The temporary file is deleted afterward.

        Args:
            yaml_content (str or dict): The initial YAML content, either as a raw
                                       string or a Python dictionary.
            filename (str): A suggested filename. This parameter is kept for backward
                            compatibility but is currently ignored.

        Returns:
            dict or None: The parsed YAML content as a Python dictionary, or None if
                          the editor fails to launch or the edited content is not
                          valid YAML.
        """
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
        """
        Validates basic structure of a Kubernetes YAML object.

        Args:
            yaml_content (dict): The parsed YAML content.
            expected_fields (list, optional): A list of top-level fields to check for.
                                              Defaults to ["apiVersion", "kind", "metadata"].

        Returns:
            tuple[bool, str]: A tuple containing a boolean indicating validity and a
                              human-readable message.
        """
        if not yaml_content:
            return False, "Empty YAML content"
        required = expected_fields or ["apiVersion", "kind", "metadata"]
        missing = [f for f in required if f not in yaml_content]
        if missing:
            return False, f"Missing required fields: {', '.join(missing)}"
        return True, "YAML is valid"

    def run_yaml_edit_question(self, question, index=None):
        """
        Runs a full YAML editing exercise for a single question.

        This method orchestrates the exercise by:
        1. Displaying the prompt.
        2. Opening the starting YAML in Vim for editing.
        3. Allowing multiple attempts to edit and validate the YAML.
        4. Comparing the user's final YAML with the expected solution.
        5. Providing feedback and showing the correct solution if needed.

        Args:
            question (dict): A dictionary containing the exercise details, including
                             'prompt', 'starting_yaml', and 'correct_yaml'.
            index (int, optional): The index of the question for display purposes.

        Returns:
            bool: True if the user's solution matches the expected solution (or if it
                  is structurally valid when no solution is provided), False otherwise.
        """
        prompt = question.get('prompt') or question.get('requirements', '')
        print(f"\n=== Exercise {index}: {prompt} ===")
        # Prepare initial YAML and expected solution
        starting = question.get('starting_yaml', '')
        expected_raw = question.get('correct_yaml')
        expected_obj = None
        if expected_raw is not None and yaml:
            try:
                expected_obj = yaml.safe_load(expected_raw) if isinstance(expected_raw, str) else expected_raw
            except Exception:
                expected_obj = None
        # Interactive edit loop, allow retries on failure
        success = False
        last_valid = False
        content_to_edit = starting
        while True:
            edited = self.edit_yaml_with_vim(content_to_edit, f"exercise-{index}.yaml")
            if edited is None:
                try:
                    retry = input("Could not parse YAML. Try again from last valid state? (y/N): ").strip().lower().startswith('y')
                except (EOFError, KeyboardInterrupt):
                    retry = False
                if not retry:
                    break
                continue

            content_to_edit = edited  # Update content for next retry
            # Semantic validation of required fields
            valid, msg = self.validate_yaml(edited)
            print(f"Validation: {msg}")
            last_valid = valid
            # If expected solution provided, compare
            if expected_obj is not None:
                if edited == expected_obj:
                    print("✅ Correct!")
                    success = True
                    break
                print("❌ YAML does not match expected output. Differences:")
                try:
                    exp_lines = yaml.dump(expected_obj, default_flow_style=False).splitlines()
                    edit_lines = yaml.dump(edited, default_flow_style=False).splitlines()
                    for line in difflib.unified_diff(exp_lines, edit_lines, fromfile='Expected', tofile='Your', lineterm=''):
                        print(line)
                except Exception as diff_err:
                    print(f"Error generating diff: {diff_err}")
            else:
                # No expected, use basic validation
                if valid:
                    success = True
                    break
            # Ask user to retry or skip
            try:
                retry = input("Try again? (y/N): ").strip().lower().startswith('y')
            except (EOFError, KeyboardInterrupt):
                retry = False
            if not retry:
                break
        # If expected exists and failed after retries, show expected solution
        if expected_obj is not None and not success:
            print("\nExpected solution:" )
            try:
                print(yaml.dump(expected_obj, default_flow_style=False))
            except Exception:
                print(expected_raw)
        # Return success for expected-based, else last validation status
        return success if expected_obj is not None else last_valid

    def run_progressive_yaml_exercises(self, exercises):
        """Run multi-step YAML exercise with progressive complexity."""
        if not exercises:
            print("No exercises provided.")
            return False
        current_yaml = exercises[0].get('starting_yaml', '')
        for step_idx, step in enumerate(exercises, start=1):
            print(f"\n=== Step {step_idx}: {step.get('prompt', '')} ===")
            content_to_edit = current_yaml
            while True:
                edited = self.edit_yaml_with_vim(content_to_edit, f"step-{step_idx}.yaml")
                if edited is None:
                    return False
                if 'validation_func' in step and callable(step['validation_func']):
                    valid, msg = step['validation_func'](edited)
                    print(f"Step validation: {msg}")
                    if not valid:
                        try:
                            retry = input("Fix this step? (y/N): ").strip().lower().startswith('y')
                        except (EOFError, KeyboardInterrupt):
                            retry = False
                        if retry:
                            content_to_edit = edited
                            continue
                        return False
                current_yaml = edited
                break
        return True

    def run_scenario_exercise(self, scenario):
        """Run scenario-based exercise with dynamic requirements."""
        title = scenario.get('title', '')
        print(f"\n=== Scenario: {title} ===")
        description = scenario.get('description', '')
        if description:
            print(description)
        current_yaml = scenario.get('base_template', '')
        for requirement in scenario.get('requirements', []):
            desc = requirement.get('description', '')
            print(f"\n📋 Requirement: {desc}")
            if requirement.get('hints'):
                try:
                    show_hints = input("Show hints? (y/N): ").strip().lower().startswith('y')
                except (EOFError, KeyboardInterrupt):
                    show_hints = False
                if show_hints:
                    for hint in requirement.get('hints', []):
                        print(f"💡 {hint}")
            edited = self.edit_yaml_with_vim(current_yaml)
            if edited is None:
                continue
            if self._validate_requirement(edited, requirement):
                print("✅ Requirement satisfied!")
                current_yaml = edited
            else:
                print("❌ Requirement not met. Try again.")
        return current_yaml

    def run_live_cluster_exercise(self, exercise):
        """Interactive exercise that applies to real cluster."""
        print(f"\n🚀 Live Exercise: {exercise.get('prompt', '')}")
        starting_yaml = exercise.get('starting_yaml', '')
        edited_yaml = self.edit_yaml_with_vim(starting_yaml)
        if edited_yaml is None:
            return False
        try:
            apply_choice = input("Apply to cluster? (y/N): ").strip().lower().startswith('y')
        except (EOFError, KeyboardInterrupt):
            apply_choice = False
        if apply_choice:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(edited_yaml, f)
                temp_path = f.name
            try:
                result = subprocess.run(['kubectl', 'apply', '-f', temp_path], capture_output=True, text=True)
                if result.returncode == 0:
                    print("✅ Successfully applied to cluster!")
                    if exercise.get('validation_script'):
                        self._run_validation_script(exercise['validation_script'])
                else:
                    print(f"❌ Apply failed: {result.stderr}")
            finally:
                os.unlink(temp_path)
        return True

    def create_interactive_question(self):
        """Build custom YAML exercise interactively."""
        if yaml is None:
            print("YAML library not available.")
            return None
        print("\n=== Create Custom YAML Exercise ===")
        resource_types = ["pod", "deployment", "service", "configmap", "secret"]
        print("Available resource types: " + ", ".join(resource_types))
        try:
            resource_type = input("Choose resource type: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return None
        if resource_type not in resource_types:
            print("Invalid resource type")
            return None
        requirements = []
        while True:
            try:
                req = input("Add requirement (or 'done'): ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if req.lower() == 'done':
                break
            requirements.append(req)
        template = self.create_yaml_exercise(resource_type)
        starting_yaml = yaml.dump(template, default_flow_style=False)
        exercise = {
            'prompt': f"Create a {resource_type} with: {', '.join(requirements)}",
            'starting_yaml': starting_yaml
        }
        return self.run_yaml_edit_question(exercise)

    def _validate_requirement(self, yaml_obj, requirement):
        """Internal helper to validate a single requirement."""
        if 'validation_func' in requirement and callable(requirement['validation_func']):
            valid, _ = requirement['validation_func'](yaml_obj)
            return valid
        return True

    def _run_validation_script(self, script):
        """Internal helper to run an external validation script."""
        try:
            if isinstance(script, str):
                result = subprocess.run(script, shell=True, capture_output=True, text=True)
            else:
                result = subprocess.run(script, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Validation script failed: {result.stderr}")
                return False
            print(result.stdout)
            return True
        except Exception as e:
            print(f"Error running validation script: {e}")
            return False

# ==============================================================================
# Standalone Vim Commands Quiz
# ==============================================================================

def vim_commands_quiz():
    """
    Runs a simple command-line quiz to test the user's knowledge of basic Vim commands.
    This is provided as a supplemental tool for users to refresh their Vim skills.

    Returns:
        float: The final score as a ratio of correct answers to total questions.
    """
    vim_commands = [
        {"prompt": "Enter insert mode at cursor", "answer": "i"},
        {"prompt": "Append text after cursor", "answer": "a"},
        {"prompt": "Open a new line below the current line", "answer": "o"},
        {"prompt": "Save file and quit", "answer": ":wq"},
        {"prompt": "Exit without saving changes", "answer": ":q!"},
        {"prompt": "Save file without exiting", "answer": ":w"},
        {"prompt": "Delete current line", "answer": "dd"},
        {"prompt": "Copy current line (yank)", "answer": "yy"},
        {"prompt": "Paste after cursor", "answer": "p"},
        {"prompt": "Undo last change", "answer": "u"},
        {"prompt": "Search forward for 'pattern'", "answer": "/pattern"},
        {"prompt": "Find next search occurrence", "answer": "n"},
        {"prompt": "Go to top of file", "answer": "gg"},
        {"prompt": "Go to end of file", "answer": "G"},
        {"prompt": "Go to line 10", "answer": ":10"},
    ]
    print("\n--- Basic Vim Commands Quiz ---")
    print("Test your knowledge of essential Vim commands.")
    score = 0
    for cmd in vim_commands:
        ans = input(f"\nHow do you: {cmd['prompt']}? ")
        if ans.strip() == cmd['answer']:
            print("✅ Correct!")
            score += 1
        else:
            print(f"❌ Incorrect. The correct command is: {cmd['answer']}")
    print(f"\nQuiz Complete! Your Score: {score}/{len(vim_commands)}")
    return score / len(vim_commands)
