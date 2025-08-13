import os
from abc import ABC, abstractmethod
import logging
from typing import Optional

from kubelingo.utils.config import get_ai_provider

try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    import openai
except ImportError:
    openai = None


class LLMClient(ABC):
    """Abstract base class for a client that interacts with a Large Language Model."""

    @abstractmethod
    def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        json_mode: bool = False,
    ) -> Optional[str]:
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Tests the connection to the LLM provider to validate the API key."""
        pass


class OpenAIClient(LLMClient):
    """LLM client for OpenAI models."""

    def __init__(self):
        if openai is None:
            raise ImportError(
                "The 'openai' package is required to use OpenAIClient. "
                "Please install it with 'pip install openai'."
            )
        from kubelingo.utils.config import get_openai_api_key

        api_key = get_openai_api_key()
        if not api_key:
            raise ValueError(
                "OpenAI API key is not set in config or OPENAI_API_KEY environment variable."
            )

        self.client = openai.OpenAI(api_key=api_key)

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        json_mode: bool = False,
    ) -> Optional[str]:
        """Sends a chat completion request to the OpenAI API."""
        params = {
            "model": "gpt-4-turbo",
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            params["response_format"] = {"type": "json_object"}

        try:
            response = self.client.chat.completions.create(**params)
            content = response.choices[0].message.content
            return content
        except Exception as e:
            logging.error(f"OpenAI API request failed: {e}", exc_info=True)
            raise

    def test_connection(self) -> bool:
        """Tests the connection to the OpenAI API by making a minimal request."""
        try:
            # Listing models is a lightweight way to check auth
            self.client.models.list()
            return True
        except openai.AuthenticationError:
            logging.warning("OpenAI API key is invalid.")
            return False
        except Exception as e:
            logging.error(f"Failed to connect to OpenAI: {e}")
            return False


class GeminiClient(LLMClient):
    """LLM client for Google Gemini models."""

    def __init__(self):
        if genai is None:
            raise ImportError(
                "The 'google-generativeai' package is required to use GeminiClient. "
                "Please install it with 'pip install google-generativeai'."
            )
        from kubelingo.utils.config import get_gemini_api_key

        api_key = get_gemini_api_key()
        if not api_key:
            raise ValueError(
                "Gemini API key not found in config file or GEMINI_API_KEY environment variable."
            )

        genai.configure(api_key=api_key)

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        json_mode: bool = False,
    ) -> Optional[str]:
        """Sends a chat completion request to the Gemini API."""
        local_messages = list(messages)  # Make a copy to avoid mutation
        system_prompt = ""
        if local_messages and local_messages[0]["role"] == "system":
            system_prompt = local_messages.pop(0)["content"]

        # Convert message history to Gemini's format.
        gemini_messages = []
        for message in local_messages:
            role = "model" if message["role"] == "assistant" else "user"
            gemini_messages.append({"role": role, "parts": [message["content"]]})

        try:
            model = genai.GenerativeModel(
                "gemini-1.5-pro-latest", system_instruction=system_prompt
            )
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                response_mime_type="application/json" if json_mode else "text/plain",
            )
            response = model.generate_content(
                gemini_messages,
                generation_config=generation_config,
            )
            return response.text
        except Exception as e:
            logging.error(f"Gemini API request failed: {e}", exc_info=True)
            raise  # Re-raise for the caller to handle

    def test_connection(self) -> bool:
        """Tests the connection to the Gemini API by listing available models."""
        try:
            # Listing models is a lightweight way to check auth
            genai.list_models()
            return True
        except Exception as e:
            # The google-generativeai library can raise a generic Exception for auth errors
            logging.warning(f"Gemini API key appears to be invalid. Error: {e}")
            return False


def get_llm_client() -> LLMClient:
    """
    Factory function to get an LLM client instance based on user configuration.

    Returns:
        LLMClient: An instance of the requested LLM client.
    """
    provider = get_ai_provider()
    if provider == "gemini":
        return GeminiClient()
    elif provider == "openai":
        return OpenAIClient()
    else:
        raise ValueError(f"Unsupported LLM client type in configuration: {provider}")
