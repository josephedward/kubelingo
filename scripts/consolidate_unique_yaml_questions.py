#!/usr/bin/env python3
import os
import sys
import yaml
import json
import uuid
from typing import Dict, Any

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from kubelingo.utils.path_utils import find_yaml_files
from kubelingo.utils.config import QUESTION_DIRS, SUBJECT_MATTER, get_api_key
from kubelingo.database import add_question, get_db_connection
from kubelingo.utils.ui import Fore, Style

try:
    import openai
except ImportError:
    print(f"{Fore.RED}OpenAI library not found. Please install it with 'pip install openai'.{Style.RESET_ALL}")
    sys.exit(1)

EXERCISE_TYPES = {
    "Basic": "Simple conceptual question with a text answer, evaluated by AI (maps to 'socratic' type).",
    "Command": "A question that requires a single-line shell command, like `kubectl`, as an answer (maps to 'command' type).",
    "Manifest": "A question that requires authoring or editing a Kubernetes YAML manifest in an editor (maps to 'yaml_author' or 'yaml_edit' type)."
}

TYPE_MAPPING = {
    "Basic": "socratic",
    "Command": "command",
    "Manifest": "yaml_author"  # Defaulting to author, as it's the most common manifest task from scratch
}

def get_ai_classification(question_prompt: str) -> Dict[str, Any]:
    """
    Uses OpenAI to classify a question's exercise type and subject matter.
    """
    subject_matter_list = "\n".join([f"{i+1}. {s}" for i, s in enumerate(SUBJECT_MATTER)])
    exercise_type_list = "\n".join([f"- {name}: {desc}" for name, desc in EXERCISE_TYPES.items()])

    prompt = f"""
Analyze the following Kubernetes practice question and classify it according to the provided schema.
Return your answer as a single valid JSON object with two keys: "exercise_type" and "subject_matter".

**Question to Classify:**
"{question_prompt}"

---
**Classification Schema:**

1.  **`exercise_type`**: Choose ONE of the following types that best fits the question.
{exercise_type_list}

2.  **`subject_matter`**: Choose the ONE most relevant category from this list.
{subject_matter_list}

---
**Response Format:**
Return only a single valid JSON object, with no other text before or after it. Example:
{{
  "exercise_type": "Command",
  "subject_matter": "Core workloads (Pods, ReplicaSets, Deployments; rollouts/rollbacks)"
}}
"""
    try:
        client = openai.OpenAI()
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo-1106", # Model optimized for JSON output
            messages=[
                {"role": "system", "content": "You are a helpful assistant that classifies Kubernetes questions according to a specific schema."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        response_content = completion.choices[0].message.content
        return json.loads(response_content)
    except Exception as e:
        print(f"  {Fore.RED}Error calling OpenAI API: {e}{Style.RESET_ALL}")
        return None

def main():
    """
    Main function to find all YAML questions, deduplicate them, and use AI to classify them.
    The classified questions are then added or updated in the database.
    """
    print(f"{Fore.CYAN}--- Starting YAML Question Consolidation and Classification ---{Style.RESET_ALL}")

    api_key = os.getenv('OPENAI_API_KEY') or get_api_key()
    if not api_key:
        print(f"{Fore.RED}OpenAI API key is not configured. Please set it using 'kubelingo config set openai'.{Style.RESET_ALL}")
        sys.exit(1)
    openai.api_key = api_key

    print("1. Searching for YAML question files...")
    yaml_files = find_yaml_files(QUESTION_DIRS)
    if not yaml_files:
        print(f"{Fore.YELLOW}No YAML files found in configured directories. Exiting.{Style.RESET_ALL}")
        return

    print(f"Found {len(yaml_files)} YAML file(s).")

    print("\n2. Loading and deduplicating questions...")
    unique_questions = {}
    question_sources = {}
    for file_path in yaml_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if not isinstance(data, list):
                    continue
                for q in data:
                    prompt = q.get('prompt')
                    if prompt and prompt not in unique_questions:
                        unique_questions[prompt] = q
                        question_sources[prompt] = os.path.basename(str(file_path))
        except Exception as e:
            print(f"{Fore.YELLOW}Warning: Could not process file {file_path}: {e}{Style.RESET_ALL}")

    if not unique_questions:
        print(f"{Fore.YELLOW}No unique questions found in YAML files. Exiting.{Style.RESET_ALL}")
        return

    print(f"Found {len(unique_questions)} unique questions.")

    print("\n3. Classifying questions using AI and updating database...")
    conn = get_db_connection()
    updated_count = 0
    failed_count = 0

    try:
        for i, (prompt, question_data) in enumerate(unique_questions.items()):
            print(f"Processing question {i+1}/{len(unique_questions)}: '{prompt[:70].strip()}...'")

            classification = get_ai_classification(prompt)

            if classification and 'exercise_type' in classification and 'subject_matter' in classification:
                ex_type_str = classification['exercise_type']
                category = classification['subject_matter']

                question_type = TYPE_MAPPING.get(ex_type_str, "socratic")

                q_id = question_data.get('id', str(uuid.uuid4()))
                source_file = question_data.get('source_file') or question_sources.get(prompt)

                try:
                    # add_question with 'type' kwarg should update the question type.
                    # This assumes add_question can handle arbitrary kwargs that match column names.
                    add_question(
                        conn=conn,
                        id=q_id,
                        prompt=prompt,
                        source_file=source_file,
                        response=question_data.get('response'),
                        category=category,
                        validation_steps=question_data.get('validation_steps'),
                        validator=question_data.get('validator'),
                        type=question_type,
                        review=False # Reset review status after processing
                    )
                    updated_count += 1
                    print(f"  {Fore.GREEN}-> Classified as Type: {ex_type_str}, Category: {category}{Style.RESET_ALL}")
                except Exception as e:
                    failed_count += 1
                    print(f"  {Fore.RED}Error updating database for question ID {q_id}: {e}{Style.RESET_ALL}")
            else:
                failed_count += 1
                print(f"  {Fore.YELLOW}Could not get a valid classification.{Style.RESET_ALL}")

        conn.commit()
    finally:
        conn.close()

    print(f"\n{Fore.CYAN}--- Consolidation Complete ---{Style.RESET_ALL}")
    print(f"  - {Fore.GREEN}Successfully processed and updated: {updated_count}{Style.RESET_ALL}")
    print(f"  - {Fore.RED}Failed or skipped: {failed_count}{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
