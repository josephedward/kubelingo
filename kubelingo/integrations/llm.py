import logging
from abc import ABC, abstractmethod
from typing import Optional

from kubelingo.utils.config import get_ai_provider

try:
    import llm
except ImportError:
    llm = None


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
    """LLM client for OpenAI models, using the `llm` library."""

    @staticmethod
    def test_key(key: str) -> bool:
        """Tests an OpenAI API key without creating a client instance."""
        if not llm:
            return False
        try:
            model = llm.get_model("gpt-3.5-turbo")
            model.key = key
            # A short prompt to test the key
            response = model.prompt("test")
            return bool(response.text)
        except Exception:
            return False

    def __init__(self):
        if llm is None:
            raise ImportError(
                "The 'llm' and 'llm-openai' packages are required. "
                "Please install with 'pip install llm llm-openai'."
            )
        from kubelingo.utils.config import get_openai_api_key

        api_key = get_openai_api_key()
        if not api_key:
            raise ValueError(
                "OpenAI API key is not set. Use 'kubelingo config' to set it."
            )

        try:
            self.model = llm.get_model("gpt-4-turbo")
            self.model.key = api_key
        except Exception as e:
            raise ValueError(
                "Failed to initialize OpenAI model via `llm`. Is an API key configured? "
                "You can set it with `llm keys set openai`."
            ) from e

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        json_mode: bool = False,
    ) -> Optional[str]:
        """Sends a chat completion request to the OpenAI API via `llm`."""
        system_prompt = ""
        if messages and messages[0]["role"] == "system":
            system_prompt = messages.pop(0)["content"]

        conversation = "\n".join(f"{m['role']}: {m['content']}" for m in messages)

        try:
            response = self.model.prompt(
                system=system_prompt,
                prompt=conversation,
                temperature=temperature,
            )
            return response.text
        except Exception as e:
            logging.error(f"OpenAI API request via `llm` failed: {e}", exc_info=True)
            raise

    def test_connection(self) -> bool:
        """Tests the connection to the OpenAI API by making a minimal request."""
        try:
            response = self.model.prompt("test")
            return bool(response.text)
        except Exception as e:
            logging.error(f"Failed to connect to OpenAI via `llm`: {e}")
            return False


class GeminiClient(LLMClient):
    """LLM client for Google Gemini models, using the `llm` library."""

    @staticmethod
    def test_key(key: str) -> bool:
        """Tests a Gemini API key without creating a client instance."""
        if not llm:
            return False
        try:
            model = llm.get_model("gemini-pro")
            model.key = key
            response = model.prompt("test")
            return bool(response.text)
        except Exception:
            return False

    def __init__(self):
        if llm is None:
            raise ImportError(
                "The 'llm' and 'llm-gemini' packages are required. "
                "Please install with 'pip install llm llm-gemini'."
            )
        from kubelingo.utils.config import get_gemini_api_key

        api_key = get_gemini_api_key()
        if not api_key:
            raise ValueError(
                "Gemini API key is not set. Use 'kubelingo config' to set it."
            )

        try:
            self.model = llm.get_model("gemini-1.5-pro-latest")
            self.model.key = api_key
        except Exception as e:
            raise ValueError(
                "Failed to initialize Gemini model via `llm`. Is an API key configured? "
                "You can set it with `llm keys set gemini`."
            ) from e

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        json_mode: bool = False,
    ) -> Optional[str]:
        """Sends a chat completion request to the Gemini API via `llm`."""
        system_prompt = ""
        if messages and messages[0]["role"] == "system":
            system_prompt = messages.pop(0)["content"]

        conversation = "\n".join(f"{m['role']}: {m['content']}" for m in messages)

        try:
            response = self.model.prompt(
                system=system_prompt,
                prompt=conversation,
                temperature=temperature,
            )
            return response.text
        except Exception as e:
            logging.error(f"Gemini API request via `llm` failed: {e}", exc_info=True)
            raise

    def test_connection(self) -> bool:
        """Tests the connection to the Gemini API by making a minimal request."""
        try:
            response = self.model.prompt("test")
            return bool(response.text)
        except Exception as e:
            logging.error(f"Failed to connect to Gemini via `llm`: {e}")
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
