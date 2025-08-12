import logging
from pathlib import Path
import yaml
from typing import Dict, List, Any, Generator
import os
import json
import openai

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Mapping from YAML 'type' to our internal 'Exercise Category'
# Based on shared_context.md
TYPE_TO_EXERCISE_CATEGORY = {
    "socratic": "basic",
    "basic": "basic",
    "command": "command",
    "manifest": "manifest",
    "yaml_author": "manifest",
    "yaml_edit": "manifest",
    "live_k8s_edit": "manifest",
}


def _infer_category_and_type_with_ai(question: Dict[str, Any]) -> Dict[str, str]:
    """
    Uses OpenAI to infer the subject matter and exercise category for a question.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logging.warning(
            "OPENAI_API_KEY not set. Cannot use AI to infer question categories. Skipping."
        )
        return {}

    try:
        client = openai.OpenAI(api_key=api_key)

        # Create a compact version of the question for the prompt
        question_for_prompt = {
            "id": question.get("id"),
            "prompt": question.get("prompt"),
            "context": question.get("context"),
        }
        question_json = json.dumps(
            {k: v for k, v in question_for_prompt.items() if v is not None}
        )

        prompt = f"""
You are an expert programmer and Kubernetes administrator. Your task is to categorize a quiz question for the Kubelingo learning platform.
Based on the question's content below, infer two things:
1. "subject_matter": A short, descriptive topic for the question. Examples: "Pod Lifecycle", "Kubectl Operations", "Service Networking", "ConfigMap and Secrets", "YAML Authoring".
2. "exercise_category": Must be one of these three exact values: 'basic', 'command', or 'manifest'.
   - 'basic': For conceptual questions.
   - 'command': For questions expecting a single-line command answer (e.g., kubectl, vim).
   - 'manifest': For questions about creating or editing Kubernetes YAML files.

Here is the question data:
---
{question_json}
---

Provide your response as a single JSON object with two keys: "subject_matter" and "exercise_category". Do not add any other text or explanation.
Example response:
{{
  "subject_matter": "Pod Lifecycle",
  "exercise_category": "basic"
}}
"""
        logging.info(
            f"Using AI to infer category for question ID: {question.get('id', 'N/A')}"
        )
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content
        inferred = json.loads(content)

        if "subject_matter" in inferred and "exercise_category" in inferred:
            logging.info(
                f"AI classification successful for question {question.get('id', 'N/A')}: "
                f"Subject='{inferred['subject_matter']}', Category='{inferred['exercise_category']}'"
            )
            return inferred
        else:
            logging.warning(
                f"AI response for question {question.get('id', 'N/A')} is missing required keys: {content}"
            )
            return {}

    except openai.APIError as e:
        logging.error(
            f"OpenAI API error while processing question {question.get('id', 'N/A')}: {e}"
        )
        return {}
    except json.JSONDecodeError as e:
        logging.error(
            f"Failed to parse JSON from AI response for question {question.get('id', 'N/A')}: {e}"
        )
        return {}
    except Exception as e:
        logging.error(
            f"An unexpected error occurred during AI inference for question {question.get('id', 'N/A')}: {e}"
        )
        return {}


def _get_project_root() -> Path:
    """Gets the project root directory."""
    return Path(__file__).resolve().parent.parent


def _find_yaml_files(search_dir: Path) -> Generator[Path, None, None]:
    """Finds all YAML files in a directory."""
    for ext in ("*.yaml", "*.yml"):
        yield from search_dir.rglob(ext)


def bootstrap_quizzes_from_yaml() -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """
    Indexes YAML files from the consolidated backup directory, categorizes them
    on the fly, and returns a structured dictionary of quizzes.
    """
    logging.info("Starting bootstrap process: loading quizzes from YAML...")
    project_root = _get_project_root()
    yaml_dir = project_root / "yaml"

    if not yaml_dir.is_dir():
        logging.warning(
            f"YAML source directory not found at: {yaml_dir}"
        )
        logging.warning("No quizzes will be loaded.")
        return {}

    logging.info(f"Searching for YAML files in {yaml_dir}...")
    yaml_files = list(_find_yaml_files(yaml_dir))

    if not yaml_files:
        logging.warning(f"No YAML files found in {yaml_dir}.")
        return {}

    logging.info(f"Found {len(yaml_files)} YAML file(s). Processing...")

    quizzes: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

    for yaml_file in yaml_files:
        logging.info(f"Processing file: {yaml_file.name}")
        try:
            with open(yaml_file, "r") as f:
                # Use safe_load_all for multi-document YAML files
                documents = yaml.safe_load_all(f)
                for data in documents:
                    if not data or "questions" not in data:
                        logging.warning(
                            f"Skipping document in {yaml_file.name}: no 'questions' key found or document is empty."
                        )
                        continue

                    for question in data["questions"]:
                        subject_matter = question.get("category")
                        exercise_type = question.get("type")
                        exercise_category = (
                            TYPE_TO_EXERCISE_CATEGORY.get(exercise_type)
                            if exercise_type
                            else None
                        )

                        if not subject_matter or not exercise_category:
                            logging.info(
                                f"Missing 'category' or valid 'type' for question ID: {question.get('id', 'N/A')}. Attempting AI inference."
                            )
                            inferred_data = _infer_category_and_type_with_ai(question)

                            if inferred_data:
                                subject_matter = inferred_data.get("subject_matter")
                                exercise_category = inferred_data.get(
                                    "exercise_category"
                                )

                        if not subject_matter or not exercise_category:
                            logging.warning(
                                f"Skipping question in {yaml_file.name} (id: {question.get('id', 'N/A')}) "
                                f"due to missing 'category' or valid 'type' even after AI attempt."
                            )
                            continue

                        # Validate that the inferred category is a valid one.
                        if exercise_category not in ["basic", "command", "manifest"]:
                            logging.warning(f"AI returned an invalid exercise_category '{exercise_category}' for question {question.get('id', 'N/A')}. Skipping.")
                            continue

                        if subject_matter not in quizzes:
                            quizzes[subject_matter] = {
                                "basic": [],
                                "command": [],
                                "manifest": [],
                            }

                        quizzes[subject_matter][exercise_category].append(question)
                        logging.info(
                            f"  - Indexed question for subject '{subject_matter}', category '{exercise_category}'."
                        )

        except yaml.YAMLError as e:
            logging.error(f"Error parsing YAML file {yaml_file.name}: {e}")
        except Exception as e:
            logging.error(
                f"An unexpected error occurred while processing {yaml_file.name}: {e}"
            )

    logging.info("Bootstrap process completed.")
    num_subjects = len(quizzes)
    num_questions = sum(
        len(q_list) for cat_dict in quizzes.values() for q_list in cat_dict.values()
    )
    logging.info(f"Loaded {num_questions} questions across {num_subjects} subjects.")

    return quizzes


if __name__ == "__main__":
    # For testing the script directly
    loaded_quizzes = bootstrap_quizzes_from_yaml()
    if loaded_quizzes:
        import json
        print("\n--- Loaded Quizzes Summary ---")
        summary = {
            subject: {
                category: len(questions) for category, questions in categories.items()
            }
            for subject, categories in loaded_quizzes.items()
        }
        print(json.dumps(summary, indent=2))
