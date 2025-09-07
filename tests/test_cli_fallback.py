import json
import pytest
import requests

import kubelingo.cli as cli
import kubelingo.llm_utils as llm_utils


class DummyPrompt:
    """Simple dummy to simulate InquirerPy prompt execution."""
    def __init__(self, value):
        self.value = value
    def execute(self):
        return self.value


@pytest.fixture(autouse=True)
def reset_last_generated_q(monkeypatch):
    # Reset state before each test
    cli.last_generated_q = None
    yield
    cli.last_generated_q = None


def test_generate_trivia_ai_fallback_message(monkeypatch, capsys):
    """
    When ai_chat returns non-JSON, generate_trivia should print a generic fallback message
    and not include any provider-specific name.
    """
    # Simulate user selecting quiz type, topic, difficulty, and number of questions
    select_choices = iter([
        "True/False",  # Quiz type
        "pods"        # Topic
    ])
    monkeypatch.setattr(cli.inquirer, 'select', lambda message, choices, default=None, style=None: DummyPrompt(next(select_choices)))
    monkeypatch.setattr(cli.inquirer, 'text', lambda message: DummyPrompt("1")) # Number of questions

    # Simulate ai_chat returning an empty string (failure to parse)
    monkeypatch.setattr(llm_utils, 'ai_chat', lambda *args, **kwargs: "")

    # Simulate answering 'q' to exit quiz session
    monkeypatch.setattr(cli, 'post_answer_menu', lambda: 'q')

    # Run the quiz menu
    cli.quiz_menu()
    # Capture output
    captured = capsys.readouterr().out
    # Expect generic fallback message
    assert "AI generation failed. Please try the stored quiz mode via 'Stored' option." in captured
    # Should not mention any provider name such as 'gemini' or 'openai'
    lower = captured.lower()
    assert 'gemini' not in lower
    assert 'openai' not in lower


@pytest.mark.parametrize("provider_key,provider", [
    ("GEMINI_API_KEY", "gemini"),
    ("OPENAI_API_KEY", "openai"),
    ("OPENROUTER_API_KEY", "openrouter"),
])
def test_ai_chat_error_generic(monkeypatch, capsys, provider_key, provider):
    """
    ai_chat should print a generic error message without embedding the provider name
    """
    # Set only the given provider key
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    monkeypatch.setenv(provider_key, 'dummy_key')
    # Ensure provider selection falls to this key
    monkeypatch.delenv('KUBELINGO_LLM_PROVIDER', raising=False)
    # Monkeypatch requests.post to raise an HTTP error
    class FakeResp:
        def raise_for_status(self):
            raise Exception('HTTP Error')
    def fake_post(*args, **kwargs):
        return FakeResp()
    monkeypatch.setattr(requests, 'post', fake_post)
    # Call ai_chat
    result = llm_utils.ai_chat('system prompt', 'user prompt')
    # Should return empty string on failure
    assert result == ""
    out = capsys.readouterr().out
    # Should print generic 'AI request failed:' message
    assert 'ai request failed:' in out.lower()
    # Provider name should not appear in the printed message
    assert provider not in out.lower()


def test_generate_trivia_ai_malformed_json_fallback(monkeypatch, capsys):
    """
    When ai_chat returns malformed JSON, generate_trivia should print the AI generation failed message.
    """
    # Simulate user selecting quiz type, topic, difficulty, and number of questions
    select_choices = iter([
        "True/False",  # Quiz type
        "pods"        # Topic
    ])
    monkeypatch.setattr(cli.inquirer, 'select', lambda message, choices, default=None, style=None: DummyPrompt(next(select_choices)))
    monkeypatch.setattr(cli.inquirer, 'text', lambda message: DummyPrompt("1")) # Number of questions

    # Simulate ai_chat returning malformed JSON
    monkeypatch.setattr(llm_utils, 'ai_chat', lambda *args, **kwargs: "{invalid_json")

    # Simulate answering 'q' to exit quiz session
    monkeypatch.setattr(cli, 'post_answer_menu', lambda: 'q')

    # Run the quiz menu
    cli.quiz_menu()

    # Capture output
    captured = capsys.readouterr().out

    # Assert that the AI generation failed message is present
    assert "AI generation failed. Please try the stored quiz mode via 'Stored' option." in captured