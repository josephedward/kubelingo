import os
import uuid
import yaml
from typing import Any, Dict, Optional


REQUIRED_FIELDS = [
    "id",
    "topic",
    "question",
    "source",
    "suggested_answer",
    "user_answer",
    "ai_feedback",
]


def _pick_suggested_answer(suggestion: Any) -> Any:
    """Pick a canonical suggested_answer from a 'suggestion' field.

    - If suggestion is a list, prefer the first element.
    - If it's a dict/list, keep as structured YAML; otherwise a string.
    """
    if isinstance(suggestion, list) and suggestion:
        return suggestion[0]
    return suggestion


def normalize_question_dict(q: Dict[str, Any], default_topic: Optional[str] = None) -> Dict[str, Any]:
    """Normalize various question dict shapes into the canonical schema.

    Preserves original fields and adds canonical ones when missing.
    - Accepts either 'suggested_answer' or legacy 'suggestion'.
    - Generates 'id' when absent.
    - Ensures 'user_answer' and 'ai_feedback' exist.
    - topic falls back to provided default_topic.
    """
    norm = dict(q) if isinstance(q, dict) else {}

    # ID
    if not norm.get("id"):
        norm["id"] = uuid.uuid4().hex[:8]

    # Topic
    if not norm.get("topic"):
        if default_topic:
            norm["topic"] = default_topic
        else:
            norm["topic"] = ""

    # Suggested answer
    if "suggested_answer" not in norm:
        if "suggestion" in norm:
            norm["suggested_answer"] = _pick_suggested_answer(norm["suggestion"])
        else:
            norm["suggested_answer"] = ""

    # Required empty fields
    norm.setdefault("user_answer", "")
    norm.setdefault("ai_feedback", "")

    return norm


def write_question_file(question: Dict[str, Any], target_dir: str) -> str:
    """Write a single question to `target_dir/<id>.yaml` and return the path.

    The question is normalized before writing. Creates the directory if needed.
    """
    os.makedirs(target_dir, exist_ok=True)
    qn = normalize_question_dict(question, question.get("topic"))
    qid = qn.get("id")
    path = os.path.join(target_dir, f"{qid}.yaml")
    with open(path, "w") as f:
        yaml.safe_dump(qn, f, sort_keys=False)
    return path

