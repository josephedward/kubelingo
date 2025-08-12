import os
from abc import ABC, abstractmethod

try:
    import openai
except ImportError:
    openai = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None


class LLMClient(ABC):
    """Abstract base class for a client that interacts with a Large Language Model."""

    @abstractmethod
    def chat_completion(self, messages: list[dict[str, str]], temperature: float = 0.0, is_json: bool = False):
        pass


class OpenAIClient(LLMClient):
    """LLM client for OpenAI models."""

    def __init__(self):
        if not openai:
            raise ImportError("The 'openai' package is required for the OpenAI provider. Please run 'pip install openai'.")
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set. It's required for the OpenAI provider.")
        self.client = openai.OpenAI(api_key=api_key)

    def chat_completion(self, messages: list[dict[str, str]], temperature: float = 0.0, is_json: bool = False):
        kwargs = {
            "model": "gpt-3.5-turbo-1106",
            "messages": messages,
            "temperature": temperature,
        }
        if is_json:
            kwargs["response_format"] = {"type": "json_object"}

        completion = self.client.chat.completions.create(**kwargs)
        return completion.choices[0].message.content


class GeminiClient(LLMClient):
    """LLM client for Google Gemini models."""

    def __init__(self):
        if not genai:
            raise ImportError("The 'google.generativeai' package is required for the Gemini provider. Please run 'pip install google.generativeai'.")
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set. It's required for the Gemini provider.")
        genai.configure(api_key=api_key)
        self.model_name = 'gemini-1.5-flash'

    def chat_completion(self, messages: list[dict[str, str]], temperature: float = 0.0, is_json: bool = False):
        system_prompt = ""
        user_message = ""
        # Gemini takes history as a list of alternating user/model roles.
        # For this system, we'll simplify and combine system/user prompts.
        for msg in messages:
            if msg['role'] == 'system':
                system_prompt = msg['content']
            elif msg['role'] == 'user':
                user_message = msg['content']

        model = genai.GenerativeModel(self.model_name, system_instruction=system_prompt)
        
        config = genai.types.GenerationConfig(temperature=temperature)
        if is_json:
            config.response_mime_type = "application/json"
        
        response = model.generate_content(user_message, generation_config=config)
        return response.text


def get_llm_client() -> LLMClient:
    """
    Factory function to get an LLM client based on environment configuration.
    """
    provider = os.environ.get("AI_PROVIDER", "openai").lower()
    if provider == "openai":
        return OpenAIClient()
    elif provider == "gemini":
        return GeminiClient()
    else:
        raise ValueError(f"Unsupported AI provider: {provider}. Must be 'openai' or 'gemini'.")
