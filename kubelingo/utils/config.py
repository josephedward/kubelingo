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
# Directory for user-specific app files (e.g., database)
APP_DIR = os.path.join(HOME_DIR, ".kubelingo")
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



# --- Legacy Data Directories (used ONLY by the consolidation script) ---
# These paths are preserved to allow the one-time consolidation script to find the old files.
# They are not used by the main application or build script.
YAML_QUIZ_DIR = os.path.join(DATA_DIR, 'yaml')
YAML_QUESTIONS_FILE = os.path.join(YAML_QUIZ_DIR, 'yaml_exercises_quiz.yaml')

# --- Interactive Quiz Modules ---
# Definitions for organizing quizzes into menu groups.
BASIC_QUIZZES = {
    "Vim Practice": os.path.join(QUESTIONS_DIR, 'vim_practice.yaml'),
    "General Operations": os.path.join(QUESTIONS_DIR, 'general_operations.yaml'),
    "Resource Types Reference": os.path.join(QUESTIONS_DIR, 'resource_types_reference.yaml'),
}
COMMAND_QUIZZES = {
    "Syntax & Shell Setup": os.path.join(QUESTIONS_DIR, 'syntax_shell_setup.yaml'),
    "Helm Basics": os.path.join(QUESTIONS_DIR, 'helm_basics.yaml'),
    "Pod Management": os.path.join(QUESTIONS_DIR, 'pod_management.yaml'),
    "Deployment Management": os.path.join(QUESTIONS_DIR, 'deployment_management.yaml'),
    "ConfigMap Operations": os.path.join(QUESTIONS_DIR, 'configmap_operations.yaml'),
    "Secret Management": os.path.join(QUESTIONS_DIR, 'secret_management.yaml'),
    "Namespace Operations": os.path.join(QUESTIONS_DIR, 'namespace_operations.yaml'),
    "Service Account Operations": os.path.join(QUESTIONS_DIR, 'service_account_operations.yaml'),
    "Additional Commands": os.path.join(QUESTIONS_DIR, 'additional_commands.yaml'),
}
MANIFEST_QUIZZES = {
    "YAML Editing Practice": os.path.join(QUESTIONS_DIR, 'yaml_editing_practice.yaml'),
}
## Aggregate all enabled quizzes for interactive selection
ENABLED_QUIZZES = {**BASIC_QUIZZES, **COMMAND_QUIZZES, **MANIFEST_QUIZZES}
# --- Database ---
# Writable database for user data (history, AI questions) stored in ~/.kubelingo/kubelingo.db
DATABASE_FILE = os.path.join(APP_DIR, 'kubelingo.db')
# Read-only master backup of original questions. Used to seed the user's DB on first run.
MASTER_DATABASE_FILE = os.path.join(PROJECT_ROOT, 'question-data-backup', 'kubelingo_original.db')
# Secondary backup for redundancy (fallback).
SECONDARY_MASTER_DATABASE_FILE = os.path.join(PROJECT_ROOT, 'question-data-backup', 'kubelingo.db')


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
