import os
from abc import ABC, abstractmethod
import logging
from typing import Optional

try:
    import google.generativeai as genai
except ImportError:
    genai = None


class LLMClient(ABC):
    """Abstract base class for a client that interacts with a Large Language Model."""

    @abstractmethod
    def chat_completion(
        self, messages: list[dict[str, str]], temperature: float = 0.0
    ) -> Optional[str]:
        pass


class GeminiClient(LLMClient):
    """LLM client for Google Gemini models."""

    def __init__(self):
        if genai is None:
            raise ImportError(
                "The 'google-generativeai' package is required to use GeminiClient. "
                "Please install it with 'pip install google-generativeai'."
            )

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")

        genai.configure(api_key=api_key)

    def chat_completion(
        self, messages: list[dict[str, str]], temperature: float = 0.0
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
                "gemini-pro", system_instruction=system_prompt
            )
            generation_config = genai.types.GenerationConfig(temperature=temperature)
            response = model.generate_content(
                gemini_messages,
                generation_config=generation_config,
            )
            return response.text
        except Exception as e:
            logging.error(f"Gemini API request failed: {e}", exc_info=True)
            raise  # Re-raise for the caller to handle


def get_llm_client(client_type: str = "gemini") -> LLMClient:
    """
    Factory function to get an LLM client instance.

    Args:
        client_type (str): The type of LLM client to return. Defaults to "gemini".

    Returns:
        LLMClient: An instance of the requested LLM client.
    """
    if client_type == "gemini":
        return GeminiClient()
    else:
        raise ValueError(f"Unsupported LLM client type: {client_type}")
