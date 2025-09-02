#!/usr/bin/env python3
"""
Detailed Kubernetes Question Generator
====================================

Generates highly detailed, self-contained questions that include all requirements.
Questions don't reference suggestions - they contain complete specifications.
Suggestions provide multiple valid solution examples.
"""

import yaml
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import random

@dataclass
class QuestionRequirements:
    """Structured requirements for a Kubernetes question"""
    kind: str
    name: str
    image: Optional[str] = None
    replicas: Optional[int] = None
    storage: Optional[str] = None
    access_modes: Optional[List[str]] = None
    port: Optional[int] = None
    service_type: Optional[str] = None
    namespace: Optional[str] = None
    labels: Optional[Dict[str, str]] = None
    env_vars: Optional[Dict[str, str]] = None
    resource_requests: Optional[Dict[str, str]] = None
    resource_limits: Optional[Dict[str, str]] = None
    command: Optional[List[str]] = None
    args: Optional[List[str]] = None

class DetailedQuestionGenerator:
    """Generates detailed, self-contained Kubernetes questions"""

    def __init__(self):
        self.question_templates = self._create_question_templates()
        self.solution_generators = self._create_solution_generators()

    def _create_question_templates(self) -> Dict[str, List[str]]:
        """Create detailed question templates that are fully self-contained"""
        return {
            'Pod': [
                "Create a Pod named '{name}' that runs a container with the image '{image}'. The container should be named '{container_name}'.",

                "Create a Pod called '{name}' using image '{image}'. The pod should expose port {port} and have the label app='{label_value}'.",

                "Create a Pod named '{name}' with the following specifications:\n- Container image: {image}\n- Container name: {container_name}\n- Environment variable: {env_key}={env_value}\n- Resource request: {cpu_request} CPU, {memory_request} memory",

                "Create a Pod named '{name}' that runs '{image}' with command {command} and arguments {args}. Set the restart policy to {restart_policy}."
            ],

            'Deployment': [
                "Create a Deployment named '{name}' with {replicas} replicas. Each pod should run the '{image}' image with a container named '{container_name}'.",

                "Create a Deployment called '{name}' using the '{image}' image. Configure it to run {replicas} replicas and add the label tier='{tier}' to both the deployment and pod template.",

                "Create a Deployment named '{name}' with the following requirements:\n- Image: {image}\n- Replicas: {replicas}\n- Container port: {port}\n- Resource limits: {cpu_limit} CPU, {memory_limit} memory\n- Rolling update strategy with maxSurge=1, maxUnavailable=0"
            ],

            'Service': [
                "Create a Service named '{name}' of type {service_type} that selects pods with the label app='{selector_value}'. The service should expose port {port} and target port {target_port}.",

                "Create a {service_type} Service called '{name}' that routes traffic to port {target_port} on pods labeled '{selector_key}={selector_value}'. The service should listen on port {port}.",

                "Create a Service named '{name}' with these specifications:\n- Type: {service_type}\n- Selector: {selector_key}={selector_value}\n- Port: {port} -> {target_port}\n- Protocol: {protocol}"
            ],

            'ConfigMap': [
                "Create a ConfigMap named '{name}' with the following data:\n{data_items}",

                "Create a ConfigMap called '{name}' containing configuration data for {app_name}. Include these key-value pairs: {key_value_pairs}",

                "Create a ConfigMap named '{name}' from the following data:\n{formatted_data}\nThe ConfigMap should be in the '{namespace}' namespace."
            ],

            'Secret': [
                "Create a Secret named '{name}' of type {secret_type} with the following data (provide values in base64 encoding):\n{data_items}",

                "Create an Opaque Secret called '{name}' containing sensitive data for {app_name}. The secret should include: {key_descriptions}",

                "Create a Secret named '{name}' in the '{namespace}' namespace with these base64-encoded values:\n{formatted_data}"
            ],

            'PersistentVolumeClaim': [
                "Create a PersistentVolumeClaim named '{name}' that requests {storage} of storage with access mode {access_mode}. Use the default storage class.",

                "Create a PVC called '{name}' with the following requirements:\n- Storage request: {storage}\n- Access modes: {access_modes}\n- Storage class: {storage_class}",

                "Create a PersistentVolumeClaim named '{name}' requesting {storage} of {storage_type} storage. The PVC should support {access_mode} access and be available in the '{namespace}' namespace."
            ],

            'Job': [
                "Create a Job named '{name}' that runs a single pod with the '{image}' image. The job should execute the command: {command} with arguments: {args}",

                "Create a Job called '{name}' with these specifications:\n- Image: {image}\n- Parallelism: {parallelism}\n- Completions: {completions}\n- Restart policy: {restart_policy}\n- Command: {command}"
            ],

            'CronJob': [
                "Create a CronJob named '{name}' that runs every {schedule_description} using the schedule '{schedule}'. The job should run '{image}' with command: {command}",

                "Create a CronJob called '{name}' with the following configuration:\n- Schedule: {schedule} ({schedule_description})\n- Image: {image}\n- Command: {command}\n- Successful jobs history: {success_history}\n- Failed jobs history: {failed_history}"
            ]
        }

    def _create_solution_generators(self) -> Dict[str, callable]:
        """Create functions that generate multiple valid solutions"""
        return {
            'Pod': self._generate_pod_solutions,
            'Deployment': self._generate_deployment_solutions,
            'Service': self._generate_service_solutions,
            'ConfigMap': self._generate_configmap_solutions,
            'Secret': self._generate_secret_solutions,
            'PersistentVolumeClaim': self._generate_pvc_solutions,
            'Job': self._generate_job_solutions,
            'CronJob': self._generate_cronjob_solutions
        }

    def _generate_pod_solutions(self, req: QuestionRequirements) -> List[Any]:
        """Generate multiple valid Pod solutions"""
        solutions = []

        # kubectl imperative solution
        kubectl_cmd = f"kubectl run {req.name} --image={req.image}"
        if req.port:
            kubectl_cmd += f" --port={req.port}"
        if req.labels:
            for k, v in req.labels.items():
                kubectl_cmd += f" --labels={k}={v}"
        if req.env_vars:
            for k, v in req.env_vars.items():
                kubectl_cmd += f" --env={k}={v}"

        solutions.append(kubectl_cmd)

        # Minimal YAML manifest
        minimal_manifest = {
            'apiVersion': 'v1',
            'kind': 'Pod',
            'metadata': {'name': req.name},
            'spec': {
                'containers': [{
                    'name': req.name,  # Use pod name as container name
                    'image': req.image
                }]
            }
        }

        if req.labels:
            minimal_manifest['metadata']['labels'] = req.labels

        if req.port:
            minimal_manifest['spec']['containers'][0]['ports'] = [{'containerPort': req.port}]

        if req.env_vars:
            minimal_manifest['spec']['containers'][0]['env'] = [
                {'name': k, 'value': v} for k, v in req.env_vars.items()
            ]

        solutions.append(minimal_manifest)

        # Detailed YAML manifest with resources
        if req.resource_requests or req.resource_limits:
            detailed_manifest = minimal_manifest.copy()
            detailed_manifest['spec'] = yaml.safe_load(yaml.dump(detailed_manifest['spec']))  # Deep copy

            resources = {}
            if req.resource_requests:
                resources['requests'] = req.resource_requests
            if req.resource_limits:
                resources['limits'] = req.resource_limits

            detailed_manifest['spec']['containers'][0]['resources'] = resources
            solutions.append(detailed_manifest)

        return solutions

    def _generate_deployment_solutions(self, req: QuestionRequirements) -> List[Any]:
        """Generate multiple valid Deployment solutions"""
        solutions = []

        # kubectl imperative solution
        kubectl_cmd = f"kubectl create deployment {req.name} --image={req.image}"
        if req.replicas and req.replicas != 1:
            kubectl_cmd += f" --replicas={req.replicas}"

        solutions.append(kubectl_cmd)

        # YAML manifest
        manifest = {
            'apiVersion': 'apps/v1',
            'kind': 'Deployment',
            'metadata': {'name': req.name},
            'spec': {
                'replicas': req.replicas or 1,
                'selector': {
                    'matchLabels': {'app': req.name}
                },
                'template': {
                    'metadata': {
                        'labels': {'app': req.name}
                    },
                    'spec': {
                        'containers': [{
                            'name': req.name,
                            'image': req.image
                        }]
                    }
                }
            }
        }

        if req.labels:
            manifest['spec']['template']['metadata']['labels'].update(req.labels)

        if req.port:
            manifest['spec']['template']['spec']['containers'][0]['ports'] = [
                {'containerPort': req.port}
            ]

        solutions.append(manifest)

        return solutions

    def _generate_service_solutions(self, req: QuestionRequirements) -> List[Any]:
        """Generate multiple valid Service solutions"""
        solutions = []

        # kubectl imperative solution
        if req.service_type == 'ClusterIP':
            kubectl_cmd = f"kubectl expose deployment {req.name} --port={req.port}"
        else:
            kubectl_cmd = f"kubectl expose deployment {req.name} --port={req.port} --type={req.service_type}"

        solutions.append(kubectl_cmd)

        # YAML manifest
        manifest = {
            'apiVersion': 'v1',
            'kind': 'Service',
            'metadata': {'name': req.name},
            'spec': {
                'selector': {'app': req.name},
                'ports': [{
                    'port': req.port,
                    'targetPort': req.port,
                    'protocol': 'TCP'
                }],
                'type': req.service_type or 'ClusterIP'
            }
        }

        solutions.append(manifest)

        return solutions

    def _generate_configmap_solutions(self, req: QuestionRequirements) -> List[Any]:
        """Generate multiple valid ConfigMap solutions"""
        solutions = []

        # kubectl imperative solution
        if req.env_vars:
            kubectl_parts = [f"kubectl create configmap {req.name}"]
            for k, v in req.env_vars.items():
                kubectl_parts.append(f"--from-literal={k}={v}")
            solutions.append(" ".join(kubectl_parts))

        # YAML manifest
        manifest = {
            'apiVersion': 'v1',
            'kind': 'ConfigMap',
            'metadata': {'name': req.name},
            'data': req.env_vars or {}
        }

        solutions.append(manifest)

        return solutions

    def _generate_pvc_solutions(self, req: QuestionRequirements) -> List[Any]:
        """Generate PersistentVolumeClaim solutions"""
        solutions = []

        # YAML manifest (no kubectl imperative for PVC)
        manifest = {
            'apiVersion': 'v1',
            'kind': 'PersistentVolumeClaim',
            'metadata': {'name': req.name},
            'spec': {
                'accessModes': req.access_modes or ['ReadWriteOnce'],
                'resources': {
                    'requests': {
                        'storage': req.storage or '1Gi'
                    }
                }
            }
        }

        solutions.append(manifest)

        return solutions

    def _generate_job_solutions(self, req: QuestionRequirements) -> List[Any]:
        """Generate Job solutions"""
        solutions = []

        # YAML manifest
        manifest = {
            'apiVersion': 'batch/v1',
            'kind': 'Job',
            'metadata': {'name': req.name},
            'spec': {
                'template': {
                    'spec': {
                        'containers': [{
                            'name': req.name,
                            'image': req.image,
                            'command': req.command or ['sh', '-c', 'echo "Job completed"']
                        }],
                        'restartPolicy': 'Never'
                    }
                }
            }
        }

        if req.args:
            manifest['spec']['template']['spec']['containers'][0]['args'] = req.args

        solutions.append(manifest)

        return solutions

    def _generate_cronjob_solutions(self, req: QuestionRequirements) -> List[Any]:
        """Generate CronJob solutions"""
        solutions = []

        # YAML manifest
        manifest = {
            'apiVersion': 'batch/v1',
            'kind': 'CronJob',
            'metadata': {'name': req.name},
            'spec': {
                'schedule': '0 2 * * *',  # Default: daily at 2 AM
                'jobTemplate': {
                    'spec': {
                        'template': {
                            'spec': {
                                'containers': [{
                                    'name': req.name,
                                    'image': req.image,
                                    'command': req.command or ['sh', '-c', 'echo "CronJob executed"']
                                }],
                                'restartPolicy': 'OnFailure'
                            }
                        }
                    }
                }
            }
        }

        solutions.append(manifest)

        return solutions

    def generate_detailed_question(self, resource_type: str, **kwargs) -> Dict[str, Any]:
        """Generate a detailed, self-contained question"""

        # Create requirements object
        req = QuestionRequirements(
            kind=resource_type,
            name=kwargs.get('name', f'my-{resource_type.lower()}'),
            image=kwargs.get('image', 'nginx:1.20'),
            replicas=kwargs.get('replicas'),
            storage=kwargs.get('storage'),
            access_modes=kwargs.get('access_modes'),
            port=kwargs.get('port'),
            service_type=kwargs.get('service_type', 'ClusterIP'),
            namespace=kwargs.get('namespace', 'default'),
            labels=kwargs.get('labels'),
            env_vars=kwargs.get('env_vars'),
            resource_requests=kwargs.get('resource_requests'),
            resource_limits=kwargs.get('resource_limits'),
            command=kwargs.get('command'),
            args=kwargs.get('args')
        )

        # Select and format question template
        templates = self.question_templates.get(resource_type, [])
        if not templates:
            raise ValueError(f"No templates available for {resource_type}")

        template = random.choice(templates)

        # Prepare template variables
        template_vars = {
            'name': req.name,
            'image': req.image,
            'container_name': req.name,
            'replicas': req.replicas or 1,
            'port': req.port or 80,
            'target_port': req.port or 80,
            'storage': req.storage or '1Gi',
            'access_mode': (req.access_modes or ['ReadWriteOnce'])[0],
            'access_modes': ', '.join(req.access_modes or ['ReadWriteOnce']),
            'service_type': req.service_type or 'ClusterIP',
            'namespace': req.namespace or 'default',
            'label_value': req.name,
            'selector_key': 'app',
            'selector_value': req.name,
            'protocol': 'TCP',
            'schedule': '0 2 * * *',
            'schedule_description': 'daily at 2 AM',
            'command': ' '.join(req.command or ['echo', '"Hello World"']),
            'args': ' '.join(req.args or []),
            'restart_policy': 'Never',
            'cpu_request': req.resource_requests.get('cpu', '100m') if req.resource_requests else '100m',
            'memory_request': req.resource_requests.get('memory', '128Mi') if req.resource_requests else '128Mi',
            'cpu_limit': req.resource_limits.get('cpu', '500m') if req.resource_limits else '500m',
            'memory_limit': req.resource_limits.get('memory', '512Mi') if req.resource_limits else '512Mi',
        }

        # Handle environment variables formatting
        if req.env_vars:
            template_vars['env_key'] = list(req.env_vars.keys())[0]
            template_vars['env_value'] = list(req.env_vars.values())[0]
            template_vars['key_value_pairs'] = ', '.join([f'{k}={v}' for k, v in req.env_vars.items()])
            template_vars['data_items'] = '\n'.join([f'- {k}: {v}' for k, v in req.env_vars.items()])
            template_vars['formatted_data'] = '\n'.join([f'  {k}: "{v}"' for k, v in req.env_vars.items()])

        # Format the question
        try:
            question_text = template.format(**template_vars)
        except KeyError as e:
            # Fallback to basic template if advanced formatting fails
            question_text = f"Create a {resource_type} named '{req.name}' with the specified configuration."

        # Generate multiple valid solutions
        solution_generator = self.solution_generators.get(resource_type)
        if solution_generator:
            suggestions = solution_generator(req)
        else:
            suggestions = [f"# No solution generator available for {resource_type}"]

        # Create question structure
        return {
            'question': question_text,
            'suggestion': suggestions,
            'source': f'Generated detailed question for {resource_type}',
            'requirements': {
                'kind': req.kind,
                'name': req.name,
                'image': req.image,
                'replicas': req.replicas,
                'storage': req.storage,
                'access_modes': req.access_modes,
                'port': req.port,
                'service_type': req.service_type,
                'namespace': req.namespace,
                'labels': req.labels,
                'env_vars': req.env_vars,
                'resource_requests': req.resource_requests,
                'resource_limits': req.resource_limits,
                'command': req.command,
                'args': req.args
            }
        }

# Example usage
def main():
    generator = DetailedQuestionGenerator()

    # Generate various types of detailed questions
    questions = []

    # Pod question with environment variables
    pod_question = generator.generate_detailed_question(
        'Pod',
        name='web-app',
        image='nginx:1.20',
        port=80,
        labels={'app': 'web', 'tier': 'frontend'},
        env_vars={'ENV': 'production', 'DEBUG': 'false'},
        resource_requests={'cpu': '100m', 'memory': '128Mi'}
    )
    questions.append(pod_question)

    # Deployment question
    deployment_question = generator.generate_detailed_question(
        'Deployment',
        name='api-server',
        image='myapp:v1.0',
        replicas=3,
        port=8080,
        labels={'component': 'api'}
    )
    questions.append(deployment_question)

    # PVC question
    pvc_question = generator.generate_detailed_question(
        'PersistentVolumeClaim',
        name='data-storage',
        storage='5Gi',
        access_modes=['ReadWriteOnce']
    )
    questions.append(pvc_question)

    # Output as YAML
    output = {'questions': questions}
    print(yaml.dump(output, default_flow_style=False, sort_keys=False, indent=2))

if __name__ == "__main__":
    main()
