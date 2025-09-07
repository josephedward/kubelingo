#!/usr/bin/env python3
"""
demo_openrouter.py: A simple script to test the ai_chat function with the OpenRouter provider.

Usage:
  # Ensure OPENROUTER_API_KEY is set in the environment or declared in a .env file
  python3 demo_openrouter.py
"""
import os
import sys
# Load environment variables from .env if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from kubelingo.cli import ai_chat
except ImportError:
    print("Error: Cannot import ai_chat from kubelingo.cli. Run this script from the project root.")
    sys.exit(1)

def main():
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("Error: OPENROUTER_API_KEY environment variable not set.")
        sys.exit(1)
    # The provider will be auto-detected by ai_chat based on environment variables

    # Example conversation
    system_prompt = "You are a helpful assistant named Lingo."
    user_prompt = "What's the greeting in multiple languages?"
    print("System prompt:", system_prompt)
    print("User prompt:", user_prompt)

    # Call ai_chat and display the response
    response = ai_chat(system_prompt, user_prompt)
    if not response:
        print("No response received from OpenRouter.")
        sys.exit(1)
    print("\nAI Response:\n" + response)

if __name__ == "__main__":
    main()