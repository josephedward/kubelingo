import sys
import os
import yaml

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))
sys.path.insert(0, project_root)

from kubelingo.question_generator import generate_more_questions

topic = "kubectl_common_operations"
example_question = {
    "question": "Create a service using the definition in example-service.yaml.",
    "suggestion": ["kubectl apply -f example-service.yaml"],
    "source": "https://kubernetes.io/docs/reference/kubectl/#examples-common-operations"
}

new_question = generate_more_questions(topic, example_question)

if new_question:
    print("\n--- Generated New Question ---")
    print(yaml.safe_dump({"questions": [new_question]}, indent=2, sort_keys=False))
else:
    print("\nFailed to generate a new question.")