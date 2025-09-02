#!/usr/bin/env python3
"""
Kubernetes Question Generator Module

This module generates natural language questions about Kubernetes topics
with varying difficulty levels for training and assessment purposes.
"""

import random
import json
from typing import Dict, List, Optional
from enum import Enum

class DifficultyLevel(Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"

class KubernetesTopics(Enum):
    PODS = "pods"
    DEPLOYMENTS = "deployments"
    SERVICES = "services"
    CONFIGMAPS = "configmaps"
    SECRETS = "secrets"
    INGRESS = "ingress"
    VOLUMES = "volumes"
    RBAC = "rbac"
    NETWORKING = "networking"
    MONITORING = "monitoring"
    SECURITY = "security"
    TROUBLESHOOTING = "troubleshooting"

class QuestionGenerator:
    def __init__(self):
        self.question_templates = self._init_question_templates()
        self.contexts = self._init_contexts()
    
    def _init_question_templates(self) -> Dict[str, Dict[str, List[str]]]:
        """Initialize question templates organized by topic and difficulty"""
        return {
            KubernetesTopics.PODS.value: {
                DifficultyLevel.BEGINNER.value: [
                    "Create a simple Pod named '{pod_name}' running '{image}' image",
                    "Deploy a Pod with '{image}' that exposes port {port}",
                    "Create a Pod that runs '{image}' with environment variable {env_var}='{env_value}'"
                ],
                DifficultyLevel.INTERMEDIATE.value: [
                    "Create a Pod with resource limits: CPU {cpu_limit} and memory {memory_limit}",
                    "Deploy a Pod with a sidecar container for logging using '{sidecar_image}'",
                    "Create a Pod with both resource requests and limits, and readiness probe"
                ],
                DifficultyLevel.ADVANCED.value: [
                    "Create a Pod with init containers, security context, and custom service account",
                    "Deploy a Pod with affinity rules, tolerations, and custom DNS policy",
                    "Create a multi-container Pod with shared volumes and inter-container communication"
                ]
            },
            KubernetesTopics.DEPLOYMENTS.value: {
                DifficultyLevel.BEGINNER.value: [
                    "Create a Deployment named '{deployment_name}' with {replicas} replicas of '{image}'",
                    "Deploy an application with horizontal scaling capabilities",
                    "Create a Deployment with rolling update strategy"
                ],
                DifficultyLevel.INTERMEDIATE.value: [
                    "Create a Deployment with custom rolling update parameters and health checks",
                    "Deploy an application with HorizontalPodAutoscaler based on CPU utilization",
                    "Create a Deployment with persistent storage and ConfigMap integration"
                ],
                DifficultyLevel.ADVANCED.value: [
                    "Create a blue-green deployment strategy with custom labels and selectors",
                    "Deploy a stateful application with ordered deployment and persistent volumes",
                    "Create a Deployment with advanced scheduling, resource quotas, and network policies"
                ]
            },
            KubernetesTopics.SERVICES.value: {
                DifficultyLevel.BEGINNER.value: [
                    "Create a ClusterIP Service to expose '{deployment_name}' on port {port}",
                    "Create a NodePort Service for external access to your application",
                    "Expose a Deployment using a LoadBalancer Service"
                ],
                DifficultyLevel.INTERMEDIATE.value: [
                    "Create a Service with multiple ports and custom endpoint configuration",
                    "Deploy a headless Service for StatefulSet communication",
                    "Create a Service with session affinity and custom timeout settings"
                ],
                DifficultyLevel.ADVANCED.value: [
                    "Create an ExternalName Service with custom DNS configuration",
                    "Deploy a Service mesh integration with Istio sidecar injection",
                    "Create Services with advanced traffic routing and load balancing"
                ]
            },
            KubernetesTopics.INGRESS.value: {
                DifficultyLevel.INTERMEDIATE.value: [
                    "Create an Ingress resource to route traffic to multiple services",
                    "Configure SSL/TLS termination with custom certificates",
                    "Set up path-based routing with custom headers and annotations"
                ],
                DifficultyLevel.ADVANCED.value: [
                    "Create an Ingress with advanced features: rate limiting, authentication, and CORS",
                    "Deploy a multi-tenant Ingress setup with namespace isolation",
                    "Configure Ingress with custom error pages and advanced rewrite rules"
                ]
            },
            KubernetesTopics.SECURITY.value: {
                DifficultyLevel.INTERMEDIATE.value: [
                    "Create a Pod with security context: non-root user, read-only filesystem",
                    "Deploy an application with Pod Security Standards enforcement",
                    "Create RBAC rules for service account with minimal permissions"
                ],
                DifficultyLevel.ADVANCED.value: [
                    "Implement Network Policies for micro-segmentation and zero-trust",
                    "Create a comprehensive security setup with admission controllers",
                    "Deploy applications with OPA Gatekeeper policy enforcement"
                ]
            },
            KubernetesTopics.TROUBLESHOOTING.value: {
                DifficultyLevel.INTERMEDIATE.value: [
                    "Debug a failing Pod that keeps restarting due to configuration issues",
                    "Troubleshoot service connectivity issues between microservices",
                    "Resolve resource constraints causing Pod scheduling failures"
                ],
                DifficultyLevel.ADVANCED.value: [
                    "Debug complex networking issues in a multi-cluster setup",
                    "Troubleshoot performance bottlenecks in a high-traffic application",
                    "Resolve storage and persistence issues in a StatefulSet"
                ]
            }
        }
    
    def _init_contexts(self) -> Dict[str, List[str]]:
        """Initialize context scenarios for more realistic questions"""
        return {
            "applications": ["nginx", "redis", "mysql", "nodejs-app", "python-api", "react-frontend"],
            "environments": ["development", "staging", "production", "testing"],
            "industries": ["e-commerce", "fintech", "healthcare", "gaming", "iot"],
            "scaling_scenarios": ["Black Friday traffic", "viral social media post", "planned maintenance", "disaster recovery"],
            "team_sizes": ["small startup", "enterprise", "mid-size company", "open source project"]
        }
    
    def generate_question(self, 
                         topic: Optional[str] = None, 
                         difficulty: Optional[str] = None,
                         include_context: bool = True) -> Dict[str, Any]:
        """Generate a Kubernetes question with specified parameters"""
        
        # Select random topic and difficulty if not specified
        if topic is None:
            topic = random.choice(list(KubernetesTopics)).value
        if difficulty is None:
            difficulty = random.choice(list(DifficulityLevel)).value
            
        # Get question template
        templates = self.question_templates.get(topic, {}).get(difficulty, [])
        if not templates:
            # Fallback to beginner pods if topic/difficulty combo doesn't exist
            templates = self.question_templates[KubernetesTopics.PODS.value][DifficultyLevel.BEGINNER.value]
            topic = KubernetesTopics.PODS.value
            difficulty = DifficultyLevel.BEGINNER.value
        
        template = random.choice(templates)
        
        # Generate context variables
        context_vars = self._generate_context_variables()
        
        # Fill template with context
        try:
            question_text = template.format(**context_vars)
        except KeyError:
            # If template has variables we don't have, use as-is
            question_text = template
            
        question = {
            "id": self._generate_question_id(),
            "topic": topic,
            "difficulty": difficulty,
            "question": question_text,
            "context_variables": context_vars,
            "expected_resources": self._get_expected_resources(topic),
            "success_criteria": self._generate_success_criteria(topic, difficulty),
            "hints": self._generate_hints(topic, difficulty) if difficulty in [DifficultyLevel.ADVANCED.value, DifficultyLevel.EXPERT.value] else []
        }
        
        if include_context:
            question["scenario_context"] = self._generate_scenario_context()
            
        return question
    
    def _generate_context_variables(self) -> Dict[str, str]:
        """Generate realistic context variables for question templates"""
        return {
            "pod_name": f"{random.choice(['web', 'api', 'worker', 'cache'])}-{random.randint(1, 999)}",
            "deployment_name": f"{random.choice(self.contexts['applications'])}-deployment",
            "image": random.choice(["nginx:1.21", "redis:6.2", "mysql:8.0", "node:16", "python:3.9"]),
            "port": random.choice([80, 8080, 3000, 5000, 8000, 9000]),
            "replicas": random.choice([2, 3, 5, 8, 10]),
            "cpu_limit": random.choice(["100m", "200m", "500m", "1", "2"]),
            "memory_limit": random.choice(["128Mi", "256Mi", "512Mi", "1Gi", "2Gi"]),
            "env_var": random.choice(["DATABASE_URL", "API_KEY", "LOG_LEVEL", "PORT", "NODE_ENV"]),
            "env_value": random.choice(["production", "development", "info", "debug", "8080"]),
            "sidecar_image": random.choice(["fluent/fluent-bit:1.8", "grafana/promtail:2.4.0"])
        }
    
    def _get_expected_resources(self, topic: str) -> List[str]:
        """Return expected Kubernetes resources for a given topic"""
        resource_mapping = {
            KubernetesTopics.PODS.value: ["Pod"],
            KubernetesTopics.DEPLOYMENTS.value: ["Deployment"],
            KubernetesTopics.SERVICES.value: ["Service"],
            KubernetesTopics.INGRESS.value: ["Ingress"],
            KubernetesTopics.CONFIGMAPS.value: ["ConfigMap"],
            KubernetesTopics.SECRETS.value: ["Secret"],
            KubernetesTopics.RBAC.value: ["Role", "RoleBinding", "ServiceAccount"],
            KubernetesTopics.VOLUMES.value: ["PersistentVolume", "PersistentVolumeClaim"],
            KubernetesTopics.NETWORKING.value: ["NetworkPolicy"],
            KubernetesTopics.MONITORING.value: ["ServiceMonitor", "PodMonitor"],
        }
        return resource_mapping.get(topic, ["Pod"])
    
    def _generate_success_criteria(self, topic: str, difficulty: str) -> List[str]:
        """Generate success criteria for grading"""
        base_criteria = [
            "YAML syntax is valid",
            "Required Kubernetes resources are defined",
            "Resource specifications are complete"
        ]
        
        if difficulty in [DifficultyLevel.INTERMEDIATE.value, DifficultyLevel.ADVANCED.value]:
            base_criteria.extend([
                "Best practices are followed",
                "Resource limits and requests are specified",
                "Labels and selectors are properly configured"
            ])
            
        if difficulty == DifficultyLevel.ADVANCED.value:
            base_criteria.extend([
                "Security contexts are properly configured",
                "Advanced features are correctly implemented",
                "Solution demonstrates deep Kubernetes knowledge"
            ])
            
        return base_criteria
    
    def _generate_hints(self, topic: str, difficulty: str) -> List[str]:
        """Generate hints for complex questions"""
        hints = {
            KubernetesTopics.PODS.value: [
                "Remember to specify resource requests and limits",
                "Consider adding readiness and liveness probes",
                "Don't forget to set appropriate security contexts"
            ],
            KubernetesTopics.DEPLOYMENTS.value: [
                "Configure rolling update strategy parameters",
                "Add proper labels for service selection",
                "Consider pod disruption budgets for availability"
            ],
            KubernetesTopics.SECURITY.value: [
                "Use non-root users when possible",
                "Implement principle of least privilege",
                "Consider network policies for traffic control"
            ]
        }
        return random.sample(hints.get(topic, hints[KubernetesTopics.PODS.value]), min(2, len(hints.get(topic, []))))
    
    def _generate_scenario_context(self) -> Dict[str, str]:
        """Generate realistic scenario context"""
        return {
            "environment": random.choice(self.contexts["environments"]),
            "industry": random.choice(self.contexts["industries"]),
            "team_size": random.choice(self.contexts["team_sizes"]),
            "constraints": random.choice([
                "Cost optimization is critical",
                "High availability is required",
                "Security compliance is mandatory",
                "Fast deployment is essential"
            ])
        }
    
    def _generate_question_id(self) -> str:
        """Generate unique question ID"""
        import hashlib
        import time
        return hashlib.md5(f"{time.time()}".encode()).hexdigest()[:8]
    
    def generate_question_set(self, count: int = 10, **filters) -> List[Dict[str, Any]]:
        """Generate a set of questions with optional filters"""
        questions = []
        for _ in range(count):
            question = self.generate_question(**filters)
            questions.append(question)
        return questions
    
    def save_questions_to_file(self, questions: List[Dict[str, Any]], filename: str):
        """Save generated questions to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(questions, f, indent=2, ensure_ascii=False)

def main():
    """Demo usage of the question generator"""
    generator = QuestionGenerator()
    
    # Generate single questions
    print("=== Single Question Examples ===")
    
    # Beginner pod question
    question1 = generator.generate_question(topic="pods", difficulty="beginner")
    print(f"Beginner Pod Question: {question1['question']}")
    print(f"Success Criteria: {question1['success_criteria']}")
    print()
    
    # Advanced deployment question  
    question2 = generator.generate_question(topic="deployments", difficulty="advanced")
    print(f"Advanced Deployment Question: {question2['question']}")
    print(f"Hints: {question2['hints']}")
    print()
    
    # Generate a question set
    print("=== Question Set Generation ===")
    question_set = generator.generate_question_set(count=5, difficulty="intermediate")
    
    for i, q in enumerate(question_set, 1):
        print(f"{i}. [{q['topic'].title()}] {q['question']}")
    
    # Save to file
    generator.save_questions_to_file(question_set, "sample_questions.json")
    print(f"\nSaved {len(question_set)} questions to sample_questions.json")

if __name__ == "__main__":
    main()