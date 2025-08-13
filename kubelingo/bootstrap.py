import getpass
import logging
import sqlite3
import sys
from pathlib import Path

import questionary
import yaml

from kubelingo.database import add_question, get_db_connection, init_db
from kubelingo.integrations.llm import GeminiClient, OpenAIClient
from kubelingo.modules.ai_categorizer import AICategorizer
from kubelingo.utils.config import (
    get_api_key,
    save_ai_provider,
    save_api_key,
)
from kubelingo.utils.path_utils import find_and_sort_files_by_mtime, get_project_root
from kubelingo.utils.ui import Fore, Style

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def _ensure_provider_is_set():
    """
    Checks if an AI provider is configured, prompting the user to select one
    if not. This is intended for interactive startup.
    """
    # Only run this interactive setup if in a TTY.
    if not sys.stdout.isatty():
        return

    from kubelingo.utils.config import get_ai_provider, save_ai_provider

    provider = get_ai_provider()

    if not provider:
        selected_provider = questionary.select(
            "Please select an AI provider for feedback and study features:",
            choices=[
                {"name": "Gemini", "value": "gemini"},
                {"name": "OpenAI", "value": "openai"},
            ],
        ).ask()

        if selected_provider:
            save_ai_provider(selected_provider)
            print(f"AI provider set to {selected_provider.capitalize()}.")
        # If user cancels (returns None), we do nothing and let the app continue.
        # The key check in the CLI will handle the messaging.


def initialize_app():
    """
    Performs all necessary startup tasks for the application, including
    API key checks and database schema initialization.
    """
    _ensure_provider_is_set()
    init_db()


