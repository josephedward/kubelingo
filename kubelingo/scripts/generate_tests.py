
import os

test_file_content = """
import pytest
"""

providers = ["openai", "gemini", "openrouter", "perplexity"]
question_types = ["vocab", "true_false", "mcq", "commands", "manifests"]
subjects = [
    'Api Discovery Docs', 'App Configuration', 'Commands Args Env', 'Configmap', 'Core Workloads',
    'Deployment', 'Helm Basics', 'Image Registry Use', 'Imperative Vs Declarative', 'Ingress Http Routing',
    'Jobs Cronjobs', 'Kubectl Common Operations', 'Kubectl Operations', 'Labels Annotations Selectors',
    'Linux Commands Syntax', 'Logging', 'Namespaces Contexts', 'Networking Utilities',
    'Observability Troubleshooting', 'Persistence', 'Pod Design Patterns', 'Probes Health',
    'Resource Management', 'Resource Reference', 'Scheduling Hints', 'Security Basics',
    'Service Accounts In Apps', 'Services', 'RBAC', 'Monitoring', 'Troubleshooting',
    'Pod', 'Service', 'Configmap', 'Secret', 'PVC', 'Job'
]

def slugify(text):
    return text.lower().replace(' ', '_').replace('/', '_')

for provider in providers:
    for question_type in question_types:
        for subject in subjects:
            subject_slug = slugify(subject)
            test_file_content += f'''
def test_{provider}_{question_type}_{subject_slug}():
    # TODO: Implement test for provider {provider}, question type {question_type}, and subject {subject}
    pass
'''

with open("tests/test_ai_generation.py", "w") as f:
    f.write(test_file_content)
