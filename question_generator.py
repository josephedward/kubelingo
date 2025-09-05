#!/usr/bin/env python3
"""
Kubernetes Question Generator Module

This module generates natural language questions about Kubernetes topics
with varying difficulty levels for training and assessment purposes.
"""

import random
import json
from typing import Any, Dict, List, Optional
from enum import Enum



class QuestionType(Enum):
    VOCABULARY = "vocabulary"
    TRUE_FALSE = "true_false"


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

class DifficultyLevel(Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

class QuestionGenerator:
    def __init__(self):
        self.question_templates = self._init_question_templates()
        self.contexts = self._init_contexts()
        self.doc_links = self._init_doc_links()
        self._generated_question_ids = set()

    def _init_doc_links(self) -> Dict[str, str]:
        """Initialize documentation links for Kubernetes topics"""
        base_url = "https://kubernetes.io/docs/concepts"
        return {
            KubernetesTopics.PODS.value: f"{base_url}/workloads/pods/",
            KubernetesTopics.DEPLOYMENTS.value: f"{base_url}/workloads/controllers/deployment/",
            KubernetesTopics.SERVICES.value: f"{base_url}/services-networking/service/",
            KubernetesTopics.CONFIGMAPS.value: f"{base_url}/configuration/configmap/",
            KubernetesTopics.SECRETS.value: f"{base_url}/configuration/secret/",
            KubernetesTopics.INGRESS.value: f"{base_url}/services-networking/ingress/",
            KubernetesTopics.VOLUMES.value: f"{base_url}/storage/volumes/",
            KubernetesTopics.RBAC.value: f"{base_url}/security/rbac-authorization/",
        }
    
    def _init_question_templates(self) -> Dict[str, Any]:
        """Initialize question templates organized by topic and difficulty"""
        return {
            KubernetesTopics.PODS.value: [
                "Create a simple Pod named '{pod_name}' running '{image}' image",
                "Deploy a Pod with '{image}' that exposes port {port}",
                "Create a Pod that runs '{image}' with environment variable {env_var}='{env_value}'",
                "Create a Pod with resource limits: CPU {cpu_limit} and memory {memory_limit}",
                "Deploy a Pod with a sidecar container for logging using '{sidecar_image}'",
                "Create a Pod with both resource requests and limits, and readiness probe",
                "Create a Pod with init containers, security context, and custom service account",
                "Deploy a Pod with affinity rules, tolerations, and custom DNS policy",
                "Create a multi-container Pod with shared volumes and inter-container communication"
            ],
            KubernetesTopics.DEPLOYMENTS.value: [
                "Create a Deployment named '{deployment_name}' with {replicas} replicas of '{image}'",
                "Deploy an application named '{deployment_name}' with horizontal scaling capabilities, targeting {hpa_target_cpu}% CPU utilization",
                "Create a Deployment with rolling update strategy",
                "Create a Deployment with custom rolling update parameters and health checks",
                "Deploy an application with HorizontalPodAutoscaler based on CPU utilization",
                "Create a Deployment with persistent storage and ConfigMap integration",
                "Create a blue-green deployment strategy with custom labels and selectors",
                "Deploy a stateful application with ordered deployment and persistent volumes",
                "Create a Deployment with advanced scheduling, resource quotas, and network policies"
            ],
            KubernetesTopics.SERVICES.value: [
                "Create a ClusterIP Service to expose '{deployment_name}' on port {port}",
                "Create a NodePort Service for external access to your application",
                "Expose a Deployment using a LoadBalancer Service",
                "Create a Service with multiple ports and custom endpoint configuration",
                "Deploy a headless Service for StatefulSet communication",
                "Create a Service with session affinity and custom timeout settings",
                "Create an ExternalName Service with custom DNS configuration",
                "Deploy a Service mesh integration with Istio sidecar injection",
                "Create Services with advanced traffic routing and load balancing"
            ],
            # Volume-related question templates
            KubernetesTopics.VOLUMES.value: [
                "Create a PersistentVolume named '{pv_name}' with storage capacity {storage_capacity} and access mode {access_mode}",
                "Create a PersistentVolumeClaim named '{pvc_name}' requesting {storage_capacity} with access mode {access_mode}",
                "Configure a Pod to use an existing PersistentVolumeClaim '{pvc_name}' mounted at {mount_path}",
                "Create a StorageClass named '{storage_class}' with provisioner '{provisioner}' and use it in a PersistentVolumeClaim",
                "Deploy a Pod that mounts PVC '{pvc_name}' at path {mount_path} with subPath support",
                "Create a StatefulSet with volumeClaimTemplates using StorageClass '{storage_class}' and dynamic provisioning",
                "Configure a Pod with both emptyDir and hostPath volumes for data sharing and persistence",
                "Explain the purpose and usage of 'subPathExpr' in a VolumeMount, providing a practical example."
            ],
            KubernetesTopics.INGRESS.value: [
                "Create an Ingress resource named '{ingress_name}' to route traffic to service '{service_name}' on path '{path}'",
                "Create a simple Ingress to expose a web application",
                "Create an Ingress resource to route traffic to multiple services",
                "Configure SSL/TLS termination with custom certificates",
                "Set up path-based routing with custom headers and annotations",
                "Create an Ingress with advanced features: rate limiting, authentication, and CORS",
                "Deploy a multi-tenant Ingress setup with namespace isolation",
                "Configure Ingress with custom error pages and advanced rewrite rules"
            ],
            KubernetesTopics.SECURITY.value: [
                "Create a Pod with a SecurityContext that runs as non-root user",
                "Set a Pod's SecurityContext to run with `allowPrivilegeEscalation: false`",
                "Create a Pod with security context: non-root user, read-only filesystem",
                "Deploy an application with Pod Security Standards enforcement",
                "Create RBAC rules for service account with minimal permissions",
                "Implement Network Policies for micro-segmentation and zero-trust",
                "Create a comprehensive security setup with admission controllers",
                "Deploy applications with OPA Gatekeeper policy enforcement"
            ],
            KubernetesTopics.TROUBLESHOOTING.value: [
                "View the logs of a Pod named '{pod_name}'",
                "Get a shell into the container of Pod '{pod_name}'",
                "Debug a failing Pod that keeps restarting due to configuration issues",
                "Troubleshoot service connectivity issues between microservices",
                "Resolve resource constraints causing Pod scheduling failures",
                "Debug complex networking issues in a multi-cluster setup",
                "Troubleshoot performance bottlenecks in a high-traffic application",
                "Resolve storage and persistence issues in a StatefulSet"
            ],
            KubernetesTopics.RBAC.value: [
                "Create a ServiceAccount named '{sa_name}' in namespace '{namespace}'",
                "Create a Role named '{role_name}' that grants read access to Pods",
                "Create a RoleBinding named '{rb_name}' to bind Role '{role_name}' to ServiceAccount '{sa_name}'",
                "Create a ClusterRole that grants read access to Nodes and PersistentVolumes",
                "Create a ClusterRoleBinding to grant a user cluster-admin privileges",
                "Configure a Pod to use a specific ServiceAccount",
                "Create a Role with specific resourceNames and verb restrictions",
                "Design a multi-tenant RBAC structure with namespace isolation",
                "Audit RBAC permissions and identify potential security risks"
            ],
            KubernetesTopics.CONFIGMAPS.value: [
                "Create a ConfigMap named '{configmap_name}' with data '{configmap_key}' set to '{configmap_value}'",
                "Create a ConfigMap named '{configmap_name}' from file '{file_name}'",
                "Create a Pod that consumes a ConfigMap '{configmap_name}' as an environment variable",
                "Mount a ConfigMap '{configmap_name}' as a volume in a Pod at path '{mount_path}'",
                "Create a Pod that mounts a ConfigMap with subPath to a specific file",
                "Update a ConfigMap and observe the changes in a running Pod"
            ],
            KubernetesTopics.SECRETS.value: [
                "Create a Secret named '{secret_name}' with username '{secret_username}' and password '{secret_password}'",
                "Create a generic Secret '{secret_name}' from a local file '{file_name}'",
                "Create a Pod that consumes a Secret '{secret_name}' as an environment variable",
                "Mount a Secret '{secret_name}' as a volume in a Pod at path '{mount_path}'",
                "Create a Pod that uses a Secret to pull an image from a private registry",
                "Use a TLS Secret to secure an Ingress resource"
            ],
            KubernetesTopics.NETWORKING.value: [
                "Create a NetworkPolicy named '{policy_name}' that denies all ingress traffic to pods with label '{label}'",
                "Create a NetworkPolicy named '{policy_name}' that allows ingress traffic from pods with label '{label}'",
                "Create a NetworkPolicy that allows traffic from a specific IP block",
                "Create a NetworkPolicy that allows egress traffic to a specific CIDR",
                "Create a NetworkPolicy that allows traffic to the Kubernetes API server",
                "Design a NetworkPolicy to isolate a namespace by default"
            ],
                        KubernetesTopics.MONITORING.value: [
                "Create a ServiceMonitor to scrape metrics from a Service with label '{label}'",
                "Create a PodMonitor to scrape metrics from a Pod with label '{label}'",
                "Configure a ServiceMonitor to use a specific interval and scrape timeout",
                "Create a PodMonitor that scrapes metrics from a specific port",
                "Create a ServiceMonitor with relabeling rules to modify metrics labels",
                "Configure a PodMonitor to use mTLS for secure scraping"
            ],
            QuestionType.VOCABULARY.value: {
                KubernetesTopics.VOLUMES.value: [
                    {"question": "What is a PersistentVolume?", "description": "A piece of storage in the cluster that has been provisioned by an administrator or dynamically provisioned using Storage Classes.", "expected_answer": "PersistentVolume"},
                    {"question": "Define PersistentVolumeClaim.", "description": "A request for storage by a user that can be fulfilled by a PersistentVolume.", "expected_answer": "PersistentVolumeClaim"},
                    {"question": "Provide a detailed explanation of a Volume in Kubernetes, including its key components, lifecycle, and typical use-cases.", "description": "A directory accessible to all containers in a Pod, used for sharing data or persisting data beyond the life of a single container.", "expected_answer": "Volume"}
                ],
                KubernetesTopics.PODS.value: [
                    {"question": "Name this Kubernetes resource:", "description": "A basic unit of deployment in Kubernetes, representing a single instance of a running process in your cluster.", "expected_answer": "Pod"}
                ],
                "general": [
                    {"question": "What is a Pod?", "description": "The smallest deployable unit in Kubernetes.", "expected_answer": "Pod"},
                    {"question": "What is a Deployment?", "description": "A controller that provides declarative updates for Pods and ReplicaSets.", "expected_answer": "Deployment"}
                ]
            },
            QuestionType.TRUE_FALSE.value: {
                KubernetesTopics.VOLUMES.value: [
                    "True or False: An emptyDir volume persists data across pod restarts.",
                    "True or False: 'subPathExpr' can be used to dynamically select a file within a volume based on environment variables."
                ],
                "general": [
                    "True or False: A Pod can span multiple worker nodes."
                ]
            }
        }
        return templates
    
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
                         question_type: Optional[str] = None,
                         include_context: bool = True) -> Dict[str, Any]:
        """Generate a Kubernetes question with specified parameters"""

        max_retries = 10 # Limit retries to prevent infinite loops
        for _ in range(max_retries):
            # --- Existing logic for selecting question type, topic, difficulty, and templates ---
            # Select random question type if not specified
            _question_type = question_type # Use a local variable to avoid modifying the original parameter
            _topic = topic

            if _question_type is None:
                if _topic is not None and _topic in self.question_templates:
                    pass
                else:
                    _question_type = random.choice([qt.value for qt in QuestionType])

            if _topic is None:
                if _question_type in [QuestionType.VOCABULARY.value, QuestionType.TRUE_FALSE.value]:
                    available_topics = list(self.question_templates.get(_question_type, {}).keys())
                    if "general" in available_topics:
                        available_topics.remove("general")
                    if available_topics:
                        _topic = random.choice(available_topics)
                    else:
                        _topic = "general"
                else:
                    _topic = random.choice(list(KubernetesTopics)).value

            templates = []
            if _question_type in [QuestionType.VOCABULARY.value, QuestionType.TRUE_FALSE.value]:
                templates = self.question_templates.get(_question_type, {}).get(_topic, [])
                if not templates and _topic != "general":
                    templates = self.question_templates.get(_question_type, {}).get("general", [])
            else:
                templates = self.question_templates.get(_topic, [])

            if not templates:
                if _question_type == QuestionType.VOCABULARY.value:
                    _topic = "general"
                    templates = self.question_templates.get(QuestionType.VOCABULARY.value, {}).get(_topic, [])
                elif _question_type == QuestionType.TRUE_FALSE.value:
                    _topic = "general"
                    templates = self.question_templates.get(QuestionType.TRUE_FALSE.value, {}).get(_topic, [])
                else:
                    _topic = KubernetesTopics.PODS.value
                    templates = self.question_templates.get(_topic, [])

            # If no predefined templates, create a generic fallback question for this topic
            if not templates:
                if _question_type not in [QuestionType.VOCABULARY.value, QuestionType.TRUE_FALSE.value]:
                    resources = self._get_expected_resources(_topic)
                    resource = resources[0] if resources else _topic
                    var_name = f"{resource.lower()}_name"
                    context_vars = self._generate_context_variables()
                    context_vars[var_name] = f"{resource.lower()}-{random.randint(1, 999)}"
                    template = f"Create a {resource} named '{{{var_name}}}'"
                    question_text = template.format(**context_vars)
                    expected_resources = resources
                else:
                    question_text = f"No specific {_question_type} question found for topic '{_topic}'. Please define more templates."
                    context_vars = {}
                    expected_resources = []

                question_id = self._generate_question_id() # Generate ID here
                if question_id in self._generated_question_ids:
                    continue # Try again if ID is not unique

                question = {
                    "id": question_id,
                    "topic": _topic,
                    "question": question_text,
                    "documentation_link": self.doc_links.get(_topic),
                }
                if _question_type not in [QuestionType.VOCABULARY.value, QuestionType.TRUE_FALSE.value]:
                    question["context_variables"] = context_vars
                    question["expected_resources"] = expected_resources
                    question["success_criteria"] = self._generate_success_criteria(_topic)
                    question["hints"] = self._generate_hints(_topic)
                    if include_context:
                        question["scenario_context"] = self._generate_scenario_context()
                else: # For VOCABULARY and TRUE_FALSE questions
                    question["context_variables"] = {}
                    question["expected_resources"] = []
                    question["success_criteria"] = []
                    question["hints"] = []
                    question["scenario_context"] = None
                self._generated_question_ids.add(question_id) # Add to set
                return question
            # Otherwise, pick a random template and fill with context variables
            template = random.choice(templates)
            context_vars = self._generate_context_variables()

            question_text = ""
            description = ""
            expected_answer = ""

            if _question_type in [QuestionType.VOCABULARY.value, QuestionType.TRUE_FALSE.value]:
                question_text = template["question"]
                description = template.get("description", "") # Get description if available
                expected_answer = template.get("expected_answer", "") # Get expected_answer if available
            else:
                try:
                    question_text = template.format(**context_vars)
                except KeyError:
                    question_text = template

            question_id = self._generate_question_id() # Generate ID here
            if question_id in self._generated_question_ids:
                continue # Try again if ID is not unique

            question = {
                "id": question_id,
                "topic": _topic,
                "question": question_text,
                "documentation_link": self.doc_links.get(_topic),
            }

            if _question_type not in [QuestionType.VOCABULARY.value, QuestionType.TRUE_FALSE.value]:
                question["context_variables"] = context_vars
                question["expected_resources"] = self._get_expected_resources(_topic)
                question["success_criteria"] = self._generate_success_criteria(_topic)
                question["hints"] = self._generate_hints(_topic)
                if include_context:
                    question["scenario_context"] = self._generate_scenario_context()
            else: # For VOCABULARY and TRUE_FALSE questions
                question["context_variables"] = {}
                question["expected_resources"] = []
                question["success_criteria"] = []
                question["hints"] = []
                question["scenario_context"] = None
                question["description"] = description # Add description
                question["expected_answer"] = expected_answer # Add expected_answer

            self._generated_question_ids.add(question_id) # Add to set
            return question

        # If max_retries reached without finding a unique question
        return {
            "id": self._generate_question_id(), # Still generate a unique ID for the fallback
            "topic": topic,
            "question": "Could not generate a unique question after multiple retries. Please try again or expand the question templates.",
            "documentation_link": None,
            "context_variables": {},
            "expected_resources": [],
            "success_criteria": [],
            "hints": []
        }
    
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
            "sidecar_image": random.choice(["fluent/fluent-bit:1.8", "grafana/promtail:2.4.0"]),
            "hpa_target_cpu": random.choice(["50", "60", "70", "80"]),
            # Volume-specific context variables
            "pv_name": f"pv-{random.randint(1, 999)}",
            "pvc_name": f"pvc-{random.randint(1, 999)}",
            "storage_capacity": random.choice(["1Gi", "5Gi", "10Gi", "50Gi"]),
            "access_mode": random.choice(["ReadWriteOnce", "ReadOnlyMany", "ReadWriteMany"]),
            "storage_class": random.choice(["standard", "fast", "premium", "slow"]),
            "provisioner": random.choice(["kubernetes.io/aws-ebs", "kubernetes.io/gce-pd", "kubernetes.io/cinder"]),
            "mount_path": random.choice(["/data", "/mnt/storage", "/var/lib"]),
            # RBAC-specific context variables
            "sa_name": f"sa-{random.randint(1, 999)}",
            "role_name": f"role-{random.randint(1, 999)}",
            "rb_name": f"rb-{random.randint(1, 999)}",
            "namespace": random.choice(["default", "kube-system", "production", "development"]),
            # ConfigMap-specific context variables
            "configmap_name": f"cm-{random.randint(1, 999)}",
            "configmap_key": random.choice(["app.properties", "settings.yaml", "config.json"]),
            "configmap_value": random.choice(["key1=value1", "user: admin"]),
            # Secret-specific context variables
            "secret_name": f"secret-{random.randint(1, 999)}",
            "secret_username": "admin",
            "secret_password": "password123",
            "file_name": random.choice(["config.properties", "api-key.txt", "app.conf"]),
            # Networking-specific context variables
            "policy_name": f"netpol-{random.randint(1, 999)}",
            "label": random.choice(["app=nginx", "tier=frontend", "env=production"])
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
    
    def _generate_success_criteria(self, topic: str) -> List[str]:
        """Generate success criteria for grading"""
        base_criteria = [
            "YAML syntax is valid",
            "Required Kubernetes resources are defined",
            "Resource specifications are complete",
            "Best practices are followed",
            "Resource limits and requests are specified",
            "Labels and selectors are properly configured",
            "Security contexts are properly configured",
            "Advanced features are correctly implemented",
            "Solution demonstrates deep Kubernetes knowledge"
        ]
            
        return base_criteria
    
    def _generate_hints(self, topic: str) -> List[str]:
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
    
    # Deployment question with horizontal scaling
    question1 = generator.generate_question(topic="deployments")
    print(f"Deployment Question: {question1['question']}")
    print()
    
    # Generate a question set for deployments
    print("=== Deployment Question Set Generation ===")
    question_set = generator.generate_question_set(count=2, topic="deployments")
    
    for i, q in enumerate(question_set, 1):
        print(f"{i}. [{q['topic'].title()}] {q['question']}")
    
    # Save to file
    generator.save_questions_to_file(question_set, "sample_questions.json")
    print(f"\nSaved {len(question_set)} questions to sample_questions.json")

if __name__ == "__main__":
    main()