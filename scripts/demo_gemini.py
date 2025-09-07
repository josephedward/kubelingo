#!/usr/bin/env python3
"""
demo_gemini.py: A simple script to test the ai_chat function with the Gemini provider.

Usage:
  # Ensure GEMINI_API_KEY is set in the environment or declared in a .env file
  python3 demo_gemini.py
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
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set.")
        sys.exit(1)

    system_prompt = "You are a helpful assistant."

    # Example 1: Trivia Question
    print("=== Gemini CKAD Trivia Example ===")
    trivia_prompt = (
        "Create a Kubernetes trivia question suitable for CKAD candidates. "
        "The question should require a conceptual answer and provide all necessary context. "
        "Return the question and the complete answer."
    )
    print("Prompt: ", trivia_prompt)
    response = ai_chat(system_prompt, trivia_prompt)
    print("Response:\n", response)
    print()

    # Example 2: Command Question
    print("=== Gemini CKAD Command Example ===")
    command_prompt = (
        "Create a Kubernetes CKAD question that requires running a kubectl command. "
        "Include all required details: context, resource names, and expected result. "
        "Return both the question and the complete command answer."
    )
    print("Prompt: ", command_prompt)
    response = ai_chat(system_prompt, command_prompt)
    print("Response:\n", response)
    print()

    # Example 3: Manifest Question
    print("=== Gemini CKAD Manifest Example ===")
    manifest_prompt = (
        "Create a Kubernetes CKAD question that requires writing a YAML manifest. "
        "Provide all required details, such as pod name, image, probes, and environment settings. "
        "Return both the question and a valid Kubernetes YAML manifest as the answer."
    )
    print("Prompt: ", manifest_prompt)
    response = ai_chat(system_prompt, manifest_prompt)
    print("Response:\n", response)
    print()

if __name__ == "__main__":
    main()