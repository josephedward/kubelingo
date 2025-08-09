import os
import json
from typing import Optional, Dict, Any

# The root of the package
# The root of the package
# The absolute path to the package root directory
PACKAGE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
# Legacy alias for backward compatibility
ROOT = PACKAGE_ROOT
# Legacy alias for backward compatibility
ROOT = PACKAGE_ROOT

# User-specific files (logs, history, database etc.) in home directory
# to support installed package execution.
HOME_DIR = os.path.expanduser("~")
# Directory for user-specific app files (e.g., database)
APP_DIR = os.path.join(HOME_DIR, ".kubelingo")
# Logs directory located within the package root (for history and logging)
LOGS_DIR = os.path.join(PACKAGE_ROOT, 'logs')
try:
    os.makedirs(APP_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
except Exception:
    # Could not create directories (permissions?), ignore
    pass

# Data directories for built-in quiz files are located within the package,
# making them accessible after installation.
PROJECT_ROOT = PACKAGE_ROOT
DATA_DIR = os.path.join(PROJECT_ROOT, 'question-data')


# --- Database ---
# Writable database for user data (history, AI questions) stored in ~/.kubelingo/kubelingo.db
DATABASE_FILE = os.path.join(APP_DIR, 'kubelingo.db')
# Read-only backup of original questions. Used to seed the user's DB on first run.
BACKUP_DATABASE_FILE = os.path.join(PROJECT_ROOT, 'question-data-backup', 'kubelingo_original.db')


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


# --- Quiz Data Files ---

# Built-in YAML-edit quiz data files are stored in the question-data 'yaml' directory.
YAML_QUIZ_DIR = os.path.join(DATA_DIR, 'yaml')
# Default YAML quiz file for editing mode
YAML_QUESTIONS_FILE = os.path.join(YAML_QUIZ_DIR, 'yaml_exercises_quiz.yaml')
YAML_QUIZ_BACKUP_DIR = os.path.join(DATA_DIR, 'yaml-bak')
MANIFESTS_QUIZ_DIR = os.path.join(DATA_DIR, 'manifests')
# Default JSON quiz file for command quiz mode (legacy loader)
DEFAULT_DATA_FILE = os.path.join(DATA_DIR, 'json', 'kubernetes.json')


# --- Enabled Quizzes ---
# Quizzes that appear as primary options in the interactive menu, grouped by theme.
# The file paths are used as unique identifiers to query the database.
# Foundational concepts, vim, and shell usage.
BASIC_QUIZZES = {
    "Vim Practice": os.path.join(YAML_QUIZ_DIR, 'vim_quiz.yaml'),
    "Syntax & Shell Setup": os.path.join(YAML_QUIZ_DIR, 'kubectl_basic_syntax_quiz.yaml'),
    "General Operations": os.path.join(YAML_QUIZ_DIR, 'kubectl_operations_quiz.yaml'),
    "Resource Types Reference": os.path.join(YAML_QUIZ_DIR, 'kubectl_resource_types.yaml'),
}

# All kubectl and other command-line tool quizzes.
COMMAND_QUIZZES = {
    "Helm Basics": os.path.join(YAML_QUIZ_DIR, 'helm_basics_quiz.yaml'),
    "Pod Management": os.path.join(YAML_QUIZ_DIR, 'kubectl_pod_management_quiz.yaml'),
    "Deployment Management": os.path.join(YAML_QUIZ_DIR, 'kubectl_deployment_management_quiz.yaml'),
    "ConfigMap Operations": os.path.join(YAML_QUIZ_DIR, 'kubectl_configmap_operations_quiz.yaml'),
    "Secret Management": os.path.join(YAML_QUIZ_DIR, 'kubectl_secret_management_quiz.yaml'),
    "Namespace Operations": os.path.join(YAML_QUIZ_DIR, 'kubectl_namespace_operations_quiz.yaml'),
    "Service Account Operations": os.path.join(YAML_QUIZ_DIR, 'kubectl_service_account_operations.yaml'),
    "Additional Commands": os.path.join(YAML_QUIZ_DIR, 'kubectl_additional_commands_quiz.yaml'),
}

# Creating and editing YAML manifests.
MANIFEST_QUIZZES = {
    "YAML Editing Practice (General)": os.path.join(YAML_QUIZ_DIR, 'yaml_exercises_quiz.yaml'),
    "YAML Editing Practice (Pods)": os.path.join(MANIFESTS_QUIZ_DIR, 'pods_manifests.yaml'),
    "YAML Editing Practice (Deployments)": os.path.join(MANIFESTS_QUIZ_DIR, 'deployments_manifests.yaml'),
    "YAML Editing Practice (ConfigMaps)": os.path.join(MANIFESTS_QUIZ_DIR, 'configmaps_manifests.yaml'),
    "YAML Editing Practice (Services)": os.path.join(MANIFESTS_QUIZ_DIR, 'services_manifests.yaml'),
}
  
# Comprehensive multi-topic and AI-generated quiz sets
COMPREHENSIVE_QUIZZES = {
    "AI Generated Quiz": os.path.join(YAML_QUIZ_DIR, 'ai_generated_quiz.yaml'),
    "Kubernetes With Explanations": os.path.join(YAML_QUIZ_DIR, 'kubernetes_with_explanations.yaml'),
    "Master Quiz With Explanations": os.path.join(YAML_QUIZ_DIR, 'master_quiz_with_explanations.yaml'),
}

# --- Enabled Quizzes (legacy alias for interactive menus and CLI fallback) ---
# Combines all quiz groups for backward compatibility
ENABLED_QUIZZES = {}
ENABLED_QUIZZES.update(BASIC_QUIZZES)
ENABLED_QUIZZES.update(COMMAND_QUIZZES)
ENABLED_QUIZZES.update(MANIFEST_QUIZZES)
ENABLED_QUIZZES.update(COMPREHENSIVE_QUIZZES)

# CSV files
CSV_DIR = os.path.join(DATA_DIR, 'csv')
# Killercoda CKAD CSV quiz file
KILLERCODA_CSV_FILE = os.path.join(CSV_DIR, 'killercoda-ckad_072425.csv')
KILLERCODA_CSV_FILE = os.path.join(CSV_DIR, 'killercoda-ckad_072425.csv')

# --- History and Logging ---
HISTORY_FILE = os.path.join(LOGS_DIR, '.cli_quiz_history.json')
INPUT_HISTORY_FILE = os.path.join(LOGS_DIR, '.kubelingo_input_history')
VIM_HISTORY_FILE = os.path.join(LOGS_DIR, '.kubelingo_vim_history')
LOG_FILE = os.path.join(LOGS_DIR, 'quiz_log.txt')
# Store for flagged question IDs (decoupled from quiz source files)
FLAGGED_QUESTIONS_FILE = os.path.join(LOGS_DIR, 'flagged_questions.json')
