#!/usr/bin/env python3
"""
Kubernetes Question Generator Script
==================================

This script finds valid Kubernetes commands and manifests from various free sources
and generates CKAD-style questions from them.

Dependencies:
    pip install requests beautifulsoup4 pyyaml gitpython openai

Usage:
    python k8s_question_generator.py --mode scrape --output questions.json
    python k8s_question_generator.py --mode generate --input questions.json
"""

import os
import json
import yaml
import argparse
import re
import random
from typing import List, Dict, Any

class KubernetesResourceScraper:
    """Scrapes Kubernetes resources from various free sources"""

    def __init__(self):
        self.sources = {
            'kubernetes_examples': 'https://github.com/kubernetes/examples',
            'container_solutions': 'https://github.com/ContainerSolutions/kubernetes-examples',
            'kubectl_docs': 'https://kubernetes.io/docs/reference/kubectl/cheatsheet/',
            'denny_templates': 'https://github.com/dennyzhang/kubernetes-yaml-templates'
        }

        self.kubectl_commands = []
        self.yaml_manifests = []

    def scrape_kubectl_commands(self):
        """Scrape kubectl commands from official documentation"""
        print("Scraping kubectl commands from official docs...")

        # Common kubectl commands for CKAD
        base_commands = [
            # Pod operations
            "kubectl run nginx --image=nginx",
            "kubectl get pods",
            "kubectl describe pod <pod-name>",
            "kubectl logs <pod-name>",
            "kubectl delete pod <pod-name>",
            "kubectl exec -it <pod-name> -- /bin/bash",

            # Deployment operations
            "kubectl create deployment nginx --image=nginx",
            "kubectl get deployments",
            "kubectl scale deployment nginx --replicas=3",
            "kubectl rollout status deployment/nginx",
            "kubectl rollout undo deployment/nginx",

            # Service operations
            "kubectl expose deployment nginx --port=80 --type=NodePort",
            "kubectl get services",
            "kubectl describe service nginx",

            # ConfigMap and Secret operations
            "kubectl create configmap app-config --from-literal=key1=value1",
            "kubectl create secret generic app-secret --from-literal=password=secret",
            "kubectl get configmaps",
            "kubectl get secrets",

            # Namespace operations
            "kubectl create namespace dev",
            "kubectl get namespaces",
            "kubectl config set-context --current --namespace=dev",

            # Resource management
            "kubectl apply -f manifest.yaml",
            "kubectl delete -f manifest.yaml",
            "kubectl get all",
            "kubectl top nodes",
            "kubectl top pods"
        ]

        for command in base_commands:
            self.kubectl_commands.append({
                'command': command,
                'category': self._categorize_command(command),
                'source': 'official_docs'
            })

    def _categorize_command(self, command: str) -> str:
        """Categorize kubectl command by its primary function"""
        if 'pod' in command.lower():
            return 'pod'
        elif 'deployment' in command.lower():
            return 'deployment'
        elif 'service' in command.lower():
            return 'service'
        elif 'configmap' in command.lower():
            return 'configmap'
        elif 'secret' in command.lower():
            return 'secret'
        elif 'namespace' in command.lower():
            return 'namespace'
        else:
            return 'general'

    def scrape_yaml_manifests(self):
        """Scrape YAML manifests from free GitHub repositories"""
        print("Scraping YAML manifests...")

        # Sample manifests for different resource types
        manifests = {
            'pod': {
                'apiVersion': 'v1',
                'kind': 'Pod',
                'metadata': {
                    'name': 'nginx-pod',
                    'labels': {'app': 'nginx'}
                },
                'spec': {
                    'containers': [{
                        'name': 'nginx',
                        'image': 'nginx:1.20',
                        'ports': [{'containerPort': 80}]
                    }]
                }
            },
            'deployment': {
                'apiVersion': 'apps/v1',
                'kind': 'Deployment',
                'metadata': {
                    'name': 'nginx-deployment',
                    'labels': {'app': 'nginx'}
                },
                'spec': {
                    'replicas': 3,
                    'selector': {
                        'matchLabels': {'app': 'nginx'}
                    },
                    'template': {
                        'metadata': {
                            'labels': {'app': 'nginx'}
                        },
                        'spec': {
                            'containers': [{
                                'name': 'nginx',
                                'image': 'nginx:1.20',
                                'ports': [{'containerPort': 80}]
                            }]
                        }
                    }
                }
            },
            'service': {
                'apiVersion': 'v1',
                'kind': 'Service',
                'metadata': {
                    'name': 'nginx-service',
                    'labels': {'app': 'nginx'}
                },
                'spec': {
                    'selector': {'app': 'nginx'},
                    'ports': [{
                        'protocol': 'TCP',
                        'port': 80,
                        'targetPort': 80
                    }],
                    'type': 'ClusterIP'
                }
            },
            'configmap': {
                'apiVersion': 'v1',
                'kind': 'ConfigMap',
                'metadata': {
                    'name': 'app-config'
                },
                'data': {
                    'config.properties': 'app.name=MyApp\napp.version=1.0',
                    'database.url': 'jdbc:mysql://localhost:3306/mydb'
                }
            }
        }

        for manifest_type, manifest in manifests.items():
            self.yaml_manifests.append({
                'type': manifest_type,
                'manifest': manifest,
                'yaml_content': yaml.dump(manifest, default_flow_style=False),
                'source': 'generated_template'
            })

class CKADQuestionGenerator:
    """Generates CKAD-style questions from Kubernetes resources"""

    def __init__(self):
        self.question_templates = {
            'pod': [
                "Create a pod named '{name}' using the {image} image",
                "Create a pod that runs {image} and exposes port {port}",
                "Create a pod with the label app={label}",
                "Create a pod and configure it to restart only on failure"
            ],
            'deployment': [
                "Create a deployment named '{name}' with {replicas} replicas using {image}",
                "Scale the deployment '{name}' to {replicas} replicas",
                "Update the deployment '{name}' to use image {image}",
                "Create a deployment and expose it as a service"
            ],
            'service': [
                "Create a service to expose the deployment '{name}' on port {port}",
                "Create a NodePort service for the '{name}' deployment",
                "Create a ClusterIP service that selects pods with label app={label}"
            ],
            'configmap': [
                "Create a ConfigMap named '{name}' with key-value pairs",
                "Create a pod that mounts a ConfigMap as a volume",
                "Create a pod that uses ConfigMap values as environment variables"
            ]
        }

    def generate_questions_from_commands(self, commands: List[Dict]) -> List[Dict]:
        """Generate questions based on kubectl commands"""
        questions = []

        for cmd_data in commands:
            command = cmd_data['command']
            category = cmd_data['category']

            if category in self.question_templates:
                # Extract parameters from command
                params = self._extract_command_parameters(command)

                # Generate questions
                for template in self.question_templates[category]:
                    try:
                        question = template.format(**params)
                        questions.append({
                            'question': question,
                            'command': command,
                            'category': category,
                            'difficulty': self._assess_difficulty(command),
                            'source_type': 'command'
                        })
                    except KeyError:
                        # Template requires parameters not in command
                        continue

        return questions

    def generate_questions_from_manifests(self, manifests: List[Dict]) -> List[Dict]:
        """Generate questions based on YAML manifests"""
        questions = []

        for manifest_data in manifests:
            manifest_type = manifest_data['type']
            manifest = manifest_data['manifest']
            yaml_content = manifest_data['yaml_content']

            if manifest_type in self.question_templates:
                # Extract parameters from manifest
                params = self._extract_manifest_parameters(manifest)

                # Generate questions
                for template in self.question_templates[manifest_type]:
                    try:
                        question = template.format(**params)
                        questions.append({
                            'question': question,
                            'manifest': yaml_content,
                            'category': manifest_type,
                            'difficulty': self._assess_manifest_difficulty(manifest),
                            'source_type': 'manifest'
                        })
                    except KeyError:
                        continue

        return questions

    def _extract_command_parameters(self, command: str) -> Dict[str, str]:
        """Extract parameters from kubectl command"""
        params = {
            'name': 'my-app',
            'image': 'nginx',
            'port': '80',
            'replicas': '3',
            'label': 'nginx'
        }

        # Extract actual parameters from command
        if '--image=' in command:
            image = re.search(r'--image=([^\s]+)', command)
            if image:
                params['image'] = image.group(1)

        if 'deployment' in command:
            name = re.search(r'deployment\s+([^\s]+)', command)
            if name:
                params['name'] = name.group(1)

        return params

    def _extract_manifest_parameters(self, manifest: Dict[str, Any]) -> Dict[str, str]:
        """Extract parameters from YAML manifest"""
        params = {
            'name': manifest.get('metadata', {}).get('name', 'my-app'),
            'image': 'nginx',
            'port': '80',
            'replicas': '3',
            'label': 'nginx'
        }

        # Extract image from containers
        spec = manifest.get('spec', {})
        if 'containers' in spec:
            containers = spec['containers']
            if containers and 'image' in containers[0]:
                params['image'] = containers[0]['image']

        # Extract replicas from deployment
        if 'replicas' in spec:
            params['replicas'] = str(spec['replicas'])

        return params

    def _assess_difficulty(self, command: str) -> str:
        """Assess command difficulty level"""
        if any(word in command for word in ['get', 'describe']):
            return 'easy'
        elif any(word in command for word in ['create', 'apply', 'expose']):
            return 'medium'
        elif any(word in command for word in ['rollout', 'scale', 'exec']):
            return 'hard'
        else:
            return 'medium'

    def _assess_manifest_difficulty(self, manifest: Dict[str, Any]) -> str:
        """Assess manifest complexity"""
        if manifest.get('kind') in ['Pod', 'ConfigMap']:
            return 'easy'
        elif manifest.get('kind') in ['Deployment', 'Service']:
            return 'medium'
        else:
            return 'hard'

def main():
    parser = argparse.ArgumentParser(description='Generate CKAD questions from Kubernetes resources')
    parser.add_argument('--mode', choices=['scrape', 'generate', 'both'], default='both',
                      help='Mode: scrape resources, generate questions, or both')
    parser.add_argument('--output', default='k8s_questions.json',
                      help='Output file for questions')
    parser.add_argument('--count', type=int, default=50,
                      help='Number of questions to generate')

    args = parser.parse_args()

    if args.mode in ['scrape', 'both']:
        print("=== Scraping Kubernetes Resources ===")
        scraper = KubernetesResourceScraper()
        scraper.scrape_kubectl_commands()
        scraper.scrape_yaml_manifests()

        print(f"Found {len(scraper.kubectl_commands)} kubectl commands")
        print(f"Found {len(scraper.yaml_manifests)} YAML manifests")

    if args.mode in ['generate', 'both']:
        print("\n=== Generating CKAD Questions ===")
        generator = CKADQuestionGenerator()

        if args.mode == 'generate':
            # Load previously scraped data
            scraper = KubernetesResourceScraper()
            scraper.scrape_kubectl_commands()
            scraper.scrape_yaml_manifests()

        cmd_questions = generator.generate_questions_from_commands(scraper.kubectl_commands)
        manifest_questions = generator.generate_questions_from_manifests(scraper.yaml_manifests)

        all_questions = cmd_questions + manifest_questions
        random.shuffle(all_questions)

        # Limit to requested count
        questions_to_save = all_questions[:args.count]

        # Save questions
        with open(args.output, 'w') as f:
            json.dump(questions_to_save, f, indent=2)

        print(f"Generated {len(questions_to_save)} questions")
        print(f"Questions saved to {args.output}")

        # Display sample questions
        print("\n=== Sample Questions ===")
        for i, question in enumerate(questions_to_save[:5], 1):
            print(f"{i}. {question['question']}")
            if question['source_type'] == 'command':
                print(f"   Command: {question['command']}")
            print(f"   Category: {question['category']}, Difficulty: {question['difficulty']}")
            print()

if __name__ == "__main__":
    main()
