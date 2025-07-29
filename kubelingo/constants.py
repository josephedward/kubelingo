"""
Centralized constants for the Kubelingo application.
"""
import os

# Base directory for the project
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

# Data and logging directories
DATA_DIR = os.path.join(ROOT, 'question-data')
LOGS_DIR = os.path.join(ROOT, 'logs')

# --- Quiz Data Files ---

# JSON files
JSON_DIR = os.path.join(DATA_DIR, 'json')
DEFAULT_DATA_FILE = os.path.join(JSON_DIR, 'ckad_quiz_data.json')
YAML_QUESTIONS_FILE = os.path.join(JSON_DIR, 'yaml_edit_questions.json')
VIM_QUESTIONS_FILE = os.path.join(JSON_DIR, 'vim_quiz_data.json')

# CSV files
CSV_DIR = os.path.join(DATA_DIR, 'csv')
KILLERCODA_CSV_FILE = os.path.join(CSV_DIR, 'killercoda-ckad_072425.csv')

# --- History and Logging ---
HISTORY_FILE = os.path.join(LOGS_DIR, '.cli_quiz_history.json')
INPUT_HISTORY_FILE = os.path.join(LOGS_DIR, '.kubelingo_input_history')
VIM_HISTORY_FILE = os.path.join(LOGS_DIR, '.kubelingo_vim_history')
LOG_FILE = os.path.join(LOGS_DIR, 'quiz_log.txt')
