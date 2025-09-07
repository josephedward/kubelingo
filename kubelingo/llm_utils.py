import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

def ai_chat(*args, **kwargs):
    """
    Send messages to the configured LLM provider and return its reply text.
    Supports Gemini and OpenRouter per requirements.
    """
    # Normalize messages: either a list of dicts or two args (system, user)
    if len(args) == 1 and isinstance(args[0], list):
        messages = args[0]
    elif len(args) == 2:
        messages = [
            {"role": "system", "content": args[0]},
            {"role": "user",   "content": args[1]}
        ]
    else:
        raise ValueError("ai_chat expects (system, user) or ([messages])")
    provider = os.getenv("KUBELINGO_LLM_PROVIDER", "").lower()
    # Gemini provider
    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            print("Error: No LLM provider configured. Please set one in Settings.")
            return ""
        model = "gemini-1.5-flash-latest"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        # Merge prompts
        merged = "\n\n".join(m["content"] for m in messages)
        payload = {
            "contents": [{"role": "user", "parts": [{"text": merged}]}],
            "generationConfig": {"temperature": 0.5}
        }
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    # OpenRouter provider
    if provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not api_key:
            print("Error: No LLM provider configured. Please set one in Settings.")
            return ""
        model = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-r1-0528:free")
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": model, "messages": messages, "temperature": 0.5}
        resp = requests.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    # OpenAI provider
    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            print("Error: No OpenAI API key found. Please set the OPENAI_API_KEY environment variable.")
            return ""
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
            "messages": messages,
            "temperature": 0.5
        }
        resp = requests.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data.get("choices", [])[0].get("message", {}).get("content", "")
    # No supported provider configured
    print("Error: No LLM provider configured. Please set one in Settings.")
    return ""