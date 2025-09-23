import os
import json
import requests
from typing import Dict, Any
from .prompt_templates import build_prompt


class ProviderError(Exception):
    pass


def _ensure_key(var: str) -> str:
    val = os.getenv(var)
    if not val:
        raise ProviderError(f"Missing required env var: {var}")
    return val


def _call_openai(question_type: str, topic: str) -> Dict[str, Any]:
    from openai import OpenAI
    key = _ensure_key("OPENAI_API_KEY")
    client = OpenAI(api_key=key)
    prompts = build_prompt(question_type, topic)
    resp = client.chat.completions.create(
        model=os.getenv("KUBELINGO_OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": prompts["system"]},
            {"role": "user", "content": prompts["user"]},
        ],
        temperature=0.2,
    )
    content = resp.choices[0].message.content
    return json.loads(content)


def _call_gemini(question_type: str, topic: str) -> Dict[str, Any]:
    import google.generativeai as genai
    key = _ensure_key("GEMINI_API_KEY")
    genai.configure(api_key=key)
    model = genai.GenerativeModel(os.getenv("KUBELINGO_GEMINI_MODEL", "gemini-1.5-flash-latest"))
    prompts = build_prompt(question_type, topic)
    resp = model.generate_content([
        prompts["system"],
        prompts["user"],
    ])
    text = resp.text
    return json.loads(text)


def _call_openrouter(question_type: str, topic: str) -> Dict[str, Any]:
    key = _ensure_key("OPENROUTER_API_KEY")
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    prompts = build_prompt(question_type, topic)
    payload = {
        "model": os.getenv("KUBELINGO_OPENROUTER_MODEL", "deepseek/deepseek-chat"),
        "messages": [
            {"role": "system", "content": prompts["system"]},
            {"role": "user", "content": prompts["user"]},
        ],
        "temperature": 0.2,
    }
    r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"]
    return json.loads(text)


def _call_perplexity(question_type: str, topic: str) -> Dict[str, Any]:
    key = _ensure_key("PERPLEXITY_API_KEY")
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    prompts = build_prompt(question_type, topic)
    payload = {
        "model": os.getenv("KUBELINGO_PERPLEXITY_MODEL", "sonar-medium-online"),
        "messages": [
            {"role": "system", "content": prompts["system"]},
            {"role": "user", "content": prompts["user"]},
        ],
        "temperature": 0.2,
    }
    r = requests.post("https://api.perplexity.ai/chat/completions", headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"]
    return json.loads(text)


def generate_with_provider(provider: str, question_type: str, topic: str) -> Dict[str, Any]:
    provider = provider.lower()
    if provider == "openai":
        return _call_openai(question_type, topic)
    if provider == "gemini":
        return _call_gemini(question_type, topic)
    if provider == "openrouter":
        return _call_openrouter(question_type, topic)
    if provider == "perplexity":
        return _call_perplexity(question_type, topic)
    raise ProviderError(f"Unknown provider: {provider}")


def get_available_providers() -> list[str]:
    """Returns a list of available providers."""
    return ["openai", "gemini", "openrouter", "perplexity"]

