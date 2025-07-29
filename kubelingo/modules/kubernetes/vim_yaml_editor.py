import os
import subprocess
import tempfile
import difflib

from kubelingo.utils.validation import validate_yaml_structure
from kubelingo.utils.ui import Fore, Style, yaml


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

    def validate_yaml(self, yaml_content, expected_fields=None):
        """
        Checks for syntax and required fields (`apiVersion`, `kind`, `metadata`),
        returning (is_valid, message).
        This is a wrapper for backward compatibility.
        """
        # The expected_fields argument is ignored, as the new validation function is more comprehensive.
        if isinstance(yaml_content, dict):
            try:
                yaml_str = yaml.dump(yaml_content)
            except Exception as e:
                return False, f"Failed to dump YAML object: {e}"
        elif isinstance(yaml_content, str):
            yaml_str = yaml_content
        else:
            # Handle cases where editor returns None for empty/invalid file
            yaml_str = ""

        result = validate_yaml_structure(yaml_str)

        if result['valid']:
            message = "YAML is valid"
            if result['warnings']:
                message += f" (warnings: {', '.join(result['warnings'])})"
            return True, message
        else:
            return False, f"Invalid: {', '.join(result['errors'])}"

    def edit_yaml_with_vim(self, yaml_content, filename="exercise.yaml", prompt=None, _vim_args=None, _timeout=300):
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
            prompt (str, optional): Text to include as comments at the top of the file.
            _vim_args (list, optional): For internal testing only. A list of
                                        additional arguments to pass to Vim.
            _timeout (int, optional): The session timeout in seconds. Defaults to 300.
                                     Set to None to disable.

        Returns:
            dict or None: The parsed YAML content as a Python dictionary, or None if
                          the editor fails to launch or the edited content is not
                          valid YAML.
        """
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode='w', encoding='utf-8') as tmp:
            # If prompt is provided, include it as comment header
            if prompt:
                for line in str(prompt).splitlines():
                    tmp.write(f"# {line}\n")
                tmp.write("\n")
            # Write YAML content: raw string or dumped Python object
            if isinstance(yaml_content, str):
                tmp.write(yaml_content)
            else:
                yaml.dump(yaml_content, tmp, default_flow_style=False)
            tmp_filename = tmp.name

        try:
            # Launch editor
            editor = os.environ.get('EDITOR', 'vim')

            # Special handling for embedded pyvim editor
            if editor == 'pyvim':
                try:
                    # We assume pyvim is installed via pip
                    from pyvim.entrypoints.pyvim import run as run_pyvim
                    
                    # Run pyvim on the temporary file
                    run_pyvim(file_to_edit=tmp_filename)
                    
                    # After pyvim exits, read the content and return,
                    # letting the outer finally block handle cleanup.
                    with open(tmp_filename, 'r', encoding='utf-8') as f:
                        return yaml.safe_load(f)
                except ImportError:
                    print(f"{Fore.RED}Editor 'pyvim' is not installed.{Style.RESET_ALL}")
                    print("Please run 'pip install pyvim' to use it.")
                    return None
                except Exception as e:
                    print(f"{Fore.RED}An error occurred while running pyvim: {e}{Style.RESET_ALL}")
                    # Attempt to read the file anyway, it might have been saved before crashing
                    try:
                        with open(tmp_filename, 'r', encoding='utf-8') as f:
                            return yaml.safe_load(f)
                    except Exception:
                        return None

            vim_args = _vim_args or []
            # Separate non-script flags from script file paths (drop explicit '-S')
            flags = [arg for arg in vim_args if arg != '-S' and not os.path.isfile(arg)]
            # Scripts to be sourced after loading the file
            scripts = [arg for arg in vim_args if os.path.isfile(arg)]
            # Build command: editor, flags, file, then source scripts
            cmd = [editor] + flags + [tmp_filename]
            for script in scripts:
                cmd.extend(['-S', script])
            try:
                # Attempt to run with timeout; if the mock doesn't support timeout, retry without
                try:
                    result = subprocess.run(cmd, timeout=_timeout)
                except TypeError:
                    result = subprocess.run(cmd)
                if result.returncode != 0:
                    print(f"{Fore.YELLOW}Warning: Editor '{editor}' exited with non-zero status code ({result.returncode}).{Style.RESET_ALL}")
            except FileNotFoundError as e:
                print(f"{Fore.RED}Error launching editor '{editor}': {e}{Style.RESET_ALL}")
                print("Please ensure your EDITOR environment variable is set correctly.")
                return None
            except subprocess.TimeoutExpired:
                print(f"{Fore.RED}Editor session timed out after {_timeout} seconds.{Style.RESET_ALL}")
                return None
            except KeyboardInterrupt:
                print(f"{Fore.YELLOW}Editor session interrupted by user.{Style.RESET_ALL}")
                return None

            # Read edited content
            with open(tmp_filename, 'r', encoding='utf-8') as f:
                content = f.read()
            return yaml.safe_load(content)
        except Exception as e:
            # Catch parsing or execution errors and inform the user
            print(f"{Fore.RED}Failed to parse YAML: {e}{Style.RESET_ALL}")
            return None
        finally:
            # Clean up the temporary file
            try:
                os.unlink(tmp_filename)
            except Exception:
                pass


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
            print(f"\n=== Exercise {index}: {prompt} ===")
            edited = self.edit_yaml_with_vim(content_to_edit, f"exercise-{index}.yaml", prompt=prompt)
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
            last_valid, msg = self.validate_yaml(edited)
            print(f"Validation: {msg}")
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
                if last_valid:
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
        cancelled = False
        while True:
            try:
                req = input("Add requirement (or 'done'): ").strip()
                if req.lower() == 'done':
                    break
                requirements.append(req)
            except (EOFError, KeyboardInterrupt):
                cancelled = True
                break
        
        if cancelled:
            print("\nCustom exercise creation cancelled.")
            return None
        if not requirements:
            print("No requirements added, cancelling exercise.")
            return None
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
