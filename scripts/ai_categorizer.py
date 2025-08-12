import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Optional

try:
    import openai
except ImportError:
    openai = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

# Add project root to path to allow imports from kubelingo
# This makes the script runnable from anywhere
try:
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from kubelingo.question import QuestionSubject
except ImportError:
    logging.warning("Could not import kubelingo modules. Subject list will be empty.")
    # Mock for standalone execution/testing
    class MockEnum:
        def __iter__(self):
            return iter([])
    QuestionSubject = MockEnum()


def get_system_prompt() -> str:
    """Builds the system prompt for the AI using definitions from the codebase."""
    exercise_categories_desc = """
1.  **Exercise Category**: Choose ONE from the following fixed options: `basic`, `command`, `manifest`.
    *   `basic`: For open-ended, conceptual questions (Socratic method).
    *   `command`: For quizzes on specific single-line commands (e.g., `kubectl`, `vim`).
    *   `manifest`: For exercises involving authoring or editing Kubernetes YAML files."""

    subject_matter_list = "\n".join([f"    *   {s.value}" for s in QuestionSubject])
    subject_matter_desc = f"""
2.  **Subject Matter**: This is a more specific topic. Choose the most appropriate one from this list, or suggest a new, concise one if none fit well.
{subject_matter_list}
"""

    return f"""You are an expert in Kubernetes and your task is to categorize questions for the Kubelingo learning platform.
You must classify each question into two dimensions: Exercise Category and Subject Matter.
{exercise_categories_desc}
{subject_matter_desc}
Return your answer as a JSON object with two keys: "exercise_category" and "subject_matter".
The value for "exercise_category" MUST be one of `basic`, `command`, or `manifest`.

For example:
{{"exercise_category": "command", "subject_matter": "Core workloads (Pods, ReplicaSets, Deployments; rollouts/rollbacks)"}}
"""


def get_openai_client():
    """Initializes and returns the OpenAI client."""
    if not openai:
        raise ImportError("The 'openai' package is required for the OpenAI provider. Please run 'pip install openai'.")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set. It's required for the OpenAI provider.")
    return openai.OpenAI(api_key=api_key)


def get_gemini_client():
    """Initializes and returns the Gemini client."""
    if not genai:
        raise ImportError("The 'google-generativeai' package is required for the Gemini provider. Please run 'pip install google-generativeai'.")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set. It's required for the Gemini provider.")
    genai.configure(api_key=api_key)
    return genai


def _infer_with_openai(prompt: str, response: Optional[str] = None) -> Optional[Dict[str, str]]:
    """Uses OpenAI to infer categories."""
    try:
        client = get_openai_client()
    except (ImportError, ValueError) as e:
        logging.error(f"OpenAI client setup failed: {e}")
        return None

    user_message = f"Question Prompt:\n---\n{prompt}\n---"
    if response:
        user_message += f"\n\nExample Answer/Solution:\n---\n{response}\n---"

    try:
        logging.debug("Sending request to OpenAI for categorization...")
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo-1106",  # Model that supports JSON mode
            messages=[
                {"role": "system", "content": get_system_prompt()},
                {"role": "user", "content": user_message}
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        result_str = completion.choices[0].message.content
        result = json.loads(result_str)
        logging.debug(f"OpenAI response received: {result_str}")

        if 'exercise_category' in result and 'subject_matter' in result:
            return {
                'exercise_category': result['exercise_category'],
                'subject_matter': result['subject_matter']
            }
        else:
            logging.warning(f"OpenAI response did not contain expected keys: {result_str}")
            return None
    except Exception as e:
        logging.error(f"Error during OpenAI categorization request: {e}", exc_info=True)
        return None


def _infer_with_gemini(prompt: str, response: Optional[str] = None) -> Optional[Dict[str, str]]:
    """Uses Gemini to infer categories."""
    try:
        client = get_gemini_client()
    except (ImportError, ValueError) as e:
        logging.error(f"Gemini client setup failed: {e}")
        return None

    system_prompt = get_system_prompt()
    user_message = f"Question Prompt:\n---\n{prompt}\n---"
    if response:
        user_message += f"\n\nExample Answer/Solution:\n---\n{response}\n---"

    full_prompt = f"{system_prompt}\n\nNow, categorize the following question:\n\n{user_message}"

    try:
        logging.debug("Sending request to Gemini for categorization...")
        # Using a model that supports JSON output format.
        model = client.GenerativeModel('gemini-1.5-flash')
        gemini_response = model.generate_content(
            full_prompt,
            generation_config=client.types.GenerationConfig(
                response_mime_type="application/json",
            )
        )
        result_str = gemini_response.text
        result = json.loads(result_str)
        logging.debug(f"Gemini response received: {result_str}")

        if 'exercise_category' in result and 'subject_matter' in result:
            return {
                'exercise_category': result['exercise_category'],
                'subject_matter': result['subject_matter']
            }
        else:
            logging.warning(f"Gemini response did not contain expected keys: {result_str}")
            return None
    except Exception as e:
        logging.error(f"Error during Gemini categorization request: {e}", exc_info=True)
        return None


def infer_categories_from_text(prompt: str, response: Optional[str] = None) -> Optional[Dict[str, str]]:
    """
    Uses an AI model to infer the exercise category and subject matter for a given question.
    This function consolidates the logic for question categorization, dispatching to the
    correct provider based on the AI_PROVIDER environment variable.
    """
    provider = os.environ.get("AI_PROVIDER", "openai").lower()

    if provider == "gemini":
        logging.info("Using Gemini provider for AI categorization.")
        return _infer_with_gemini(prompt, response)
    elif provider == "openai":
        logging.info("Using OpenAI provider for AI categorization.")
        return _infer_with_openai(prompt, response)
    else:
        logging.error(f"Invalid AI_PROVIDER: '{provider}'. Must be 'openai' or 'gemini'.")
        return None


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    test_prompt = "How do you check the logs of a pod named 'webapp-123'?"
    test_response = "kubectl logs webapp-123"

    print("-" * 20)
    print("Testing with OpenAI provider...")
    if not os.environ.get("OPENAI_API_KEY"):
        print("Skipping OpenAI test: OPENAI_API_KEY environment variable not set.")
    else:
        os.environ["AI_PROVIDER"] = "openai"
        print(f"Testing categorization for prompt: '{test_prompt}'")
        categories = infer_categories_from_text(test_prompt, test_response)
        if categories:
            print(f"Successfully inferred categories with OpenAI: {categories}")
        else:
            print("Failed to infer categories with OpenAI.")

    print("\n" + "-" * 20)
    print("Testing with Gemini provider...")
    if not os.environ.get("GEMINI_API_KEY"):
        print("Skipping Gemini test: GEMINI_API_KEY environment variable not set.")
    else:
        os.environ["AI_PROVIDER"] = "gemini"
        print(f"Testing categorization for prompt: '{test_prompt}'")
        categories = infer_categories_from_text(test_prompt, test_response)
        if categories:
            print(f"Successfully inferred categories with Gemini: {categories}")
        else:
            print("Failed to infer categories with Gemini.")
