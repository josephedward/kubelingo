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


def get_ai_client():
    """Initializes and returns the OpenAI client."""
    if not openai:
        raise ImportError("The 'openai' package is required for AI categorization. Please run 'pip install openai'.")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set. It's required for AI categorization.")
    return openai.OpenAI(api_key=api_key)


def infer_categories_from_text(prompt: str, response: Optional[str] = None) -> Optional[Dict[str, str]]:
    """
    Uses an AI model to infer the exercise category and subject matter for a given question.
    This function consolidates the logic for question categorization.
    """
    try:
        client = get_ai_client()
    except (ImportError, ValueError) as e:
        logging.error(f"AI client setup failed: {e}")
        return None

    user_message = f"Question Prompt:\n---\n{prompt}\n---"
    if response:
        user_message += f"\n\nExample Answer/Solution:\n---\n{response}\n---"

    try:
        logging.debug("Sending request to AI for categorization...")
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo-1106",  # A model that supports JSON mode
            messages=[
                {"role": "system", "content": get_system_prompt()},
                {"role": "user", "content": user_message}
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        result_str = completion.choices[0].message.content
        result = json.loads(result_str)
        logging.debug(f"AI response received: {result_str}")

        if 'exercise_category' in result and 'subject_matter' in result:
            return {
                'exercise_category': result['exercise_category'],
                'subject_matter': result['subject_matter']
            }
        else:
            logging.warning(f"AI response did not contain expected keys: {result_str}")
            return None
    except Exception as e:
        logging.error(f"Error during AI categorization request: {e}", exc_info=True)
        return None


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    if not os.environ.get("OPENAI_API_KEY"):
        print("Please set the OPENAI_API_KEY environment variable to run this test.")
    else:
        test_prompt = "How do you check the logs of a pod named 'webapp-123'?"
        test_response = "kubectl logs webapp-123"
        print(f"Testing categorization for prompt: '{test_prompt}'")
        categories = infer_categories_from_text(test_prompt, test_response)
        if categories:
            print(f"Successfully inferred categories: {categories}")
        else:
            print("Failed to infer categories.")
