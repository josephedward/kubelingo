import os
import json
import requests
try:
    from dotenv import load_dotenv
    # Load environment variables from .env file if present
    load_dotenv()
except ImportError:
    # dotenv not installed; skip loading .env file
    pass

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
    # Determine LLM provider: explicit or auto-detect via API keys
    provider = os.getenv("KUBELINGO_LLM_PROVIDER", "").lower()
    # Auto-detect provider if not explicitly set
    if not provider:
        detected = []
        if os.getenv("GEMINI_API_KEY"): detected.append("gemini")
        if os.getenv("OPENROUTER_API_KEY"): detected.append("openrouter")
        if os.getenv("OPENAI_API_KEY"): detected.append("openai")
        if len(detected) == 1:
            provider = detected[0]
    # No provider configured
    if not provider:
        print("Error: No LLM provider configured. Please set one in Settings.")
        return ""
    try:
        if provider == "gemini":
            api_key = os.getenv("GEMINI_API_KEY", "")
            if not api_key:
                raise RuntimeError("No GEMINI_API_KEY set")
            model = "gemini-1.5-flash-latest"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            merged = "\n\n".join(m["content"] for m in messages)
            payload = {"contents": [{"role": "user", "parts": [{"text": merged}]}],
                       "generationConfig": {"temperature": 0.5}}
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        elif provider == "openrouter":
            api_key = os.getenv("OPENROUTER_API_KEY", "")
            if not api_key:
                raise RuntimeError("No OPENROUTER_API_KEY set")
            model = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-r1-0528:free")
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {"model": model, "messages": messages, "temperature": 0.5}
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        elif provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                raise RuntimeError("No OPENAI_API_KEY set")
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {"model": os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
                       "messages": messages, "temperature": 0.5}
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.json().get("choices", [])[0].get("message", {}).get("content", "")
        else:
            # No provider configured
            raise RuntimeError("No LLM provider configured; set KUBELINGO_LLM_PROVIDER or API key.")
    except Exception as e:
        # On any request failure, print a generic message and return empty string
        print(f"AI request failed: {e}")
        return ""