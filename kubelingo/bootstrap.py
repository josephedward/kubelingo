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


def _check_api_keys():
    """Checks for API keys and prompts if none are configured."""
    # Check if at least one key is already set
    if get_api_key('gemini') or get_api_key('openai'):
        return

    print(f"\n{Fore.YELLOW}--- Welcome to Kubelingo ---{Style.RESET_ALL}")
    print("AI-powered features like Socratic study mode require an API key.")
    print("You can get a key from Google AI Studio (for Gemini) or OpenAI.")
    print("")

    if questionary.confirm("Would you like to set up an API key now?", default=True).ask():
        # Prompt for Gemini
        gemini_key = getpass.getpass("Enter your Gemini API key (or press Enter to skip): ").strip()
        if gemini_key:
            if GeminiClient.test_key(gemini_key):
                save_api_key('gemini', gemini_key)
                print(f"{Fore.GREEN}✓ Gemini API key is valid and has been saved.{Style.RESET_ALL}")
                save_ai_provider('gemini')  # Set as default provider
                return  # Exit after successful configuration
            else:
                print(f"{Fore.RED}✗ The Gemini API key provided is not valid.{Style.RESET_ALL}")

        # Prompt for OpenAI if Gemini was skipped or failed
        openai_key = getpass.getpass("Enter your OpenAI API key (or press Enter to skip): ").strip()
        if openai_key:
            if OpenAIClient.test_key(openai_key):
                save_api_key('openai', openai_key)
                print(f"{Fore.GREEN}✓ OpenAI API key is valid and has been saved.{Style.RESET_ALL}")
                save_ai_provider('openai')  # Set as default provider
            else:
                print(f"{Fore.RED}✗ The OpenAI API key provided is not valid.{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.YELLOW}No API key was configured. Some AI features may be disabled.{Style.RESET_ALL}")
            print(f"You can set one up later in the {Fore.CYAN}Settings -> API Keys{Style.RESET_ALL} menu.")
    else:
        print(f"\n{Fore.YELLOW}No API key was configured. Some AI features may be disabled.{Style.RESET_ALL}")
        print(f"You can set one up later in the {Fore.CYAN}Settings -> API Keys{Style.RESET_ALL} menu.")

    print("-" * 30 + "\n")


def initialize_app():
    """
    Performs all necessary startup tasks for the application, including
    API key checks and database schema initialization.
    """
    _check_api_keys()
    init_db()


