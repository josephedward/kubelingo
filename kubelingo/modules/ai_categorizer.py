import json
import logging
from typing import Dict, Optional, List

import backoff

from kubelingo.integrations.llm import get_llm_client
from kubelingo.question import QuestionCategory, QuestionSubject
from kubelingo.utils.ui import Fore, Style


class AICategorizer:
    """Uses a configured AI model to classify questions into schema categories and subjects."""

    def __init__(self):
        try:
            self.client = get_llm_client()
        except (ImportError, ValueError) as e:
            logging.error(f"Failed to initialize LLM client for AICategorizer: {e}")
            raise
        self.system_prompt = self.get_system_prompt()

    def get_system_prompt(self) -> str:
        """Returns the system prompt for the classification task."""
        category_desc = (
            f"- '{QuestionCategory.OPEN_ENDED.value}': Conceptual questions requiring a textual explanation, evaluated by AI.\n"
            f"- '{QuestionCategory.BASIC_TERMINOLOGY.value}': Questions about definitions, concepts, and names, typically validated with string matching.\n"
            f"- '{QuestionCategory.COMMAND_SYNTAX.value}': Questions that are answered with a single command-line execution, validated by execution or AI.\n"
            f"- '{QuestionCategory.YAML_MANIFEST.value}': Questions that involve creating or editing a YAML file, validated by comparing to a correct manifest."
        )
        subject_desc = "\n".join([f"- '{s.value}'" for s in QuestionSubject])

        return f"""
You are an expert Kubernetes administrator and educator. Your task is to categorize Kubernetes-related questions into a two-level schema.
You will be given a question prompt and must return a JSON object with two keys: "exercise_category" and "subject_matter".

1.  **exercise_category**: Choose ONE of the following high-level exercise types. Use the exact string value provided.
{category_desc}

2.  **subject_matter**: Choose the ONE most relevant subject matter from this list:
{subject_desc}

Analyze the question's content to make the best choice. For example:
- A question about 'kubectl create deployment' should be categorized as {{ "exercise_category": "{QuestionCategory.COMMAND_SYNTAX.value}", "subject_matter": "{QuestionSubject.CORE_WORKLOADS.value}" }}.
- A question asking to write a YAML file for a Pod is {{ "exercise_category": "{QuestionCategory.YAML_MANIFEST.value}", "subject_matter": "{QuestionSubject.CORE_WORKLOADS.value}" }}.
- A conceptual question about the purpose of a Service is {{ "exercise_category": "{QuestionCategory.BASIC_TERMINOLOGY.value}", "subject_matter": "{QuestionSubject.SERVICES.value}" }}.
- A question about using Vim to find and replace text is {{ "exercise_category": "{QuestionCategory.COMMAND_SYNTAX.value}", "subject_matter": "{QuestionSubject.LINUX_SYNTAX.value}" }}.

Return ONLY a valid JSON object in the format:
{{
  "exercise_category": "The full string value of the category",
  "subject_matter": "The full string value of the subject"
}}
Do not include any other text or explanation.
"""

    # The backoff decorator should handle exceptions from the underlying client (OpenAI, Gemini, etc.)
    @backoff.on_exception(backoff.expo, Exception, max_tries=5)
    def categorize_question(self, question: dict) -> Optional[Dict[str, str]]:
        """Classifies a single question using the AI model."""
        prompt_text = question.get('prompt', '')
        if not prompt_text:
            return None

        user_prompt = f"Categorize this question: {prompt_text}"
        
        try:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            response = self.client.chat_completion(
                messages=messages,
                json_mode=True,
                temperature=0.0
            )

            if not response:
                return None

            response_str = response
            if not isinstance(response, str):
                # Handle response objects that have a `text` attribute or method.
                if hasattr(response, 'text'):
                    text_attr = getattr(response, 'text')
                    if callable(text_attr):
                        response_str = text_attr()
                    else:
                        response_str = text_attr
                else: # Fallback for unknown object types
                    response_str = str(response)

            data = json.loads(response_str)
            
            category = data.get("exercise_category")
            subject_matter = data.get("subject_matter")

            valid_categories = [c.value for c in QuestionCategory]
            valid_subjects = [s.value for s in QuestionSubject]

            if category in valid_categories and subject_matter in valid_subjects:
                return {"exercise_category": category, "subject_matter": subject_matter}
            else:
                logging.warning(f"{Fore.YELLOW}\nWarning: AI returned invalid or unexpected data: {data}. Skipping.{Style.RESET_ALL}")
                return None

        except json.JSONDecodeError:
            logging.warning(f"{Fore.YELLOW}\nWarning: Failed to decode AI JSON response. Skipping.{Style.RESET_ALL}")
            return None
        except Exception as e:
            # The backoff decorator will catch this and retry. If it fails after all retries,
            # this will be the final exception raised.
            logging.error(f"{Fore.RED}\nAn unexpected error occurred during AI categorization: {e}{Style.RESET_ALL}")
            raise  # Re-raise to allow backoff to handle it.
