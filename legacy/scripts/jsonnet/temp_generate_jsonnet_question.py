import sys
import os
import yaml

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))
sys.path.insert(0, project_root)

from kubelingo import jsonnet_generator

def generate_example_question():
    topic = "image_registry_use"
    ext_vars = {
        "registry": "custom-registry.io",
        "pullSecret": "my-custom-secret",
        "topic": topic, # Add topic to ext_vars
    }
    print(f"Generating question for topic: {topic} with external variables: {ext_vars}\n")
    
    # Add this line to print the template path
    template_path = os.path.join(jsonnet_generator.JSONNET_TEMPLATES, f"{topic}.jsonnet")
    print(f"Looking for template at: {template_path}\n")

    generated_question = jsonnet_generator.generate_from_jsonnet(topic, ext_vars)
    
    if generated_question:
        print("--- Generated Question ---")
        print(yaml.safe_dump(generated_question, indent=2, sort_keys=False))
    else:
        print("No Jsonnet template found or python-jsonnet library missing.\n")

if __name__ == "__main__":
    generate_example_question()
