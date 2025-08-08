import os
from typing import Optional

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

# Data directories for built-in quiz files are located at the project root
PROJECT_ROOT = os.path.abspath(os.path.join(PACKAGE_ROOT, os.pardir))
DATA_DIR = os.path.join(PROJECT_ROOT, 'question-data')


# --- Database ---
# Writable database for user data (history, AI questions) stored in ~/.kubelingo/kubelingo.db
DATABASE_FILE = os.path.join(APP_DIR, 'kubelingo.db')
# Read-only backup of original questions. Used to seed the user's DB on first run.
BACKUP_DATABASE_FILE = os.path.join(PROJECT_ROOT, 'question-data-backup', 'kubelingo_original.db')


# --- API Keys ---
API_KEY_FILE = os.path.join(APP_DIR, 'api_key')


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


# --- Quiz Data Files ---

# Built-in YAML-edit quiz data files are stored in the question-data 'yaml' directory.
YAML_QUIZ_DIR = os.path.join(DATA_DIR, 'yaml')
YAML_QUIZ_BACKUP_DIR = os.path.join(DATA_DIR, 'yaml-bak')


# --- Enabled Quizzes ---
# Quizzes that appear as primary options in the interactive menu.
# The file paths are used as unique identifiers to query the database.
ENABLED_QUIZZES = {
    "Vim Quiz": os.path.join(YAML_QUIZ_DIR, 'vim_quiz.yaml'),
    "YAML Editing": os.path.join(YAML_QUIZ_DIR, 'yaml_exercises_quiz.yaml'),
    "Kubectl Basic Syntax": os.path.join(YAML_QUIZ_DIR, 'kubectl_basic_syntax_quiz.yaml'),
    "Kubectl Operations": os.path.join(YAML_QUIZ_DIR, 'kubectl_operations_quiz.yaml'),
    "Kubectl Resource Types": os.path.join(YAML_QUIZ_DIR, 'kubectl_resource_types.yaml'),
    "Helm Basics": os.path.join(YAML_QUIZ_DIR, 'helm_basics_quiz.yaml'),
    "Kubectl Shell Setup": os.path.join(YAML_QUIZ_DIR, 'kubectl_shell_setup_quiz.yaml'),
    "Kubectl Pod Management": os.path.join(YAML_QUIZ_DIR, 'kubectl_pod_management_quiz.yaml'),
    "Kubectl Deployment Management": os.path.join(YAML_QUIZ_DIR, 'kubectl_deployment_management_quiz.yaml'),
    "Kubectl Namespace Operations": os.path.join(YAML_QUIZ_DIR, 'kubectl_namespace_operations_quiz.yaml'),
    "Kubectl ConfigMap Operations": os.path.join(YAML_QUIZ_DIR, 'kubectl_configmap_operations_quiz.yaml'),
    "Kubectl Secret Management": os.path.join(YAML_QUIZ_DIR, 'kubectl_secret_management_quiz.yaml'),
    "Kubectl Service Account Operations": os.path.join(YAML_QUIZ_DIR, 'kubectl_service_account_ops_quiz.yaml'),
    "Kubectl Additional Commands": os.path.join(YAML_QUIZ_DIR, 'kubectl_additional_commands_quiz.yaml'),
}

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
