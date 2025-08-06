import os
import subprocess
import tempfile
import shlex
import difflib

from kubelingo.utils.validation import validate_yaml_structure
from kubelingo.utils.ui import Fore, Style, yaml


class VimYamlEditor:
    """
    Provides functionality to create, edit, and validate Kubernetes YAML manifests
    interactively using Vim.
    """
    def create_yaml_exercise(self, exercise_type, template_data=None):
        """Creates a YAML exercise template for a given resource type."""
        data = template_data or {}
        if exercise_type == "pod":
            name = data.get("name", "nginx-pod")
            labels = data.get("labels", {"app": "nginx"})
            container_name = data.get("container_name", "nginx")
            image = data.get("image", "nginx:1.20")
            ports = data.get("ports", [{"containerPort": 80}])
            return {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {"name": name, "labels": labels},
                "spec": {"containers": [{"name": container_name, "image": image, "ports": ports}]}
            }
        raise ValueError(f"Unknown exercise type: {exercise_type}")
    
    def edit_yaml_with_vim(self, yaml_content, filename="exercise.yaml", prompt=None, _vim_args=None, _timeout=300):
        """
        Opens YAML content in Vim for interactive editing.
        After editing, parses and returns the YAML as a Python dict, or None on error.
        """
        if prompt:
            print(f"\n{Fore.CYAN}--- Task ---{Style.RESET_ALL}")
            print(prompt)
            print(f"{Fore.CYAN}------------{Style.RESET_ALL}")
            try:
                input("Press Enter to open the editor...")
            except (EOFError, KeyboardInterrupt):
                print("\nEditor launch cancelled.")
                return None

        # Write to a temporary YAML file, injecting the prompt as comments if provided
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode='w', encoding='utf-8') as tmp:
            # Inject prompt at the top of the file as comments for context
            if prompt:
                for line in prompt.splitlines():
                    tmp.write(f"# {line}\n")
                tmp.write("\n")
            # Write the YAML content
            if isinstance(yaml_content, str):
                tmp.write(yaml_content)
            else:
                yaml.dump(yaml_content, tmp, default_flow_style=False)
            tmp_filename = tmp.name
        vimrc_file = None
        try:
            editor_env = os.environ.get('EDITOR', 'vim')
            editor_list = shlex.split(editor_env)
            editor_name = os.path.basename(editor_list[0])

            vim_args = _vim_args or []
            flags = [arg for arg in vim_args if arg != '-S' and not os.path.isfile(arg)]
            scripts = [arg for arg in vim_args if os.path.isfile(arg)]

            # Base command
            cmd = editor_list + flags

            # If using Vim, provide a temp vimrc for consistent settings.
            if 'vim' in editor_name:
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.vimrc', encoding='utf-8') as f:
                    # Ensure Vim is not in 'compatible' mode and backspace works across indents, line breaks, and start of insert
                    f.write("set nocompatible\n")
                    f.write("set backspace=indent,eol,start\n")
                    # Use spaces for tabs and configure indentation
                    f.write("set expandtab\n")
                    f.write("set tabstop=2\n")
                    f.write("set shiftwidth=2\n")
                    f.write("filetype plugin indent on\n")
                    f.write("syntax on\n")
                    vimrc_file = f.name
                # More robustly construct command to ensure -u is in the right place
                cmd = [editor_list[0], '-u', vimrc_file] + editor_list[1:] + flags

            cmd.append(tmp_filename)

            for script in scripts:
                cmd.extend(['-S', script])

            used_fallback = False
            try:
                # Launch editor
                result = subprocess.run(cmd, timeout=_timeout)
            except TypeError:
                used_fallback = True
                result = subprocess.run(cmd)
            except FileNotFoundError as e:
                print(f"\033[31mError launching editor '{editor_env}': {e}\033[0m")
                return None
            except subprocess.TimeoutExpired:
                print(f"\033[31mEditor session timed out after {_timeout} seconds.\033[0m")
                return None
            except KeyboardInterrupt:
                print("\033[33mEditor session interrupted by user.\033[0m")
                return None
            # Warn on non-zero exit
            if result.returncode != 0:
                print(f"{Fore.YELLOW}Warning: Editor '{editor_name}' exited with status {result.returncode}.{Style.RESET_ALL}")
            # Read back edited content
            with open(tmp_filename, 'r', encoding='utf-8') as f:
                content = f.read()
            # Parse YAML if PyYAML is available and timeout fallback not used
            if (not used_fallback) and yaml and hasattr(yaml, 'safe_load'):
                try:
                    parsed = yaml.safe_load(content)
                except Exception as e:
                    print(f"\033[31mFailed to parse YAML: {e}\033[0m")
                    return None
                # Only accept mappings or sequences
                if not isinstance(parsed, (dict, list)):
                    print(f"\033[31mFailed to parse YAML: invalid content type {type(parsed).__name__}\033[0m")
                    return None
                return parsed
            # Fallback simple parser when PyYAML is not available
            data = {}
            for line in content.splitlines():
                s = line.split('#', 1)[0]
                if not s.strip():
                    continue
                if ':' in s:
                    k, v = s.split(':', 1)
                    data[k.strip()] = v.strip()
            return data
        finally:
            if vimrc_file:
                try:
                    os.unlink(vimrc_file)
                except Exception:
                    pass
            try:
                os.unlink(tmp_filename)
            except Exception:
                pass
    
    def run_progressive_yaml_exercises(self, steps):
        """
        Runs a multi-step YAML editing exercise.
        Each step: prompt, edit in Vim, validate via provided function.
        steps: list of dicts with 'prompt', optional 'starting_yaml', and 'validation_func'.
        Returns True if all steps pass, False on first failure.
        """
        previous = None
        for idx, step in enumerate(steps, start=1):
            prompt = step.get('prompt', '')
            content = step.get('starting_yaml') if idx == 1 else previous
            filename = f"step-{idx}.yaml"
            print(f"\n=== Step {idx}: {prompt} ===")
            result = self.edit_yaml_with_vim(content, filename, prompt=prompt)
            if result is None:
                return False
            # Validate
            validator = step.get('validation_func')
            try:
                valid, _ = validator(result)
            except Exception:
                return False
            if not valid:
                return False
            previous = result
        return True
    
    def run_yaml_edit_question(self, question, index=None):
        """
        Runs a single YAML editing exercise with retry logic.
        question should have 'prompt', 'starting_yaml', 'correct_yaml', 'explanation'.
        Returns True if the user produces expected YAML, False otherwise.
        """
        prompt = question.get('prompt', '')
        starting = question.get('starting_yaml', '')
        expected_raw = question.get('correct_yaml', '')
        try:
            expected_obj = yaml.safe_load(expected_raw) if isinstance(expected_raw, str) and yaml else None
        except Exception:
            expected_obj = None
        while True:
            print(f"\n=== Exercise {index}: {prompt} ===")
            result = self.edit_yaml_with_vim(starting, f"exercise-{index}.yaml", prompt=prompt)
            if result is None:
                return False
            # Validate YAML manifest structure (syntax and basic fields)
            try:
                raw_str = yaml.dump(result)
                validation = validate_yaml_structure(raw_str)
                # Report any errors or warnings
                for err in validation.get('errors', []):
                    print(f"{Fore.RED}YAML validation error: {err}{Style.RESET_ALL}")
                for warn in validation.get('warnings', []):
                    print(f"{Fore.YELLOW}YAML validation warning: {warn}{Style.RESET_ALL}")
            except Exception:
                # If validation fails unexpectedly, skip
                pass
            # Compare structures if possible
            is_correct = False
            if expected_obj is not None:
                is_correct = (result == expected_obj)
            else:
                is_correct = True
            if is_correct:
                print("✅ Correct!")
                return True
            # Incorrect: show message and offer retry
            print("❌ YAML does not match expected output.")
            try:
                retry = input("Try again? (y/N): ").strip().lower().startswith('y')
            except (EOFError, KeyboardInterrupt):
                retry = False
            if not retry:
                # Show expected solution
                print("Expected solution:")
                print(expected_raw)
                return False
            # Prepare for retry
            starting = result
