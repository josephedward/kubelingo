#!/usr/bin/env python3
"""
generate_jsonnet_question.py

Demonstrates reliable question generation via Jsonnet templates.

This standalone script uses the kubelingo.jsonnet_generator to render
a CKAD-style question for a specified topic from a Jsonnet template,
ensuring predictable, schema-correct output.
"""
import sys
import yaml
try:
    import kubelingo.jsonnet_generator as jsonnet_generator
except ModuleNotFoundError:
    print("No Jsonnet template found or python-jsonnet library missing.")
    sys.exit(1)

def generate_example_question():
    """
    Generate and print a question for the 'image_registry_use' topic
    using external variables for registry and pullSecret.
    """
    topic = "image_registry_use"
    ext_vars = {
        "registry": "custom-registry.io",
        "pullSecret": "my-custom-secret",
    }
    print(f"Generating question for topic: {topic} with external variables: {ext_vars}\n")
    # Attempt generation via Jsonnet template
    generated_question = jsonnet_generator.generate_from_jsonnet(topic, ext_vars)
    if not generated_question:
        print("No Jsonnet template found or python-jsonnet library missing.\n")
        return
    # Pretty-print the generated question dict
    print("--- Generated Question ---")
    try:
        print(yaml.safe_dump(generated_question, indent=2, sort_keys=False))
    except Exception:
        print(generated_question)

if __name__ == "__main__":
    generate_example_question()