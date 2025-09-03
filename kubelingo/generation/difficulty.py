"""
Difficulty levels and Kubernetes topic enums for question generation.
"""
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