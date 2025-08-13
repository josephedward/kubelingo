import pytest

from kubelingo.integrations.llm import GeminiClient
from kubelingo.utils.config import get_api_key

# A decorator to skip tests if the gemini API key is not available
skip_if_no_gemini_key = pytest.mark.skipif(
    not get_api_key("gemini"),
    reason="Gemini API key not found. Set GEMINI_API_KEY environment variable.",
)


@skip_if_no_gemini_key
def test_gemini_client_connection():
    """
    Tests that the GeminiClient can successfully connect to the API.
    This is an integration test and requires a valid GEMINI_API_KEY.
    """
    client = GeminiClient()
    assert client.test_connection() is True


@skip_if_no_gemini_key
def test_gemini_chat_completion():
    """
    Tests that the GeminiClient can get a chat completion.
    This is an integration test and requires a valid GEMINI_API_KEY.
    """
    client = GeminiClient()
    messages = [{"role": "user", "content": "what is 1+1?"}]
    response = client.chat_completion(messages)
    assert response is not None, "The response from chat_completion was None."
    assert isinstance(response, str), f"Expected a string response, but got {type(response)}"
    assert "2" in response, f"Expected '2' in response text, but got: {response}"
