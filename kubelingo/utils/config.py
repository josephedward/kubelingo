import os
import json
from typing import Optional, Dict, Any

# The absolute path to the project root directory, which contains the 'kubelingo' package and 'scripts'.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# The root of the package (package directory)
PACKAGE_ROOT = os.path.join(PROJECT_ROOT, 'kubelingo')
# Legacy alias for backward compatibility: now points to project root
ROOT = PROJECT_ROOT

# User-specific files (logs, history, database etc.) in home directory
# to support installed package execution.
HOME_DIR = os.path.expanduser("~")
# By default use project-local .kubelingo directory to ensure write access
APP_DIR = os.path.join(PROJECT_ROOT, ".kubelingo")
# Logs directory located within the project root
LOGS_DIR = os.path.join(PROJECT_ROOT, 'logs')
try:
    os.makedirs(APP_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
except Exception:
    # Could not create directories (permissions?), ignore
    pass

# Data directories for built-in quiz files are located at the project root.
# Data directories for built-in quiz files are located at the project root.
DATA_DIR = os.path.join(PROJECT_ROOT, 'question-data')

# The single, consolidated directory for all question data after running the consolidation script.
# The build_question_db.py script will use this as the sole source.
QUESTIONS_DIR = os.path.join(DATA_DIR, 'questions')


# --- Pathfinding & Discovery Configuration ---
# These lists define candidate directories for scripts to scan, making the project
# more resilient to file reorganization. They are used by helpers in `kubelingo.utils.path_utils`.

# Candidate directories for question sources (YAML/YML files).
# This now merges the former QUESTION_SOURCE_DIRS and QUESTION_DIRS
QUESTION_DIRS = [
    QUESTIONS_DIR,  # Primary, consolidated directory
    os.path.join(DATA_DIR, 'yaml'),  # Legacy YAML quizzes
    os.path.join(PROJECT_ROOT, 'misc', 'manifests'),  # Legacy manifests
    os.path.join(DATA_DIR, 'yaml-bak'),  # Legacy backup
    os.path.join(PROJECT_ROOT, 'question-data-archive'),
    os.path.join(PROJECT_ROOT, 'question-data-backup'),
]

# Candidate directories for YAML backup files.
YAML_BACKUP_DIRS = [
    os.path.join(PROJECT_ROOT, 'backups', 'yaml'),
    os.path.join(PROJECT_ROOT, 'question-data', 'yaml'),
    os.path.join(PROJECT_ROOT, 'question-data-archive'),
]

# Candidate directories for SQLite database backups.
SQLITE_BACKUP_DIRS = [
    os.path.join(PROJECT_ROOT, 'backups', 'sqlite'),
    os.path.join(PROJECT_ROOT, 'question-data-backup'),
]


# --- Legacy Data Directories (used ONLY by the consolidation script) ---
# These paths are preserved to allow the one-time consolidation script to find the old files.
# They are not used by the main application or build script.
YAML_QUIZ_DIR = os.path.join(DATA_DIR, 'yaml')
YAML_QUESTIONS_FILE = os.path.join(YAML_QUIZ_DIR, 'yaml_exercises_quiz.yaml')


# --- Consolidated Question Files ---
K8S_QUESTIONS_FILE = os.path.join(PROJECT_ROOT, 'question-data-archive', 'yaml', 'kubernetes.yaml')


## --- Interactive Quiz Modules ---
# Organize quizzes into three core types: Basic, Command, and Manifest
# Basic/Open-Ended quizzes (conceptual Q&A)
BASIC_QUIZZES = {
    "General Operations": os.path.join(QUESTIONS_DIR, 'kubectl_operations.yaml'),
}
# Command-Based/Syntax quizzes (kubectl, helm, shell, vim commands)
COMMAND_QUIZZES = {
    "Resource Reference": os.path.join(QUESTIONS_DIR, 'resource_reference.yaml'),
    "Kubectl Operations": os.path.join(QUESTIONS_DIR, 'kubectl_operations.yaml'),
    "Additional Commands": os.path.join(QUESTIONS_DIR, 'additional_commands.yaml'),
    "CKAD Practice": os.path.join(QUESTIONS_DIR, 'ckad_questions.yaml'),
    "ConfigMap Operations": os.path.join(QUESTIONS_DIR, 'configmap_operations.yaml'),
    "Deployment Management": os.path.join(QUESTIONS_DIR, 'deployment_management.yaml'),
    "Helm Basics": os.path.join(QUESTIONS_DIR, 'helm_basics.yaml'),
    "Helm Repositories": os.path.join(QUESTIONS_DIR, 'helm_basics.yaml'),
    "Kubectl Common Operations": os.path.join(QUESTIONS_DIR, 'kubectl_common_operations.yaml'),
    "Namespace Operations": os.path.join(QUESTIONS_DIR, 'namespace_operations.yaml'),
    "Pod Management": os.path.join(QUESTIONS_DIR, 'pod_management.yaml'),
    "Secret Management": os.path.join(QUESTIONS_DIR, 'secret_management.yaml'),
    "Service Account Operations": os.path.join(QUESTIONS_DIR, 'service_account_operations.yaml'),
    "Shell Setup: Aliases & Autocomplete": os.path.join(QUESTIONS_DIR, 'syntax_and_shell_setup.yaml'),
    "Vim Basics": os.path.join(QUESTIONS_DIR, 'vim_basics.yaml'),
}
# Manifest-Based exercises (YAML authoring and editing)
MANIFEST_QUIZZES = {
    # YAML authoring exercises
    "Configuration & Security": os.path.join(QUESTIONS_DIR, 'configuration_&_security.yaml'),
    "Core Concepts": os.path.join(QUESTIONS_DIR, 'core_concepts.yaml'),
    "Helm": os.path.join(QUESTIONS_DIR, 'helm.yaml'),
    "Services Manifests": os.path.join(QUESTIONS_DIR, 'services.yaml'),
    "Workload Management": os.path.join(QUESTIONS_DIR, 'workload_management.yaml'),
    "YAML Authoring": os.path.join(QUESTIONS_DIR, 'yaml_authoring.yaml'),
    "YAML Editing - ConfigMaps": os.path.join(QUESTIONS_DIR, 'yaml_editing-configmaps.yaml'),
    "YAML Editing - Deployments": os.path.join(QUESTIONS_DIR, 'yaml_editing-deployments.yaml'),
    "YAML Editing - General": os.path.join(QUESTIONS_DIR, 'yaml_editing-general.yaml'),
    "YAML Editing - Pods": os.path.join(QUESTIONS_DIR, 'yaml_editing-pods.yaml'),
    "YAML Editing Practice": os.path.join(QUESTIONS_DIR, 'yaml_editing_practice.yaml'),
}
## Aggregate all enabled quizzes for interactive selection
ENABLED_QUIZZES = {**BASIC_QUIZZES, **COMMAND_QUIZZES, **MANIFEST_QUIZZES}
# --- Database ---
# Writable database for user data (history, AI questions) stored in ~/.kubelingo/kubelingo.db
DATABASE_FILE = os.path.join(APP_DIR, 'kubelingo.db')


def get_live_db_path() -> str:
    """Helper function to return the canonical path to the live user database."""
    return DATABASE_FILE


# Read-only master backup of original questions. Used to seed the user's DB on first run.
MASTER_DATABASE_FILE = os.path.join(PROJECT_ROOT, 'question-data-backup', 'kubelingo_original.db')
# Secondary backup for redundancy (fallback).
SECONDARY_MASTER_DATABASE_FILE = os.path.join(PROJECT_ROOT, 'question-data-backup', 'kubelingo.db')

# Predefined subject-matter categories for questions (subcategory within exercise types).
# Each question's 'category' field must match one of these values for consistent classification.
SUBJECT_MATTER = [
    "Core workloads (Pods, ReplicaSets, Deployments; rollouts/rollbacks)",
    "Pod design patterns (initContainers, sidecars, lifecycle hooks)",
    "Commands, args, and env (ENTRYPOINT/CMD overrides, env/envFrom)",
    "App configuration (ConfigMaps, Secrets, projected & downwardAPI volumes)",
    "Probes & health (liveness, readiness, startup; graceful shutdown)",
    "Resource management (requests/limits, QoS classes, HPA basics)",
    "Jobs & CronJobs (completions, parallelism, backoff, schedules)",
    "Services (ClusterIP/NodePort/LoadBalancer, selectors, headless)",
    "Ingress & HTTP routing (basic rules, paths, service backends)",
    "Networking utilities (DNS in-cluster, port-forward, exec, curl)",
    "Persistence (PVCs, using existing StorageClasses, common volume types)",
    "Observability & troubleshooting (logs, describe/events, kubectl debug/ephemeral containers)",
    "Labels, annotations & selectors (label ops, field selectors, jsonpath)",
    "Imperative vs declarative (—dry-run, create/apply/edit/replace/patch)",
    "Image & registry use (imagePullPolicy, imagePullSecrets, private registries)",
    "Security basics (securityContext, runAsUser/fsGroup, capabilities, readOnlyRootFilesystem)",
    "ServiceAccounts in apps (mounting SA, minimal RBAC for app access)",
    "Scheduling hints (nodeSelector, affinity/anti-affinity, tolerations)",
    "Namespaces & contexts (scoping resources, default namespace, context switching)",
    "API discovery & docs (kubectl explain, api-resources, api-versions)",
    "Kubectl CLI usage and commands",
    "Vim editor usage",
]


# --- API Keys ---
API_KEY_FILE = os.path.join(APP_DIR, 'api_key')


# --- Cluster Configuration ---
CLUSTER_CONFIG_FILE = os.path.join(APP_DIR, 'clusters.json')


def save_api_key(key: str) -> bool:
    """Saves the OpenAI API key to the config file."""
    try:
        os.makedirs(APP_DIR, mode=0o700, exist_ok=True)
        with open(API_KEY_FILE, 'w', encoding='utf-8') as f:
            f.write(key.strip())
        os.chmod(API_KEY_FILE, 0o600)
        return True
    except Exception:
        return False


def get_api_key() -> Optional[str]:
    """Retrieves the OpenAI API key from the config file."""
    if os.path.exists(API_KEY_FILE):
        try:
            with open(API_KEY_FILE, 'r', encoding='utf-8') as f:
                key = f.read().strip()
                return key if key else None
        except Exception:
            pass
    return None


def save_cluster_configs(configs: Dict[str, Any]) -> bool:
    """Saves cluster configurations to a JSON file."""
    try:
        os.makedirs(APP_DIR, mode=0o700, exist_ok=True)
        with open(CLUSTER_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(configs, f, indent=2)
        os.chmod(CLUSTER_CONFIG_FILE, 0o600)
        return True
    except Exception:
        return False


def get_cluster_configs() -> Dict[str, Any]:
    """Retrieves cluster configurations from the JSON file."""
    if os.path.exists(CLUSTER_CONFIG_FILE):
        try:
            with open(CLUSTER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                return json.loads(content) if content else {}
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
        except Exception:
            pass
    return {}



# --- History and Logging ---
HISTORY_FILE = os.path.join(LOGS_DIR, '.cli_quiz_history.json')
INPUT_HISTORY_FILE = os.path.join(LOGS_DIR, '.kubelingo_input_history')
VIM_HISTORY_FILE = os.path.join(LOGS_DIR, '.kubelingo_vim_history')
LOG_FILE = os.path.join(LOGS_DIR, 'quiz_log.txt')
# Store for flagged question IDs (decoupled from quiz source files)
FLAGGED_QUESTIONS_FILE = os.path.join(LOGS_DIR, 'flagged_questions.json')


# Helper functions for path discovery can be implemented in path_utils.py
