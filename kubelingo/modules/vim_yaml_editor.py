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
        """(Not yet implemented) Loop through each step, carry over the YAML, validate, and advance."""
        print("Progressive YAML exercises are not yet implemented.")
        return False

    def run_scenario_exercise(self, scenario):
        """(Not yet implemented) Show scenario, then for each requirement open Vim and validate."""
        print("Scenario exercises are not yet implemented.")
        return None

    def run_live_cluster_exercise(self, exercise):
        """(Not yet implemented) Open Vim, then `kubectl apply` and print success/failure."""
        print("Live cluster exercises are not yet implemented.")
        return False

    def create_interactive_question(self):
        """(Not yet implemented) Prompt your own requirements, build a template, then hand off to run_yaml_edit_question()."""
        print("Creating a custom interactive question is not yet implemented.")
        return None

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
