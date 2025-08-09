import os
import json
from typing import Optional, Dict, Any

# The absolute path to the project root directory, which contains the 'kubelingo' package and 'scripts'.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# The root of the package
PACKAGE_ROOT = os.path.join(PROJECT_ROOT, 'kubelingo')
# Legacy alias for backward compatibility
ROOT = PACKAGE_ROOT

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
DATA_DIR = os.path.join(PROJECT_ROOT, 'question-data')


# --- Database ---
# Writable database for user data (history, AI questions) stored in ~/.kubelingo/kubelingo.db
DATABASE_FILE = os.path.join(APP_DIR, 'kubelingo.db')
# Read-only master backup of original questions. Used to seed the user's DB on first run.
MASTER_DATABASE_FILE = os.path.join(PROJECT_ROOT, 'question-data-backup', 'kubelingo_master.db')
# Secondary backup for redundancy.
SECONDARY_MASTER_DATABASE_FILE = os.path.join(PROJECT_ROOT, 'question-data-backup', 'kubelingo_master.db.bak')
# Legacy alias for backward compatibility.
BACKUP_DATABASE_FILE = MASTER_DATABASE_FILE


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

# The canonical source for all question data is the collection of YAML files
# in this directory. The database is seeded from these files on first run.
# Directory for primary YAML quiz files
YAML_QUIZ_DIR = os.path.join(DATA_DIR, 'yaml')
# Backup directory for legacy YAML quiz files (optional)
YAML_QUIZ_BACKUP_DIR = ''
# Default YAML questions file for editing and unified quiz mode
# Default YAML questions file for editing and unified quiz mode
YAML_QUESTIONS_FILE = os.path.join(YAML_QUIZ_DIR, 'yaml_exercises_quiz.yaml')

# --- Interactive Quiz Modules ---
# Definitions for organizing quizzes into menu groups.
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
    "Service Account Operations": os.path.join(YAML_QUIZ_DIR, 'kubectl_service_account_ops_quiz.yaml'),
    "Additional Commands": os.path.join(YAML_QUIZ_DIR, 'kubectl_additional_commands_quiz.yaml'),
}

# Manifest-based quizzes: YAML editing exercises.
MANIFEST_QUIZZES = {
    "YAML Editing Exercises": os.path.join(YAML_QUIZ_DIR, 'yaml_exercises_quiz.yaml'),
    "YAML Quiz": os.path.join(YAML_QUIZ_DIR, 'yaml_quiz.yaml'),
}

# Combine all quizzes for the interactive menu.
ENABLED_QUIZZES = {}
ENABLED_QUIZZES.update(BASIC_QUIZZES)
ENABLED_QUIZZES.update(COMMAND_QUIZZES)
ENABLED_QUIZZES.update(MANIFEST_QUIZZES)

# CSV files
CSV_DIR = os.path.join(DATA_DIR, 'csv')
# Killercoda CKAD CSV quiz file
KILLERCODA_CSV_FILE = os.path.join(CSV_DIR, 'killercoda-ckad_072425.csv')

# --- History and Logging ---
HISTORY_FILE = os.path.join(LOGS_DIR, '.cli_quiz_history.json')
INPUT_HISTORY_FILE = os.path.join(LOGS_DIR, '.kubelingo_input_history')
VIM_HISTORY_FILE = os.path.join(LOGS_DIR, '.kubelingo_vim_history')
LOG_FILE = os.path.join(LOGS_DIR, 'quiz_log.txt')
# Store for flagged question IDs (decoupled from quiz source files)
FLAGGED_QUESTIONS_FILE = os.path.join(LOGS_DIR, 'flagged_questions.json')
