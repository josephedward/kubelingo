import logging
from pathlib import Path
import yaml
from typing import Dict, List, Any, Generator
import os
import json
from datetime import datetime

try:
    import openai
except ImportError:
    openai = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

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


def _infer_with_openai(question: Dict[str, Any]) -> Dict[str, str]:
    """
    Uses OpenAI to infer the subject matter and exercise category for a question.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logging.warning(
            "OPENAI_API_KEY not set. Cannot use AI to infer question categories. Skipping."
        )
        return {}

    if not openai:
        logging.warning("OpenAI SDK not installed. Cannot use OpenAI. Skipping.")
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
            f"Using OpenAI to infer category for question ID: {question.get('id', 'N/A')}"
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
                f"OpenAI classification successful for question {question.get('id', 'N/A')}: "
                f"Subject='{inferred['subject_matter']}', Category='{inferred['exercise_category']}'"
            )
            return inferred
        else:
            logging.warning(
                f"OpenAI response for question {question.get('id', 'N/A')} is missing required keys: {content}"
            )
            return {}

    except openai.APIError as e:
        logging.error(
            f"OpenAI API error while processing question {question.get('id', 'N/A')}: {e}"
        )
        return {}
    except json.JSONDecodeError as e:
        logging.error(
            f"Failed to parse JSON from OpenAI response for question {question.get('id', 'N/A')}: {e}"
        )
        return {}
    except Exception as e:
        logging.error(
            f"An unexpected error occurred during OpenAI inference for question {question.get('id', 'N/A')}: {e}"
        )
        return {}


def _infer_with_gemini(question: Dict[str, Any]) -> Dict[str, str]:
    """
    Uses Google Gemini to infer the subject matter and exercise category.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logging.warning("GOOGLE_API_KEY not set. Cannot use Gemini. Skipping.")
        return {}

    if not genai:
        logging.warning("Google Generative AI SDK not installed. Cannot use Gemini. Skipping.")
        return {}

    try:
        genai.configure(api_key=api_key)

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

Provide your response as a single, raw JSON object with two keys: "subject_matter" and "exercise_category". Do not wrap it in markdown backticks or add any other text or explanation.
Example response:
{{
  "subject_matter": "Pod Lifecycle",
  "exercise_category": "basic"
}}
"""
        logging.info(
            f"Using Gemini to infer category for question ID: {question.get('id', 'N/A')}"
        )
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        content = response.text
        inferred = json.loads(content)

        if "subject_matter" in inferred and "exercise_category" in inferred:
            logging.info(
                f"Gemini classification successful for question {question.get('id', 'N/A')}: "
                f"Subject='{inferred['subject_matter']}', Category='{inferred['exercise_category']}'"
            )
            return inferred
        else:
            logging.warning(
                f"Gemini response for question {question.get('id', 'N/A')} is missing required keys: {content}"
            )
            return {}
            
    except json.JSONDecodeError as e:
        logging.error(
            f"Failed to parse JSON from Gemini response for question {question.get('id', 'N/A')}: {e}"
        )
        return {}
    except Exception as e:
        logging.error(
            f"An unexpected error occurred during Gemini inference for question {question.get('id', 'N/A')}: {e}"
        )
        return {}


def _infer_category_and_type_with_ai(question: Dict[str, Any]) -> Dict[str, str]:
    """
    Uses the configured AI backend to infer subject matter and exercise category.
    """
    ai_backend = os.getenv("AI_BACKEND", "openai").lower()

    if ai_backend == "gemini":
        return _infer_with_gemini(question)
    
    if ai_backend != "openai":
        logging.warning(f"Unsupported AI_BACKEND '{ai_backend}'. Defaulting to OpenAI.")

    return _infer_with_openai(question)




def _get_project_root() -> Path:
    """Gets the project root directory."""
    return Path(__file__).resolve().parent.parent


def _find_yaml_files(search_dir: Path) -> Generator[Path, None, None]:
    """Finds all YAML files in a directory."""
    for ext in ("*.yaml", "*.yml"):
        yield from search_dir.rglob(ext)


def bootstrap_quizzes_from_yaml() -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """
    Indexes YAML files, uses AI to categorize if needed, writes a consolidated
    timestamped YAML file, and returns a structured dictionary of quizzes.
    """
    logging.info("Starting bootstrap process: loading quizzes from YAML...")
    project_root = _get_project_root()
    yaml_dir = project_root / "yaml"

    if not yaml_dir.is_dir():
        logging.warning(f"YAML source directory not found at: {yaml_dir}")
        logging.warning("No quizzes will be loaded.")
        return {}

    logging.info(f"Searching for YAML files in {yaml_dir}...")
    yaml_files = list(_find_yaml_files(yaml_dir))

    if not yaml_files:
        logging.warning(f"No YAML files found in {yaml_dir}.")
        return {}

    logging.info(f"Found {len(yaml_files)} YAML file(s). Consolidating and processing...")

    all_questions = []
    for yaml_file in yaml_files:
        try:
            with open(yaml_file, "r") as f:
                documents = yaml.safe_load_all(f)
                for data in documents:
                    if data and "questions" in data:
                        all_questions.extend(data["questions"])
        except Exception as e:
            logging.error(f"Error processing file {yaml_file.name}: {e}")

    logging.info(f"Found a total of {len(all_questions)} questions to process.")
    
    processed_questions = []
    EXERCISE_CATEGORY_TO_TYPE = {
        "basic": "socratic",
        "command": "command",
        "manifest": "manifest",
    }
    
    for question in all_questions:
        q_id = question.get("id", "N/A")
        subject_matter = question.get("category")
        exercise_type = question.get("type")
        exercise_category = TYPE_TO_EXERCISE_CATEGORY.get(exercise_type) if exercise_type else None

        if not subject_matter or not exercise_category:
            logging.info(f"Missing 'category' or valid 'type' for question ID: {q_id}. Attempting AI inference.")
            inferred_data = _infer_category_and_type_with_ai(question)
            if inferred_data:
                inferred_subject = inferred_data.get("subject_matter")
                inferred_category = inferred_data.get("exercise_category")

                if inferred_subject and inferred_category in EXERCISE_CATEGORY_TO_TYPE:
                    question["category"] = inferred_subject
                    question["type"] = EXERCISE_CATEGORY_TO_TYPE[inferred_category]
                    logging.info(f"Successfully updated question {q_id} via AI.")
                else:
                    logging.warning(f"AI inference for {q_id} produced invalid data. Skipping updates.")
        
        # Final check before adding to processed list
        final_subject = question.get("category")
        final_type = question.get("type")
        if final_subject and TYPE_TO_EXERCISE_CATEGORY.get(final_type):
             processed_questions.append(question)
        else:
             logging.warning(f"Skipping question {q_id} due to missing/invalid category or type after processing.")

    if processed_questions:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = yaml_dir / f"categorized_questions_{timestamp}.yaml"
        logging.info(f"Writing {len(processed_questions)} categorized questions to {output_filename}")
        try:
            with open(output_filename, 'w') as f:
                yaml.dump({'questions': processed_questions}, f, default_flow_style=False, sort_keys=False, indent=2)
        except Exception as e:
            logging.error(f"Failed to write categorized questions to file: {e}")


    quizzes: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    for question in processed_questions:
        subject = question.get("category")
        ex_type = question.get("type")
        ex_category = TYPE_TO_EXERCISE_CATEGORY.get(ex_type)

        if subject and ex_category:
            if subject not in quizzes:
                quizzes[subject] = {"basic": [], "command": [], "manifest": []}
            quizzes[subject][ex_category].append(question)

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
