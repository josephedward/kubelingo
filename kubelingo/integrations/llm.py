import os
from abc import ABC, abstractmethod

class LLMClient(ABC):
    """Abstract base class for a client that interacts with a Large Language Model."""

    @abstractmethod
    def chat_completion(self, messages: list[dict[str, str]], temperature: float = 0.0):
        pass


class GeminiClient(LLMClient):
    """LLM client for Google Gemini models."""

    def chat_completion(self, messages: list[dict[str, str]], temperature: float = 0.0):
        # Example implementation for Gemini API
        import requests
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")

        url = "https://gemini.googleapis.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}"}
        payload = {
            "messages": messages,
            "temperature": temperature,
        }

        response = requests.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            raise RuntimeError(f"Gemini API error: {response.status_code} {response.text}")

        return response.json().get("choices", [{}])[0].get("message", {}).get("content", "")


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
