#!/usr/bin/env python3
"""
This script loads all unique questions from YAML files, uses an AI to categorize
them by exercise type and subject matter, and saves them to a new database file.
"""

import argparse
import os
import sys
import json
import backoff
import dataclasses
from tqdm import tqdm
from typing import Dict, Optional, List

# Ensure the parent directory is on sys.path to allow for package imports
if __name__ == '__main__' and __package__ is None:
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(pkg_dir)
    sys.path.insert(0, project_root)
    __package__ = 'scripts'

try:
    import openai
except ImportError:
    openai = None

from kubelingo.database import init_db, add_question, get_db_connection
from kubelingo.modules.yaml_loader import YAMLLoader
from kubelingo.utils.path_utils import get_all_question_dirs, find_yaml_files
from kubelingo.utils.config import get_api_key
from kubelingo.utils.ui import Fore, Style
from kubelingo.question import Question

# --- AI Categorization ---

EXERCISE_TYPES = ['basic', 'command', 'manifest']
SUGGESTED_SUBJECTS = [
    "Core workloads (Pods, ReplicaSets, Deployments; rollouts/rollbacks)",
    "Services (ClusterIP/NodePort/LoadBalancer, selectors, headless)",
    "Storage (PersistentVolumes, PersistentVolumeClaims, StorageClasses)",
    "Configuration (ConfigMaps, Secrets)",
    "Security (ServiceAccounts, Roles, RoleBindings, NetworkPolicies)",
    "Scheduling (taints, tolerations, node affinity, node selectors)",
    "Observability (logging, monitoring, debugging)",
    "Kubectl CLI usage and commands",
    "Vim editor usage",
    "Helm",
]


class AICategorizer:
    """Uses an AI model to classify questions into schema categories and subjects."""

    def __init__(self, api_key: str, model_name: str = "gpt-4-turbo"):
        if not openai:
            raise ImportError("OpenAI library not found. Please run 'pip install openai'.")
        if not api_key:
            raise ValueError("OpenAI API key is required.")
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model_name
        self.system_prompt = self.get_system_prompt()

    def get_system_prompt(self) -> str:
        """Returns the system prompt for the classification task."""
        category_desc = "\n".join([f"- '{c}'" for c in EXERCISE_TYPES])
        subject_desc = "\n".join([f"- '{s}'" for s in SUGGESTED_SUBJECTS])

        return f"""
You are an expert Kubernetes administrator and educator. Your task is to categorize Kubernetes-related questions into a two-level schema.
You will be given a question prompt and must return a JSON object with two keys: "schema_category" and "subject_matter".

1.  **schema_category**: Choose ONE of the following three high-level exercise types. This choice is mandatory and must be from this list:
{category_desc}
    - 'basic': For conceptual, theoretical, or knowledge-based questions. This includes questions about "what is X?", "what does X do?", or recalling specific names, shortnames, or simple commands (e.g., "What command lists pods?").
    - 'command': For practical, hands-on questions that require the user to *construct and execute* a specific `kubectl` command to achieve a goal. These are typically imperative commands for creating or modifying resources.
    - 'manifest': For questions requiring writing or editing YAML/JSON manifests.

2.  **subject_matter**: Choose the ONE most relevant subject matter. Here is a list of suggested subjects to use if they are a good fit:
{subject_desc}
    If the question topic is not well-represented by the list above, you are encouraged to create a new, concise, and descriptive subject matter.

Analyze the question's content to make the best choice. For example:
- A question asking "What is the shortname for ConfigMap?" is {{ "schema_category": "basic", "subject_matter": "Kubectl CLI usage and commands" }}.
- A question like "Create a deployment named frontend --image=nginx:1.14" is {{ "schema_category": "command", "subject_matter": "Core workloads (Pods, ReplicaSets, Deployments; rollouts/rollbacks)" }}.
- A question asking to write a YAML file for a Pod is {{ "schema_category": "manifest", "subject_matter": "Core workloads (Pods, ReplicaSets, Deployments; rollouts/rollbacks)" }}.
- A conceptual question about the purpose of a Service is {{ "schema_category": "basic", "subject_matter": "Services (ClusterIP/NodePort/LoadBalancer, selectors, headless)" }}.

Return ONLY a valid JSON object in the format:
{{
  "schema_category": "The chosen category string",
  "subject_matter": "The chosen or created subject string"
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
                    {{"role": "system", "content": self.system_prompt}},
                    {{"role": "user", "content": f"Categorize this question: {prompt_text}"}},
                ],
                response_format={{"type": "json_object"}},
                temperature=0.0
            )
            data = json.loads(response.choices[0].message.content)

            category = data.get("schema_category")
            subject_matter = data.get("subject_matter")

            if category in EXERCISE_TYPES and isinstance(subject_matter, str) and subject_matter:
                return {{"schema_category": category, "subject_matter": subject_matter}}
            else:
                print(f"{{Fore.YELLOW}}\\nWarning: AI returned invalid data: {data}. Skipping.{{Style.RESET_ALL}}")
                return None

        except json.JSONDecodeError:
            print(f"{{Fore.YELLOW}}\\nWarning: Failed to decode AI JSON response. Skipping.{{Style.RESET_ALL}}")
            return None
        except Exception as e:
            print(f"{{Fore.RED}}\\nAn unexpected error occurred during AI categorization: {e}{{Style.RESET_ALL}}")
            return None

# --- Main script logic ---

def main():
    """Main function to run the import and categorization script."""
    parser = argparse.ArgumentParser(
        description="Import questions from YAML files into a new SQLite database with AI-powered categorization.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "output_db",
        help="Path to the new SQLite database file to be created.",
    )
    parser.add_argument(
        "--search-dir",
        action='append',
        help="Optional: Path to a specific directory to search for YAML files. Can be used multiple times. Defaults to searching all standard question directories."
    )
    args = parser.parse_args()

    if os.path.exists(args.output_db):
        overwrite = input(f"{{Fore.YELLOW}}Warning: Output database '{{args.output_db}}' already exists. Overwrite? (y/n): {{Style.RESET_ALL}}").lower()
        if overwrite != 'y':
            print("Operation cancelled.")
            return
        os.remove(args.output_db)

    api_key = get_api_key()
    if not api_key:
        print(f"{{Fore.RED}}Error: OpenAI API key not found. Set the OPENAI_API_KEY environment variable.{{Style.RESET_ALL}}")
        sys.exit(1)

    print(f"Initializing new database at: {args.output_db}")
    init_db(db_path=args.output_db)
    conn = get_db_connection(db_path=args.output_db)

    search_dirs = args.search_dir or get_all_question_dirs()
    yaml_files = find_yaml_files(search_dirs)

    if not yaml_files:
        print(f"{{Fore.YELLOW}}No YAML files found in the specified directories.{{Style.RESET_ALL}}")
        return

    print(f"Found {len(yaml_files)} YAML file(s) to process...")

    all_questions = []
    loader = YAMLLoader()
    for file_path in yaml_files:
        try:
            questions = loader.load_file(str(file_path))
            all_questions.extend(questions)
        except Exception as e:
            print(f"{{Fore.YELLOW}}Warning: Could not process file '{file_path}': {e}{{Style.RESET_ALL}}")

    unique_questions: Dict[str, Question] = {{}}
    for q in all_questions:
        if q.prompt and q.prompt not in unique_questions:
            unique_questions[q.prompt] = q

    print(f"Found {len(unique_questions)} unique questions. Categorizing with AI...")

    categorizer = AICategorizer(api_key=api_key)
    processed_count = 0

    try:
        with tqdm(total=len(unique_questions), desc="Categorizing Questions") as pbar:
            for question in unique_questions.values():
                q_dict = dataclasses.asdict(question)
                ai_categories = categorizer.categorize_question(q_dict)

                schema_cat = q_dict.get('schema_category')
                subject_mat = q_dict.get('subject')

                if ai_categories:
                    schema_cat = ai_categories.get('schema_category', schema_cat)
                    subject_mat = ai_categories.get('subject_matter', subject_mat)

                add_question(
                    conn=conn,
                    id=q_dict.get('id'),
                    prompt=q_dict.get('prompt'),
                    source_file=q_dict.get('source_file'),
                    response=q_dict.get('response'),
                    category=q_dict.get('category'),
                    source=q_dict.get('source'),
                    validation_steps=q_dict.get('validation_steps'),
                    validator=q_dict.get('validator'),
                    review=q_dict.get('review', False),
                    explanation=q_dict.get('explanation'),
                    difficulty=q_dict.get('difficulty'),
                    pre_shell_cmds=q_dict.get('pre_shell_cmds'),
                    initial_files=q_dict.get('initial_files'),
                    question_type=q_dict.get('type'),
                    answers=q_dict.get('answers'),
                    correct_yaml=q_dict.get('correct_yaml'),
                    metadata=q_dict.get('metadata'),
                    schema_category=schema_cat,
                    subject_matter=subject_mat
                )
                processed_count += 1
                pbar.update(1)

    finally:
        if conn:
            conn.close()

    print(f"\\n{{Fore.GREEN}}Successfully processed and added {processed_count} questions to '{args.output_db}'.{{Style.RESET_ALL}}")

if __name__ == "__main__":
    main()
