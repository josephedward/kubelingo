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
        system_prompt: str,
        user_prompt: str,
        is_json: bool = False,
        temperature: float = 0.0,
    ) -> Optional[str]:
        """
        Sends a chat completion request to the LLM.

        Args:
            system_prompt: The system message to guide the model's behavior.
            user_prompt: The user's message.
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
        system_prompt: str,
        user_prompt: str,
        is_json: bool = False,
        temperature: float = 0.0,
    ) -> Optional[str]:
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
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
        system_prompt: str,
        user_prompt: str,
        is_json: bool = False,
        temperature: float = 0.0,
    ) -> Optional[str]:
        # Gemini uses a different structure, combining system and user prompts.
        # It also has specific ways to enforce JSON output.
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        if is_json:
            full_prompt += "\n\nRespond ONLY with a valid JSON object."

        try:
            # Note: Gemini's 'temperature' is part of generation_config.
            generation_config = {"temperature": temperature}
            if is_json:
                generation_config["response_mime_type"] = "application/json"
                
            response = self.model.generate_content(
                full_prompt,
                generation_config=generation_config,
            )
            return response.text
        except Exception as e:
            logging.error(f"Gemini API request failed: {e}", exc_info=True)
            return None


def get_llm_client() -> LLMClient:
    """
    Factory function to get an instance of the configured LLM client.
    Reads the KUBELINGO_AI_PROVIDER environment variable.
    """
    # Defer config import to avoid circular dependencies at module load time
    from kubelingo.utils.config import get_openai_api_key, get_gemini_api_key

    if AI_PROVIDER == 'gemini':
        api_key = os.getenv("GEMINI_API_KEY") or get_gemini_api_key()
        if not api_key:
            raise ValueError("Gemini API key not found. Set GEMINI_API_KEY or use 'kubelingo config set gemini'.")
        logging.info("Using Gemini AI Provider.")
        return GeminiClient(api_key=api_key)
    
    # Default to OpenAI
    api_key = os.getenv("OPENAI_API_KEY") or get_openai_api_key()
    if not api_key:
        raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY or use 'kubelingo config set openai'.")
    logging.info("Using OpenAI AI Provider.")
    return OpenAIClient(api_key=api_key)
