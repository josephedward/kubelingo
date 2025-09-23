import os
import pytest
from dotenv import load_dotenv
from kubelingo.kubelingo import check_ai_ready_for_generation

def test_check_ai_ready_with_env_file(tmp_path):
    """
    Tests that check_ai_ready_for_generation correctly identifies a configured provider
    when the configuration is in a .env file.
    """
    # Create a .env file in a temporary directory
    env_content = """
KUBELINGO_LLM_PROVIDER=openai
OPENAI_API_KEY=sk-proj-123456789012345678901234567890123456789012345678
"""
    env_file = tmp_path / ".env"
    env_file.write_text(env_content)

    # Change the current directory to the temporary directory
    # so that load_dotenv() can find the .env file.
    original_cwd = os.getcwd()
    os.chdir(tmp_path)

    # Load the .env file
    load_dotenv()

    # Run the check
    is_ready, message = check_ai_ready_for_generation(print_warnings=False)

    # Go back to the original directory
    os.chdir(original_cwd)

    # Assert that the check passes
    assert is_ready is True, f"check_ai_ready_for_generation failed with message: {message}"
