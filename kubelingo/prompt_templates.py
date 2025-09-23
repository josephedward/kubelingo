from typing import Dict


def build_prompt(question_type: str, topic: str) -> Dict[str, str]:
    """Return a dict with 'system' and 'user' prompt strings for the given type.
    The model must return strict JSON with required fields.
    """
    base_rules = (
        "You are generating CKAD-quality practice questions."
        " Always return a single JSON object, no prose, no markdown."
        " Use keys: type, topic, question, suggested_answer, source."
        " For MCQ also include 'options' (list of 4 with exactly 3 plausible but wrong, 1 correct)."
        " For True/False set suggested_answer to 'true' or 'false'."
        " For Vocab set suggested_answer to the single correct term only."
        " For Commands ensure the command is syntactically correct and includes all variables stated in the question."
        " For Manifests return valid YAML under suggested_answer; it must parse and include apiVersion and kind."
        " Prefer official Kubernetes docs for 'source' if known; otherwise empty string is allowed."
    )

    sys = base_rules

    if question_type == 'true_false':
        user = (
            f"Generate a True/False question in the '{topic}' domain."
            " Make it non-trivial and relevant to Kubernetes usage."
            " Output JSON."
        )
    elif question_type == 'vocab':
        user = (
            f"Generate a vocabulary question for Kubernetes '{topic}'."
            " The question must describe a concept and ask for the term; do not include the term in the question."
            " Output JSON."
        )
    elif question_type == 'mcq':
        user = (
            f"Generate a 4-option multiple choice question for '{topic}'."
            " Include exactly 3 deceptive distractors and 1 correct answer."
            " Output JSON."
        )
    elif question_type == 'commands':
        user = (
            f"Generate a command question for '{topic}'."
            " The question must state all variable values (names, images, ports, etc.)."
            " The suggested_answer must be a syntactically correct kubectl/helm or linux command as a single string."
            " Output JSON."
        )
    elif question_type == 'manifests':
        user = (
            f"Generate a manifest question for '{topic}'."
            " The question must state all variable values (names, images, ports, etc.)."
            " The suggested_answer must be properly formatted YAML for a Kubernetes resource, with apiVersion and kind."
            " Output JSON."
        )
    else:
        raise ValueError(f"Unsupported question type: {question_type}")

    return {"system": sys, "user": user}

