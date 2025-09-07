import uuid
import json
import yaml
import os

def import_from_file(file_path: str) -> list:
    """Import questions from a file."""
    # Support importing from URL
    if file_path.startswith(('http://', 'https://')):
        try:
            import requests
        except ImportError:
            raise RuntimeError("requests library is required to import from URL")
        resp = requests.get(file_path)
        resp.raise_for_status()
        content = resp.text
        _, extension = os.path.splitext(file_path)
        extension = extension.lower()
        # Parse based on extension
        items = []
        if extension == '.json':
            data = json.loads(content)
            if isinstance(data, dict) and 'questions' in data:
                data = data['questions']
        elif extension in ('.yaml', '.yml'):
            data = yaml.safe_load(content)
            if isinstance(data, dict) and 'questions' in data:
                data = data['questions']
        else:
            return []
        # Build questions list
        for item in data or []:
            items.append(format_question(
                topic=item.get('topic'),
                question=item.get('question'),
                suggested_answer=item.get('suggested_answer'),
                source=item.get('source'),
                qid=item.get('id')
            ))
        return items
    # Local file import
    # Let file I/O errors propagate for non-existent files
    _, extension = os.path.splitext(file_path)
    if extension == '.json':
        return _parse_json(file_path)
    elif extension in ('.yaml', '.yml'):
        return _parse_yaml(file_path)
    else:
        return []

def _parse_json(file_path: str) -> list:
    """Parse a JSON file for questions."""
    with open(file_path, 'r') as f:
        data = json.load(f)
    questions = []
    for item in data:
        questions.append(format_question(
            topic=item.get('topic'),
            question=item.get('question'),
            suggested_answer=item.get('suggested_answer'),
            source=item.get('source')
        ))
    return questions

def _parse_yaml(file_path: str) -> list:
    """Parse a YAML file for questions."""
    with open(file_path, 'r') as f:
        data = yaml.safe_load(f)
    questions = []
    for item in data:
        questions.append(format_question(
            topic=item.get('topic'),
            question=item.get('question'),
            suggested_answer=item.get('suggested_answer'),
            source=item.get('source')
        ))
    return questions

import uuid

def format_question(
    topic: str,
    question: str,
    suggested_answer: str,
    source: str,
    qid: str = None
) -> dict:
    """
    Build a question dict matching the canonical schema:
      {
        "id": "a1b2c3d4",
        "topic": "pods",
        "question": "...",
        "source": "...",
        "suggested_answer": "...",
        "user_answer": "",
        "ai_feedback": ""
      }

    If qid is provided, use it, otherwise generate an 8-character hex id.
    Strips leading/trailing whitespace from suggested_answer.
    """
    qid_str = qid if qid else uuid.uuid4().hex[:8]
    return {
        "id": qid_str,
        "topic": topic,
        "question": question,
        "source": source,
        "suggested_answer": suggested_answer.strip(),
        "user_answer": "",
        "ai_feedback": "",
    }