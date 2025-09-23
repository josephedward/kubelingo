import os
import pytest
from kubelingo.kubelingo import check_ai_ready_for_generation

def test_check_ai_ready_for_generation_with_env_file(monkeypatch, tmp_path):
    """
    Tests that check_ai_ready_for_generation() works correctly
    even if load_dotenv() has not been explicitly called by the caller.
    """
    # 1. Create a temporary .env file
    env_content = '''KUBELINGO_LLM_PROVIDER="openai"
OPENAI_API_KEY="sk-proj-12345678901234567890123456789012"
'''
    env_file = tmp_path / ".env"
    env_file.write_text(env_content)

    # 2. Change to the temporary directory
    monkeypatch.chdir(tmp_path)

    # 3. Unset environment variables to simulate a clean start
    monkeypatch.delenv("KUBELINGO_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    # 4. Call the function and assert it returns True
    is_ready, msg = check_ai_ready_for_generation(print_warnings=False)
    assert is_ready is True, f"check_ai_ready_for_generation failed: {msg}"

