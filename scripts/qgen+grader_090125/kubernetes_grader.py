#!/usr/bin/env python3
"""
Kubernetes Quiz Grading System
============================

Handles multiple valid answers for Kubernetes questions:
- kubectl commands (imperative)
- YAML manifests (declarative) 
- Various formatting styles
- Optional vs required fields

Uses a rule-based validation system to check if submissions meet requirements.
"""

import yaml
import re
import json
from typing import Dict, List, Any, Union, Optional
from dataclasses import dataclass
from enum import Enum

class AnswerType(Enum):
    KUBECTL_COMMAND = "kubectl"
    YAML_MANIFEST = "yaml"
    MIXED = "mixed"

@dataclass
class ValidationRule:
    """Defines what makes an answer correct"""
    field_path: str          # e.g., "metadata.name" or "spec.containers[0].image"
    expected_value: Any      # Expected value or pattern
    required: bool = True    # Whether this field is mandatory
    pattern: Optional[str] = None  # Regex pattern for flexible matching

class KubernetesAnswerValidator:
    """Validates Kubernetes answers against requirements"""

    def __init__(self):
        self.kubectl_patterns = {
            'run': r'kubectl\s+run\s+(?P<name>\S+)\s+--image=(?P<image>\S+)',
            'create_deployment': r'kubectl\s+create\s+deployment\s+(?P<name>\S+)\s+--image=(?P<image>\S+)',
            'expose': r'kubectl\s+expose\s+(?P<resource>\w+)\s+(?P<name>\S+)\s+--port=(?P<port>\d+)',
            'scale': r'kubectl\s+scale\s+(?P<resource>\w+)\s+(?P<name>\S+)\s+--replicas=(?P<replicas>\d+)',
            'get': r'kubectl\s+get\s+(?P<resource>\w+)',
            'describe': r'kubectl\s+describe\s+(?P<resource>\w+)\s+(?P<name>\S+)?',
        }

    def create_validation_rules(self, requirements: Dict[str, Any]) -> List[ValidationRule]:
        """Create validation rules from question requirements"""
        rules = []

        # Required fields based on resource type
        if requirements.get('kind'):
            rules.append(ValidationRule('kind', requirements['kind'], True))
            rules.append(ValidationRule('apiVersion', None, True))  # Any apiVersion is acceptable

        if requirements.get('name'):
            rules.append(ValidationRule('metadata.name', requirements['name'], True))

        # Container specifications
        if requirements.get('image'):
            rules.append(ValidationRule('spec.containers[0].image', requirements['image'], True))

        if requirements.get('replicas'):
            rules.append(ValidationRule('spec.replicas', requirements['replicas'], True))

        # Storage requirements
        if requirements.get('storage'):
            rules.append(ValidationRule('spec.resources.requests.storage', requirements['storage'], True))

        if requirements.get('access_modes'):
            rules.append(ValidationRule('spec.accessModes', requirements['access_modes'], True))

        # Service requirements
        if requirements.get('port'):
            rules.append(ValidationRule('spec.ports[0].port', requirements['port'], True))

        if requirements.get('service_type'):
            rules.append(ValidationRule('spec.type', requirements['service_type'], True))

        # Optional fields that can be present but aren't required
        optional_fields = ['metadata.labels', 'spec.containers[0].ports', 'spec.containers[0].resources']
        for field in optional_fields:
            rules.append(ValidationRule(field, None, False))  # Any value acceptable

        return rules

    def validate_kubectl_command(self, command: str, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a kubectl command against requirements"""
        result = {
            'valid': False,
            'type': 'kubectl_command',
            'extracted_values': {},
            'errors': [],
            'warnings': []
        }

        command = command.strip()

        # Try to match against known patterns
        for pattern_name, pattern in self.kubectl_patterns.items():
            match = re.match(pattern, command)
            if match:
                result['extracted_values'] = match.groupdict()
                result['command_type'] = pattern_name
                break

        if not result['extracted_values']:
            result['errors'].append(f"Unrecognized kubectl command format: {command}")
            return result

        # Validate extracted values against requirements
        extracted = result['extracted_values']

        # Check name
        if requirements.get('name') and extracted.get('name') != requirements['name']:
            result['errors'].append(f"Name mismatch: expected '{requirements['name']}', got '{extracted.get('name')}'")

        # Check image
        if requirements.get('image') and extracted.get('image') != requirements['image']:
            result['errors'].append(f"Image mismatch: expected '{requirements['image']}', got '{extracted.get('image')}'")

        # Check resource type for kubectl get/describe
        if requirements.get('resource') and extracted.get('resource') != requirements['resource']:
            result['errors'].append(f"Resource mismatch: expected '{requirements['resource']}', got '{extracted.get('resource')}'")

        result['valid'] = len(result['errors']) == 0
        return result

    def get_nested_value(self, data: Dict, path: str) -> Any:
        """Get nested value from dict using dot notation (e.g., 'spec.containers[0].image')"""
        try:
            current = data
            parts = path.split('.')

            for part in parts:
                # Handle array indexing like containers[0]
                if '[' in part and ']' in part:
                    key = part.split('[')[0]
                    index = int(part.split('[')[1].split(']')[0])
                    current = current[key][index]
                else:
                    current = current[part]

            return current
        except (KeyError, IndexError, TypeError):
            return None

    def validate_yaml_manifest(self, manifest: Dict[str, Any], requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a YAML manifest against requirements"""
        result = {
            'valid': False,
            'type': 'yaml_manifest',
            'extracted_values': {},
            'errors': [],
            'warnings': []
        }

        rules = self.create_validation_rules(requirements)

        for rule in rules:
            value = self.get_nested_value(manifest, rule.field_path)

            if rule.required and value is None:
                result['errors'].append(f"Required field missing: {rule.field_path}")
                continue

            if value is not None:
                result['extracted_values'][rule.field_path] = value

                # Validate specific values
                if rule.expected_value is not None:
                    if isinstance(rule.expected_value, list):
                        if value not in rule.expected_value and set(value) != set(rule.expected_value):
                            result['errors'].append(f"Invalid value for {rule.field_path}: expected one of {rule.expected_value}, got {value}")
                    elif value != rule.expected_value:
                        result['errors'].append(f"Invalid value for {rule.field_path}: expected {rule.expected_value}, got {value}")

        result['valid'] = len(result['errors']) == 0
        return result

    def validate_answer(self, answer: Union[str, Dict, List], requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Main validation function - handles any answer type"""

        # Handle string answers (kubectl commands)
        if isinstance(answer, str):
            answer = answer.strip()
            if answer.startswith('kubectl'):
                return self.validate_kubectl_command(answer, requirements)
            else:
                # Try to parse as YAML
                try:
                    parsed = yaml.safe_load(answer)
                    if isinstance(parsed, dict):
                        return self.validate_yaml_manifest(parsed, requirements)
                except yaml.YAMLError:
                    pass

                return {
                    'valid': False,
                    'type': 'unknown',
                    'errors': ['Unable to parse answer as kubectl command or YAML manifest'],
                    'warnings': []
                }

        # Handle dict answers (parsed YAML manifests)
        elif isinstance(answer, dict):
            return self.validate_yaml_manifest(answer, requirements)

        # Handle list answers (multiple manifests)
        elif isinstance(answer, list):
            if len(answer) == 1:
                return self.validate_yaml_manifest(answer[0], requirements)
            else:
                return {
                    'valid': False,
                    'type': 'multiple_manifests',
                    'errors': ['Multi-manifest answers not yet supported'],
                    'warnings': []
                }

        else:
            return {
                'valid': False,
                'type': 'unknown',
                'errors': [f'Unsupported answer type: {type(answer)}'],
                'warnings': []
            }

# Example usage and test cases
def main():
    validator = KubernetesAnswerValidator()

    # Example question requirements
    pod_requirements = {
        'kind': 'Pod',
        'name': 'nginx',
        'image': 'nginx:1.20'
    }

    pvc_requirements = {
        'kind': 'PersistentVolumeClaim',
        'name': 'my-pvc',
        'storage': '1Gi',
        'access_modes': ['ReadWriteOnce']
    }

    # Test various answers
    test_answers = [
        # kubectl command
        'kubectl run nginx --image=nginx:1.20',

        # Minimal YAML
        {
            'apiVersion': 'v1',
            'kind': 'Pod',
            'metadata': {'name': 'nginx'},
            'spec': {'containers': [{'name': 'nginx', 'image': 'nginx:1.20'}]}
        },

        # Detailed YAML with extra fields
        {
            'apiVersion': 'v1',
            'kind': 'Pod',
            'metadata': {
                'name': 'nginx',
                'labels': {'app': 'nginx', 'version': 'v1'}
            },
            'spec': {
                'containers': [{
                    'name': 'nginx',
                    'image': 'nginx:1.20',
                    'ports': [{'containerPort': 80}],
                    'resources': {
                        'requests': {'cpu': '100m', 'memory': '128Mi'},
                        'limits': {'cpu': '500m', 'memory': '512Mi'}
                    }
                }]
            }
        },

        # Wrong image
        {
            'apiVersion': 'v1',
            'kind': 'Pod', 
            'metadata': {'name': 'nginx'},
            'spec': {'containers': [{'name': 'nginx', 'image': 'nginx:1.19'}]}
        }
    ]

    print("=== Testing Pod Question Validation ===")
    print("Requirements:", pod_requirements)
    print()

    for i, answer in enumerate(test_answers, 1):
        print(f"Test {i}:")
        if isinstance(answer, str):
            print(f"Answer: {answer}")
        else:
            print(f"Answer: {answer.get('kind', 'Unknown')} manifest")

        result = validator.validate_answer(answer, pod_requirements)
        print(f"Valid: {result['valid']}")
        if result['errors']:
            print(f"Errors: {result['errors']}")
        if result['warnings']:
            print(f"Warnings: {result['warnings']}")
        print()

if __name__ == "__main__":
    main()
