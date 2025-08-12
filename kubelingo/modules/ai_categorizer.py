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
        category_desc = "\n".join([f"- '{c.value}'" for c in QuestionCategory])
        subject_desc = "\n".join([f"- '{s.value}'" for s in QuestionSubject])

        return f"""
You are an expert Kubernetes administrator and educator. Your task is to categorize Kubernetes-related questions into a two-level schema.
You will be given a question prompt and must return a JSON object with two keys: "schema_category" and "subject_matter".

1.  **schema_category**: Choose ONE of the following high-level exercise types: 'basic', 'command', or 'manifest'.
    - 'basic': Conceptual or open-ended questions.
    - 'command': Questions involving CLI commands (e.g., kubectl, helm, vim).
    - 'manifest': Questions about writing or editing YAML/JSON configuration files.

2.  **subject_matter**: Choose the ONE most relevant subject matter from this list:
{subject_desc}

Analyze the question's content to make the best choice. For example:
- A question about 'kubectl create deployment' should be categorized as {{ "schema_category": "command", "subject_matter": "Core workloads (Pods, ReplicaSets, Deployments; rollouts/rollbacks)" }}.
- A question asking to write a YAML file for a Pod is {{ "schema_category": "manifest", "subject_matter": "Core workloads (Pods, ReplicaSets, Deployments; rollouts/rollbacks)" }}.
- A conceptual question about the purpose of a Service is {{ "schema_category": "basic", "subject_matter": "Services (ClusterIP/NodePort/LoadBalancer, selectors, headless)" }}.
- A question about using Vim to find and replace text is {{ "schema_category": "command", "subject_matter": "Vim editor usage" }}.
- A question about kubectl command aliases should be {{ "schema_category": "command", "subject_matter": "Kubectl CLI usage and commands" }}.

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
            response_str = self.client.chat_completion(
                system_prompt=self.system_prompt,
                user_prompt=user_prompt,
                is_json=True,
                temperature=0.0
            )

            if not response_str:
                return None
                
            data = json.loads(response_str)
            
            category = data.get("exercise_category")
            subject_matter = data.get("subject_matter")

            exercise_category_map = {
                "basic": "basic",
                "command": "command",
                "manifest": "manifest",
                "Basic/Open-Ended": "basic",
                "Command-Based/Syntax": "command",
                "Manifests": "manifest",
            }
            valid_subjects = [s.value for s in QuestionSubject]

            if category in exercise_category_map and subject_matter in valid_subjects:
                return {"exercise_category": exercise_category_map[category], "subject_matter": subject_matter}
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
