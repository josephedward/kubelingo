import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional

# --- Environment Configuration ---
AI_PROVIDER = os.environ.get("KUBELINGO_AI_PROVIDER", "openai").lower()
DEFAULT_OAI_MODEL = "gpt-4-turbo"
DEFAULT_GEMINI_MODEL = "gemini-1.5-pro-latest"


class LLMClient(ABC):
    """Abstract base class for a client that interacts with a Large Language Model."""

    @abstractmethod
    def chat_completion(
        self,
        messages: list[dict[str, str]],
        is_json: bool = False,
        temperature: float = 0.0,
    ) -> Optional[str]:
        """
        Sends a chat completion request to the LLM.

        Args:
            messages: A list of messages comprising the conversation so far.
            is_json: Whether to request a JSON object as output.
            temperature: The sampling temperature.

        Returns:
            The model's response content as a string, or None if an error occurs.
        """
        pass


class OpenAIClient(LLMClient):
    """LLM client for OpenAI models."""

    def __init__(self, api_key: str, model: str = DEFAULT_OAI_MODEL):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("OpenAI client requires 'openai' package. Please run 'pip install openai'.")
        if not api_key:
            raise ValueError("OpenAI API key is required.")
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        is_json: bool = False,
        temperature: float = 0.0,
    ) -> Optional[str]:
        try:
            response_format = {"type": "json_object"} if is_json else {"type": "text"}
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format=response_format,
                temperature=temperature,
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"OpenAI API request failed: {e}", exc_info=True)
            return None


class GeminiClient(LLMClient):
    """LLM client for Google Gemini models."""

    def __init__(self, api_key: str, model: str = DEFAULT_GEMINI_MODEL):
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError("Gemini client requires 'google-generativeai' package. Please run 'pip install google-generativeai'.")
        if not api_key:
            raise ValueError("Google Gemini API key is required.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        is_json: bool = False,
        temperature: float = 0.0,
    ) -> Optional[str]:
        # Gemini uses a 'user' and 'model' role. System prompts are handled as part of the first user message.
        system_prompt = ""
        if messages and messages[0]["role"] == "system":
            system_prompt = messages.pop(0)["content"]

        # Convert OpenAI-style message history to Gemini's format.
        gemini_messages = []
        for i, message in enumerate(messages):
            # Map 'assistant' to 'model'
            role = "model" if message["role"] == "assistant" else "user"
            
            content = message["content"]
            # Prepend system prompt to the first message of the conversation
            if system_prompt and i == 0:
                content = f"{system_prompt}\n\n{content}"

            gemini_messages.append({"role": role, "parts": [content]})
            
        try:
            # Note: Gemini's 'temperature' is part of generation_config.
            generation_config = {"temperature": temperature}
            if is_json:
                generation_config["response_mime_type"] = "application/json"
            
            response = self.model.generate_content(
                gemini_messages,
                generation_config=generation_config,
            )
            return response.text
        except Exception as e:
            logging.error(f"Gemini API request failed: {e}", exc_info=True)
            return None


class FallbackLLMClient(LLMClient):
    """A client that tries a sequence of LLM clients until one succeeds."""

    def __init__(self, clients: list[LLMClient]):
        if not clients:
            raise ValueError("FallbackLLMClient requires at least one client.")
        self.clients = clients

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        is_json: bool = False,
        temperature: float = 0.0,
    ) -> Optional[str]:
        for client in self.clients:
            try:
                logging.info(f"Attempting to use LLM client: {client.__class__.__name__}")
                response = client.chat_completion(
                    messages, is_json=is_json, temperature=temperature
                )
                if response is not None:
                    logging.info(f"LLM client {client.__class__.__name__} succeeded.")
                    return response
                logging.warning(
                    f"LLM client {client.__class__.__name__} failed, trying next."
                )
            except Exception as e:
                logging.error(
                    f"An unexpected error occurred with {client.__class__.__name__}: {e}",
                    exc_info=True,
                )
        logging.error("All LLM clients failed to generate a response.")
        return None


def get_llm_client() -> LLMClient:
    """
    Factory function to get an instance of an LLM client with fallback capabilities.
    It will try providers in an order determined by KUBELINGO_AI_PROVIDER, with
    others as backup if their keys are available.
    """
    # Defer config import to avoid circular dependencies at module load time
    from kubelingo.utils.config import get_openai_api_key, get_gemini_api_key

    clients = []
    openai_api_key = os.getenv("OPENAI_API_KEY") or get_openai_api_key()
    if openai_api_key:
        clients.append(OpenAIClient(api_key=openai_api_key))

    gemini_api_key = os.getenv("GEMINI_API_KEY") or get_gemini_api_key()
    if gemini_api_key:
        clients.append(GeminiClient(api_key=gemini_api_key))

    if not clients:
        raise ValueError("No AI provider API key found. Set OPENAI_API_KEY or GEMINI_API_KEY.")

    # Sort clients to put the preferred provider first.
    if AI_PROVIDER == 'gemini':
        clients.sort(key=lambda c: isinstance(c, GeminiClient), reverse=True)
    else:  # Default to OpenAI first
        clients.sort(key=lambda c: isinstance(c, OpenAIClient), reverse=True)

    if len(clients) > 1:
        client_names = [c.__class__.__name__ for c in clients]
        logging.info(f"Using primary AI provider {client_names[0]} with fallbacks: {', '.join(client_names[1:])}")
        return FallbackLLMClient(clients)

    logging.info(f"Using {clients[0].__class__.__name__} as the only available AI provider.")
    return clients[0]
