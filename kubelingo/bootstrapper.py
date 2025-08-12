import logging
from pathlib import Path
import yaml
from typing import Dict, List, Any, Generator

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Mapping from YAML 'type' to our internal 'Exercise Category'
# Based on shared_context.md
TYPE_TO_EXERCISE_CATEGORY = {
    "socratic": "basic",
    "command": "command",
    "manifest": "manifest",
}


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

                        if not subject_matter or not exercise_type:
                            logging.warning(
                                f"Skipping question in {yaml_file.name} due to missing 'category' or 'type'."
                            )
                            continue

                        exercise_category = TYPE_TO_EXERCISE_CATEGORY.get(exercise_type)
                        if not exercise_category:
                            logging.warning(
                                f"Skipping question in {yaml_file.name}: unknown type '{exercise_type}'."
                            )
                            continue

                        if subject_matter not in quizzes:
                            quizzes[subject_matter] = {"basic": [], "command": [], "manifest": []}

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
