import pytest
import os
from unittest.mock import MagicMock, patch
from cli import ai_chat

@patch('requests.post')
def test_ai_chat_gemini_url(mock_post, monkeypatch):
    """
    Tests that the ai_chat function constructs the correct Gemini API URL,
    ignoring any environment variables.
    """
    # Arrange
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")
    # Set dummy old environment variables to ensure they are ignored
    monkeypatch.setenv("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta2")
    monkeypatch.setenv("GEMINI_MODEL", "chat-bison-001")
    monkeypatch.setenv("KUBELINGO_LLM_PROVIDER", "gemini")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": "This is a test response."
                        }
                    ]
                }
            }
        ]
    }
    mock_post.return_value = mock_response

    # Act
    ai_chat("system prompt", "user prompt")

    # Assert
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    url = args[0]
    assert url == "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key=test-api-key"

@patch('requests.post')
def test_ai_chat_gemini_payload(mock_post, monkeypatch):
    """
    Tests that the ai_chat function constructs the correct Gemini API payload,
    merging messages and using generationConfig.
    """
    # Arrange
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")
    monkeypatch.setenv("KUBELINGO_LLM_PROVIDER", "gemini")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": "This is a test response."
                        }
                    ]
                }
            }
        ]
    }
    mock_post.return_value = mock_response

    system_prompt = "You are a helpful assistant."
    user_prompt = "What is Kubernetes?"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    # Act
    ai_chat(messages)

    # Assert
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    payload = kwargs["json"]
    
    # Check that messages are merged
    expected_prompt = "You are a helpful assistant.\n\nWhat is Kubernetes?"
    assert payload["contents"][0]["role"] == "user"
    assert payload["contents"][0]["parts"][0]["text"] == expected_prompt
    
    # Check for generationConfig
    assert "generationConfig" in payload
    assert "temperature" in payload["generationConfig"]

def test_ai_chat_no_api_key(monkeypatch, capsys):
    """
    Tests that ai_chat returns an error and empty string when no API keys are set.
    """
    # Arrange: Ensure no API keys are set
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("KUBELINGO_LLM_PROVIDER", raising=False)

    # Act
    result = ai_chat("system prompt", "user prompt")

    # Assert
    captured = capsys.readouterr()
    assert "Error: No LLM provider configured. Please set one in Settings." in captured.out
    assert result == ""

@patch('requests.post')
def test_ai_chat_openrouter_url(mock_post, monkeypatch):
    """
    Tests that the ai_chat function constructs the correct OpenRouter API URL.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-or-key")
    monkeypatch.setenv("KUBELINGO_LLM_PROVIDER", "openrouter")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"choices": [{"message": {"content": "OK"}}]}
    mock_post.return_value = mock_response

    ai_chat("system prompt", "user prompt")
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    url = args[0]
    assert url == "https://openrouter.ai/api/v1/chat/completions"

@patch('requests.post')
def test_ai_chat_openrouter_payload(mock_post, monkeypatch):
    """
    Tests that the ai_chat function constructs the correct OpenRouter API payload and headers.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-or-key")
    monkeypatch.setenv("KUBELINGO_LLM_PROVIDER", "openrouter")
    system_prompt = "System"
    user_prompt = "User"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"choices": [{"message": {"content": "OK"}}]}
    mock_post.return_value = mock_response

    ai_chat(system_prompt, user_prompt)
    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    payload = kwargs.get("json", {})
    headers = kwargs.get("headers", {})
    assert payload.get("model") == os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-r1-0528:free")
    assert payload.get("messages") == [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    assert "temperature" in payload
    assert headers.get("Authorization") == "Bearer test-or-key"
    assert headers.get("Content-Type") == "application/json"
