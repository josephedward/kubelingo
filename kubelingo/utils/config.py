import os
import json
from typing import Optional, Dict, Any, List
from pathlib import Path

# The absolute path to the project root directory, which contains the 'kubelingo' package and 'scripts'.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# The root of the package (package directory)
PACKAGE_ROOT = os.path.join(PROJECT_ROOT, 'kubelingo')
# Legacy alias for backward compatibility: now points to project root
ROOT = PROJECT_ROOT

# Shared context file for all agents: fundamental exercise categories
SHARED_CONTEXT_FILE = os.path.join(PROJECT_ROOT, 'shared_context.md')

# By default use project-local .kubelingo directory to ensure write access
APP_DIR = os.path.join(PROJECT_ROOT, ".kubelingo")
# Backup directory for timestamped DB snapshots
BACKUP_DIR = os.path.join(APP_DIR, "backups")
# Consolidated database files
CATEGORIZED_DB = os.path.join(APP_DIR, "categorized.db")
BACKUP_QUESTIONS_DB = os.path.join(APP_DIR, "backup_questions.db")
# Logs directory located within the project root
LOGS_DIR = os.path.join(PROJECT_ROOT, 'logs')
try:
    os.makedirs(LOGS_DIR, exist_ok=True)
except Exception:
    # Could not create directories (permissions?), ignore
    pass

# The single, consolidated directory for all question data. This can be overridden by
# the KUBELINGO_QUESTIONS_DIR environment variable to allow using an external
# question data repository. The build_question_db.py script will use this as the sole source.
QUESTIONS_DIR = os.getenv('KUBELINGO_QUESTIONS_DIR') or os.path.join(PROJECT_ROOT, 'yaml')

# The single source of truth for all questions.
# The user can override this with an environment variable.
SINGLE_SOURCE_YAML_FILE = os.getenv(
    'KUBELINGO_YAML_SOURCE',
    os.path.join(QUESTIONS_DIR, 'consolidated_20250811_144940.yaml')
)


# --- Pathfinding & Discovery Configuration ---
# These lists define candidate directories for scripts to scan, making the project
# more resilient to file reorganization. They are used by helpers in `kubelingo.utils.path_utils`.

# Candidate directories for question sources (YAML/YML files).
# This now merges the former QUESTION_SOURCE_DIRS and QUESTION_DIRS
QUESTION_DIRS = [QUESTIONS_DIR]

# Candidate directories for YAML backup files.
YAML_BACKUP_DIRS = [
    os.path.join(PROJECT_ROOT, 'backups', 'yaml'),
]

# Candidate directories for SQLite database backups (timestamped '.db' files).
SQLITE_BACKUP_DIRS = [
    BACKUP_DIR,
]


# --- Database ---
def get_latest_db_path() -> Optional[str]:
    """Finds the most recent 'kubelingo_metadata_*.db' file in the project root."""
    project_root_path = Path(PROJECT_ROOT)
    db_files = list(project_root_path.glob("kubelingo_metadata_*.db"))
    if not db_files:
        # Fallback to the default app dir if no bootstrapped DB is found
        return os.path.join(APP_DIR, 'kubelingo.db')
    # Sort by modification time descending to get the latest
    latest_db = max(db_files, key=lambda p: p.stat().st_mtime)
    return str(latest_db)

# The canonical path to the database file is now determined dynamically.
DATABASE_FILE = get_latest_db_path()


def get_live_db_path() -> str:
    """Helper function to return the canonical path to the live user database."""
    # Always re-evaluate to find the latest DB, in case a new one was just created.
    return get_latest_db_path()


# Read-only master backup of original questions. Used to seed the user's DB on first run.
# DEPRECATED: Database is now built from a single YAML source file.
MASTER_DATABASE_FILE = None
# Secondary backup for redundancy (fallback).
# DEPRECATED: Database is now built from a single YAML source file.
SECONDARY_MASTER_DATABASE_FILE = None


# --- API Keys & Provider ---
SUPPORTED_AI_PROVIDERS = ['gemini', 'openai']
AI_PROVIDER_FILE = os.path.join(APP_DIR, 'ai_provider')


# --- Cluster Configuration ---
CLUSTER_CONFIG_FILE = os.path.join(APP_DIR, 'clusters.json')


def _get_api_key_file_path(provider: str) -> str:
    """Returns the path to the API key file for a given provider."""
    return os.path.join(APP_DIR, f'api_key_{provider.lower()}')


def save_api_key(provider: str, key: str) -> bool:
    """Saves an API key for a given provider to its config file."""
    key_file = _get_api_key_file_path(provider)
    try:
        os.makedirs(APP_DIR, mode=0o700, exist_ok=True)
        with open(key_file, 'w', encoding='utf-8') as f:
            f.write(key.strip())
        os.chmod(key_file, 0o600)
        return True
    except Exception:
        return False


def get_api_key(provider: str) -> Optional[str]:
    """
    Retrieves the API key for a given provider, checking the config file first,
    then the corresponding environment variable (e.g., OPENAI_API_KEY).
    """
    key, _ = get_api_key_with_source(provider)
    return key


def get_api_key_with_source(provider: str) -> tuple[Optional[str], Optional[str]]:
    """
    Retrieves the API key and its source for a given provider.

    Returns:
        A tuple containing the key and its source ('file', 'env', or None).
    """
    key_file = _get_api_key_file_path(provider)
    if os.path.exists(key_file):
        try:
            with open(key_file, 'r', encoding='utf-8') as f:
                key = f.read().strip()
                if key:
                    return key, 'file'
        except Exception:
            pass
    # Fallback to environment variable
    env_var_name = f"{provider.upper()}_API_KEY"
    key = os.getenv(env_var_name)
    if key:
        return key, 'env'
    return None, None


def save_ai_provider(provider: str) -> bool:
    """Saves the selected AI provider to the config file."""
    try:
        os.makedirs(APP_DIR, mode=0o700, exist_ok=True)
        with open(AI_PROVIDER_FILE, 'w', encoding='utf-8') as f:
            f.write(provider.strip())
        os.chmod(AI_PROVIDER_FILE, 0o600)
        return True
    except Exception:
        return False


def get_ai_provider() -> Optional[str]:
    """Retrieves the selected AI provider."""
    if os.path.exists(AI_PROVIDER_FILE):
        try:
            with open(AI_PROVIDER_FILE, 'r', encoding='utf-8') as f:
                provider = f.read().strip()
                if provider in SUPPORTED_AI_PROVIDERS:
                    return provider
        except Exception:
            pass
    # No default, return None if not set
    return None


def get_active_api_key() -> Optional[str]:
    """Retrieves the API key for the currently configured AI provider."""
    provider = get_ai_provider()
    if provider:
        return get_api_key(provider)
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
