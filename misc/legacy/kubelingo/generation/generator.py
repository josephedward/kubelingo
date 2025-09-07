"""
Question generation module for Kubelingo.
Leverages Kubernetes question templates to produce varied, difficulty-tagged questions.
"""
import random
import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from kubelingo.generation.difficulty import DifficultyLevel, KubernetesTopics

@dataclass
class Question:
    """
    Represents a generated Kubernetes question.
    """
    id: str
    topic: str
    difficulty: DifficultyLevel
    question: str
    context_variables: Dict[str, Any]
    expected_resources: List[str]
    success_criteria: List[str]
    hints: List[str]
    scenario_context: Dict[str, Any]

class QuestionGenerator:
    """
    Generates Kubernetes questions across topics and difficulty levels.
    """
    def __init__(self):
        self.question_templates = self._init_question_templates()
        self.contexts = self._init_contexts()

    def _init_question_templates(self) -> Dict[str, Dict[str, List[str]]]:
        """
        Initialize question templates organized by topic and difficulty.
        """
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
        """
        Initialize context variable pools for realistic question generation.
        """
        return {
            "applications": ["nginx", "redis", "mysql", "nodejs-app", "python-api", "react-frontend"],
            "environments": ["development", "staging", "production", "testing"],
            "industries": ["e-commerce", "fintech", "healthcare", "gaming", "iot"],
            "scaling_scenarios": ["Black Friday traffic", "viral social media post", "planned maintenance", "disaster recovery"],
            "team_sizes": ["small startup", "enterprise", "mid-size company", "open source project"]
        }

    def generate_question(
        self,
        topic: Optional[str] = None,
        difficulty: Optional[str] = None,
        include_context: bool = True
    ) -> Question:
        """
        Generate a single question with the specified topic and difficulty.
        Returns a Question object.
        """
        # Select topic and difficulty randomly if not specified
        if topic is None:
            topic = random.choice(list(self.question_templates.keys()))
        # Fallback if topic is unknown
        if topic not in self.question_templates:
            topic = KubernetesTopics.PODS.value
        if difficulty is None:
            difficulty = random.choice(list(self.question_templates.get(topic, {}).keys()))
        # Get templates for this combo
        templates = self.question_templates.get(topic, {}).get(difficulty, [])
        if not templates:
            # Fallback to beginner pods
            topic = KubernetesTopics.PODS.value
            difficulty = DifficultyLevel.BEGINNER.value
            templates = self.question_templates[topic][difficulty]
        template = random.choice(templates)
        # Generate context variables and fill template
        context_vars = self._generate_context_variables()
        try:
            question_text = template.format(**context_vars)
        except KeyError:
            question_text = template
        # Build Question object
        qid = self._generate_question_id()
        expected = self._get_expected_resources(topic)
        criteria = self._generate_success_criteria(topic, difficulty)
        hints = self._generate_hints(topic, difficulty) if difficulty in (DifficultyLevel.ADVANCED.value, DifficultyLevel.EXPERT.value) else []
        scenario = self._generate_scenario_context() if include_context else {}
        return Question(
            id=qid,
            topic=topic,
            difficulty=DifficultyLevel(difficulty) if isinstance(difficulty, str) else difficulty,
            question=question_text,
            context_variables=context_vars,
            expected_resources=expected,
            success_criteria=criteria,
            hints=hints,
            scenario_context=scenario
        )

    def generate_question_set(
        self,
        count: int = 1,
        topic: Optional[str] = None,
        difficulty: Optional[DifficultyLevel] = None
    ) -> List[Question]:
        """
        Generate a list of questions.
        """
        return [self.generate_question(topic=topic, difficulty=difficulty) for _ in range(count)]

    def save_questions_to_file(self, questions: List[Question], filename: str) -> None:
        """
        Save a list of questions to a JSON file.
        """
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump([{
                'id': q.id,
                'topic': q.topic,
                'difficulty': q.difficulty.value,
                'question': q.question,
                'context_variables': q.context_variables,
                'expected_resources': q.expected_resources,
                'success_criteria': q.success_criteria,
                'hints': q.hints,
                'scenario_context': q.scenario_context
            } for q in questions], f, indent=2, ensure_ascii=False)

    def _generate_context_variables(self) -> Dict[str, Any]:
        return {
            'pod_name': f"{random.choice(['web', 'api', 'worker', 'cache'])}-{random.randint(1,999)}",
            'deployment_name': f"{random.choice(self.contexts['applications'])}-deployment",
            'image': random.choice(['nginx:1.21', 'redis:6.2', 'mysql:8.0', 'node:16', 'python:3.9']),
            'port': random.choice([80,8080,3000,5000,8000,9000]),
            'replicas': random.choice([2,3,5,8,10]),
            'cpu_limit': random.choice(['100m','200m','500m','1','2']),
            'memory_limit': random.choice(['128Mi','256Mi','512Mi','1Gi','2Gi']),
            'env_var': random.choice(['DATABASE_URL','API_KEY','LOG_LEVEL','PORT','NODE_ENV']),
            'env_value': random.choice(['production','development','info','debug','8080']),
            'sidecar_image': random.choice(['fluent/fluent-bit:1.8','grafana/promtail:2.4.0'])
        }

    def _get_expected_resources(self, topic: str) -> List[str]:
        resource_mapping = {
            KubernetesTopics.PODS.value: ['Pod'],
            KubernetesTopics.DEPLOYMENTS.value: ['Deployment'],
            KubernetesTopics.SERVICES.value: ['Service'],
            KubernetesTopics.INGRESS.value: ['Ingress'],
            KubernetesTopics.CONFIGMAPS.value: ['ConfigMap'],
            KubernetesTopics.SECRETS.value: ['Secret'],
            KubernetesTopics.RBAC.value: ['Role','RoleBinding','ServiceAccount'],
            KubernetesTopics.VOLUMES.value: ['PersistentVolume','PersistentVolumeClaim'],
            KubernetesTopics.NETWORKING.value: ['NetworkPolicy'],
            KubernetesTopics.MONITORING.value: ['ServiceMonitor','PodMonitor'],
        }
        return resource_mapping.get(topic, ['Pod'])

    def _generate_success_criteria(self, topic: str, difficulty: str) -> List[str]:
        base = [
            'YAML syntax is valid',
            'Required Kubernetes resources are defined',
            'Resource specifications are complete'
        ]
        if difficulty in (DifficultyLevel.INTERMEDIATE.value, DifficultyLevel.ADVANCED.value):
            base += [
                'Best practices are followed',
                'Resource limits and requests are specified',
                'Labels and selectors are properly configured'
            ]
        if difficulty == DifficultyLevel.ADVANCED.value:
            base += [
                'Security contexts are properly configured',
                'Advanced features are correctly implemented',
                'Solution demonstrates deep Kubernetes knowledge'
            ]
        return base

    def _generate_hints(self, topic: str, difficulty: str) -> List[str]:
        hints = {
            KubernetesTopics.PODS.value: [
                'Remember to specify resource requests and limits',
                'Consider adding readiness and liveness probes',
                'Don\'t forget to set appropriate security contexts'
            ],
            KubernetesTopics.DEPLOYMENTS.value: [
                'Configure rolling update strategy parameters',
                'Add proper labels for service selection',
                'Consider pod disruption budgets for availability'
            ],
            KubernetesTopics.SECURITY.value: [
                'Use non-root users when possible',
                'Implement principle of least privilege',
                'Consider network policies for traffic control'
            ]
        }
        opts = hints.get(topic, hints[KubernetesTopics.PODS.value])
        return random.sample(opts, min(2, len(opts)))

    def _generate_scenario_context(self) -> Dict[str, Any]:
        return {
            'environment': random.choice(self.contexts['environments']),
            'industry': random.choice(self.contexts['industries']),
            'team_size': random.choice(self.contexts['team_sizes']),
            'constraints': random.choice([
                'Cost optimization is critical',
                'High availability is required',
                'Security compliance is mandatory',
                'Fast deployment is essential'
            ])
        }

    def _generate_question_id(self) -> str:
        import hashlib, time
        return hashlib.md5(str(time.time()).encode()).hexdigest()[:8]