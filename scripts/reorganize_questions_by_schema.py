#!/usr/bin/env python3
"""
This script reorganizes all questions in the database by assigning them to a
schema category ('Basic/Open-Ended', 'Command-Based/Syntax', 'Manifests')
and a subject matter area using an AI model for classification.
"""
import os
import sys
import json
import backoff
from tqdm import tqdm
from typing import Dict, Optional

# Ensure the parent directory is on sys.path to allow for package imports
if __name__ == '__main__' and __package__ is None:
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(pkg_dir)
    sys.path.insert(0, project_root)
    # At this point, `import kubelingo` should work
    __package__ = 'scripts'

from kubelingo.database import get_db_connection, _row_to_question_dict
from kubelingo.question import QuestionCategory, QuestionSubject
from kubelingo.utils.config import get_api_key
from kubelingo.utils.ui import Fore, Style

try:
    import openai
except ImportError:
    print(f"{Fore.RED}OpenAI library not found. Please run 'pip install openai'.{Style.RESET_ALL}")
    sys.exit(1)


class AICategorizer:
    """Uses an AI model to classify questions into schema categories."""

    def __init__(self, api_key: str, model_name: str = "gpt-4-turbo"):
        if not api_key:
            raise ValueError("OpenAI API key is required.")
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model_name
        self.system_prompt = self.get_system_prompt()

    def get_system_prompt(self) -> str:
        """Returns the system prompt for the classification task."""
        category_desc = "\n".join([f'- "{c.value}"' for c in QuestionCategory])
        subject_desc = "\n".join([f'- "{s.value}" for s in QuestionSubject])

        return f"""
You are an expert Kubernetes administrator and educator. Your task is to categorize Kubernetes-related questions into a two-level schema.
You will be given a question prompt and must return a JSON object with two keys: "schema_category" and "subject".

1.  **schema_category**: Choose ONE of the following high-level exercise types:
{category_desc}

2.  **subject**: Choose the ONE most relevant subject matter from this list:
{subject_desc}

Analyze the question's content to make the best choice. For example:
- A question about 'kubectl create deployment' should be categorized as {{ "schema_category": "Command-Based/Syntax", "subject": "Core workloads (Pods, ReplicaSets, Deployments; rollouts/rollbacks)" }}.
- A question asking to write a YAML file for a Pod is {{ "schema_category": "Manifests", "subject": "Core workloads (Pods, ReplicaSets, Deployments; rollouts/rollbacks)" }}.
- A conceptual question about the purpose of a Service is {{ "schema_category": "Basic/Open-Ended", "subject": "Services (ClusterIP/NodePort/LoadBalancer, selectors, headless)" }}.

Return ONLY a valid JSON object in the format:
{{
  "schema_category": "The full string value of the category",
  "subject": "The full string value of the subject"
}}
Do not include any other text or explanation.
"""

    @backoff.on_exception(backoff.expo, openai.RateLimitError, max_tries=5)
    def categorize_question(self, question: dict) -> Optional[Dict[str, str]]:
        """Classifies a single question using the AI model."""
        prompt_text = question.get('prompt', '')
        if not prompt_text:
            return None

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"Categorize this question: {prompt_text}"},
                ],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            data = json.loads(response.choices[0].message.content)
            
            category = data.get("schema_category")
            subject = data.get("subject")

            valid_categories = [c.value for c in QuestionCategory]
            valid_subjects = [s.value for s in QuestionSubject]

            if category in valid_categories and subject in valid_subjects:
                return {"schema_category": category, "subject": subject}
            else:
                print(f"{Fore.YELLOW}\nWarning: AI returned invalid data: {data}. Skipping.{Style.RESET_ALL}")
                return None

        except json.JSONDecodeError:
            print(f"{Fore.YELLOW}\nWarning: Failed to decode AI JSON response. Skipping.{Style.RESET_ALL}")
            return None
        except Exception as e:
            print(f"{Fore.RED}\nAn unexpected error occurred during AI categorization: {e}{Style.RESET_ALL}")
            return None


def main():
    """Main function to run the reorganization script."""
    api_key = os.getenv('OPENAI_API_KEY') or get_api_key()
    if not api_key:
        print(f"{Fore.RED}OpenAI API key not found. Please set the OPENAI_API_KEY environment variable or use 'kubelingo config set openai'.{Style.RESET_ALL}")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM questions WHERE schema_category IS NULL OR subject IS NULL")
    rows = cursor.fetchall()
    
    if not rows:
        print(f"{Fore.GREEN}All questions are already categorized. No migration needed.{Style.RESET_ALL}")
        conn.close()
        return

    print(f"Found {len(rows)} questions to categorize...")
    categorizer = AICategorizer(api_key=api_key)
    
    updated_count = 0
    with tqdm(rows, desc="Categorizing questions") as pbar:
        for row in pbar:
            q_dict = _row_to_question_dict(row)
            q_id = q_dict.get('id')
            
            result = categorizer.categorize_question(q_dict)
            
            if result:
                cursor.execute(
                    "UPDATE questions SET schema_category = ?, subject = ? WHERE id = ?",
                    (result["schema_category"], result["subject"], q_id)
                )
                updated_count += 1
                pbar.set_postfix(status="Success")
            else:
                pbar.set_postfix(status=f"Failed: {q_id}")

    conn.commit()
    conn.close()
    
    print("\nReorganization complete.")
    print(f"  - Questions updated: {updated_count}")
    print(f"  - Questions failed/skipped: {len(rows) - updated_count}")

if __name__ == '__main__':
    main()
