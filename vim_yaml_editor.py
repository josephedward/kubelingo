#!/usr/bin/env python3
"""
vim_yaml_editor.py: Interactive Vim YAML editing and validation module for kubelingo
"""
import os
import tempfile
import subprocess
import yaml
import json
from pathlib import Path

class VimYamlEditor:
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "kubelingo_yaml"
        self.temp_dir.mkdir(exist_ok=True)
        
    def create_yaml_exercise(self, exercise_type, template_data=None):
        """Create a YAML editing exercise with validation"""
        exercises = {
            "pod": self._pod_exercise,
            "configmap": self._configmap_exercise,
            "deployment": self._deployment_exercise,
            "service": self._service_exercise
        }
        
        if exercise_type in exercises:
            return exercises[exercise_type](template_data)
        else:
            raise ValueError(f"Unknown exercise type: {exercise_type}")
    
    def _pod_exercise(self, data):
        """Generate pod YAML exercise"""
        template = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": data.get("name", "nginx-pod"),
                "labels": data.get("labels", {"app": "nginx"})
            },
            "spec": {
                "containers": [{
                    "name": data.get("container_name", "nginx"),
                    "image": data.get("image", "nginx:1.20"),
                    "ports": data.get("ports", [{"containerPort": 80}])
                }]
            }
        }
        
        if data.get("env_vars"):
            template["spec"]["containers"][0]["env"] = data["env_vars"]
        if data.get("volume_mounts"):
            template["spec"]["containers"][0]["volumeMounts"] = data["volume_mounts"]
            template["spec"]["volumes"] = data.get("volumes", [])
            
        return template
    
    def _configmap_exercise(self, data):
        """Generate ConfigMap YAML exercise"""
        return {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": data.get("name", "app-config")
            },
            "data": data.get("data", {
                "database_url": "mysql://localhost:3306/app",
                "debug": "true"
            })
        }
    
    def edit_yaml_with_vim(self, yaml_content, filename="exercise.yaml"):
        """Open YAML content in Vim for editing"""
        temp_file = self.temp_dir / filename
        
        # Write initial content
        with open(temp_file, 'w') as f:
            yaml.dump(yaml_content, f, default_flow_style=False)
        
        # Open in Vim
        try:
            subprocess.run(['vim', str(temp_file)], check=True)
        except subprocess.CalledProcessError:
            print("Error opening Vim. Make sure Vim is installed.")
            return None
        except FileNotFoundError:
            print("Vim not found. Please install Vim.")
            return None
        
        # Read edited content
        try:
            with open(temp_file, 'r') as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as e:
            print(f"YAML syntax error: {e}")
            return None
    
    def validate_yaml(self, yaml_content, expected_fields=None):
        """Validate YAML structure and required fields"""
        if not yaml_content:
            return False, "Empty YAML content"
        
        required = expected_fields or ["apiVersion", "kind", "metadata"]
        missing = [field for field in required if field not in yaml_content]
        
        if missing:
            return False, f"Missing required fields: {', '.join(missing)}"
        
        return True, "YAML is valid"
    
    def _validate_yaml_semantically(self, user_yaml, correct_yaml):
        """Validate YAML by semantic comparison, not string matching"""
        try:
            user_data = yaml.safe_load(user_yaml)
            correct_data = yaml.safe_load(correct_yaml)
            return self._compare_kubernetes_objects(user_data, correct_data)
        except yaml.YAMLError as e:
            return {
                'valid': False,
                'error': f'YAML syntax error: {e}',
                'hints': 'Check your YAML syntax - indentation, colons, dashes'
            }
    
    def run_interactive_exercise(self, exercise_type, requirements):
        """Run a complete interactive YAML editing exercise"""
        print(f"\n=== Vim YAML Exercise: {exercise_type.title()} ===")
        print(f"Requirements: {requirements}")
        print("\nPress Enter to start editing in Vim...")
        input()
        
        # Generate initial template
        template_data = self._parse_requirements(requirements)
        yaml_template = self.create_yaml_exercise(exercise_type, template_data)
        
        # Edit in Vim
        edited_yaml = self.edit_yaml_with_vim(yaml_template, f"{exercise_type}-exercise.yaml")
        
        if edited_yaml:
            # Validate
            is_valid, message = self.validate_yaml(edited_yaml, template_data.get("required_fields"))
            print(f"\nValidation: {message}")
            
            if is_valid:
                print("✅ Exercise completed successfully!")
                return True
            else:
                print("❌ Please fix the issues and try again.")
                return False
        
        return False
    
    def _parse_requirements(self, requirements):
        """Parse exercise requirements into template data"""
        # Simple parsing - can be enhanced
        data = {}
        if "name:" in requirements:
            data["name"] = requirements.split("name:")[1].split()[0]
        if "image:" in requirements:
            data["image"] = requirements.split("image:")[1].split()[0]
        return data

def vim_commands_quiz():
    """Interactive Vim commands quiz"""
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
        user_answer = input(f"\nHow do you: {cmd['prompt']}? ")
        if user_answer.strip() == cmd['answer']:
            print("✅ Correct!")
            score += 1
        else:
            print(f"❌ Incorrect. Answer: {cmd['answer']}")
    
    print(f"\nFinal Score: {score}/{len(vim_commands)}")
    return score / len(vim_commands)

if __name__ == "__main__":
    editor = VimYamlEditor()
    
    # Example usage
    print("Kubelingo Vim YAML Editor")
    print("1. Pod Exercise")
    print("2. ConfigMap Exercise") 
    print("3. Vim Commands Quiz")
    
    choice = input("\nSelect option (1-3): ")
    
    if choice == "1":
        editor.run_interactive_exercise("pod", "name: nginx-app image: nginx:1.20")
    elif choice == "2":
        editor.run_interactive_exercise("configmap", "name: app-settings")
    elif choice == "3":
        vim_commands_quiz()
