
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("PERPLEXITY_API_KEY")

if not API_KEY:
    print("Error: PERPLEXITY_API_KEY not found in .env file")
else:
    url = "https://api.perplexity.ai/chat/completions"
    payload = {
        "model": "sonar-medium-online",
        "messages": [
            {"role": "system", "content": "Provide concise, precise answers."},
            {"role": "user", "content": "Ask a CKAD exam-style question that requires providing a kubectl command. State the full question and answer."}
        ],
        "max_tokens": 400
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        print(response.json())
    except requests.exceptions.RequestException as e:
        print(f"Error: API request failed: {e}")
