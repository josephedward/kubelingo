"""
Tests for quiz formatting standardization under question-data/yaml.
"""
import pytest
import yaml
import re
from pathlib import Path

# Directory containing quiz YAML files
QUIZ_DIR = Path(__file__).resolve().parent.parent / "question-data" / "yaml"

# Regex for id format: kebab-case alphanumeric and hyphens
ID_REGEX = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')

def get_quiz_files():
    """Yield all quiz YAML files (those with 'quiz' in the filename)."""
    return (
        p for p in QUIZ_DIR.glob("*quiz*.yaml")
        if p.is_file() and p.name != 'master_quiz_with_explanations.yaml'
    )

def load_yaml(file_path):
    """Load YAML from file_path using safe_load."""
    try:
        data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
        return data if data is not None else {}
    except yaml.YAMLError as e:
        pytest.fail(f"YAML parsing error in {file_path.name}: {e}")

@pytest.mark.parametrize("file_path", list(get_quiz_files()))
def test_yaml_is_list_or_has_questions_key(file_path):
    data = load_yaml(file_path)
    # Support two formats: list of questions or dict with 'questions' key
    if isinstance(data, list):
        questions = data
    else:
        assert isinstance(data, dict), (
            f"{file_path.name}: top-level structure must be a list or dict"
        )
        assert "questions" in data, f"{file_path.name}: missing 'questions' key"
        questions = data.get("questions")
        assert isinstance(questions, list), (
            f"{file_path.name}: 'questions' should be a list"
        )
    # Ensure there is at least one question
    assert questions, f"{file_path.name}: no questions found"

@pytest.mark.parametrize("file_path", list(get_quiz_files()))
def test_unique_ids_within_file(file_path):
    data = load_yaml(file_path)
    # Reuse format detection
    questions = data if isinstance(data, list) else data.get("questions", []) or []
    ids = [q.get("id") for q in questions]
    assert None not in ids, f"{file_path.name}: some questions missing 'id'"
    duplicates = {x for x in ids if ids.count(x) > 1}
    assert not duplicates, f"{file_path.name}: duplicate ids found: {duplicates}"

@pytest.mark.parametrize("file_path", list(get_quiz_files()))
def test_question_entries_format(file_path):
    data = load_yaml(file_path)
    questions = data if isinstance(data, list) else data.get("questions", []) or []
    for idx, q in enumerate(questions, 1):
        assert isinstance(q, dict), f"{file_path.name}[{idx}]: question should be a dict"
        # Validate id exists
        id_val = q.get("id")
        assert isinstance(id_val, str), f"{file_path.name}[{idx}]: 'id' should be a string"
        # Prompt / question
        prompt = q.get("prompt") or q.get("question")
        assert isinstance(prompt, str) and prompt.strip(), (
            f"{file_path.name}[{idx}]: missing or empty 'prompt'/'question'"
        )
        # Different quiz formats
        # 1) Vim quiz format with 'answers'
        if "answers" in q:
            answers = q.get("answers")
            assert isinstance(answers, list) and answers, (
                f"{file_path.name}[{idx}]: 'answers' should be a non-empty list"
            )
            for ans in answers:
                assert isinstance(ans, str) and ans.strip(), (
                    f"{file_path.name}[{idx}]: each answer should be a non-empty string"
                )
            explanation = q.get("explanation")
            assert isinstance(explanation, str) and explanation.strip(), (
                f"{file_path.name}[{idx}]: missing or empty 'explanation'"
            )
            source = q.get("source")
            if source:
                assert isinstance(source, str) and source.startswith(("http://", "https://")), (
                    f"{file_path.name}[{idx}]: invalid 'source' link"
                )
            steps = q.get("validation_steps")
            assert isinstance(steps, list), (
                f"{file_path.name}[{idx}]: 'validation_steps' should be a list"
            )
            continue
        # 2) New quiz format with 'links'
        if "links" in q:
            # Enforce kebab-case IDs for new format
            assert ID_REGEX.match(id_val), (
                f"{file_path.name}[{idx}]: id '{id_val}' should be kebab-case"
            )
            # Response
            resp = q.get("response")
            assert isinstance(resp, str) and resp.strip(), (
                f"{file_path.name}[{idx}]: missing or empty 'response'"
            )
            # Category
            cat = q.get("category")
            assert isinstance(cat, str) and cat.strip(), (
                f"{file_path.name}[{idx}]: missing or empty 'category'"
            )
            # Links
            links = q.get("links")
            assert isinstance(links, list) and links, (
                f"{file_path.name}[{idx}]: 'links' should be a non-empty list"
            )
            for link in links:
                assert isinstance(link, str), (
                    f"{file_path.name}[{idx}]: each link should be a string"
                )
                assert link.startswith(("http://", "https://")), (
                    f"{file_path.name}[{idx}]: link '{link}' should start with http:// or https://"
                )
            continue
        # 3) Simple style with top-level 'response' and optional 'citation'
        if "response" in q and "category" in q and not any(k in q for k in ["answers", "links", "metadata"]):
            resp = q.get("response")
            assert isinstance(resp, str) and resp.strip(), (
                f"{file_path.name}[{idx}]: missing or empty 'response'"
            )
            cat = q.get("category")
            assert isinstance(cat, str) and cat.strip(), (
                f"{file_path.name}[{idx}]: missing or empty 'category'"
            )
            citation = q.get("citation")
            if citation:
                assert isinstance(citation, str) and citation.startswith(("http://", "https://")), (
                    f"{file_path.name}[{idx}]: invalid 'citation' link"
                )
            continue
        # 4) Metadata style quizzes
        if "metadata" in q:
            meta = q.get("metadata", {})
            resp = meta.get("response")
            assert isinstance(resp, str) and resp.strip(), (
                f"{file_path.name}[{idx}]: missing or empty metadata 'response'"
            )
            cat = meta.get("category")
            assert isinstance(cat, str) and cat.strip(), (
                f"{file_path.name}[{idx}]: missing or empty metadata 'category'"
            )
            citation = meta.get("citation")
            if citation:
                assert isinstance(citation, str) and citation.startswith(("http://", "https://")), (
                    f"{file_path.name}[{idx}]: invalid metadata 'citation' link"
                )
            continue

        # 5) YAML authoring style quizzes with 'answer' field
        if "answer" in q:
            ans = q.get("answer")
            assert isinstance(ans, str) and ans.strip(), (
                f"{file_path.name}[{idx}]: missing or empty 'answer'"
            )
            continue
        # 5b) Live Kubernetes editing exercises
        if q.get('type') in ('live_k8s', 'live_k8s_edit'):
            # initial_files must be a dict of filename to content
            init_files = q.get('initial_files')
            assert isinstance(init_files, dict) and init_files, (
                f"{file_path.name}[{idx}]: 'initial_files' should be a non-empty dict"
            )
            # validation_steps must be a list of steps
            steps = q.get('validation_steps')
            assert isinstance(steps, list) and steps, (
                f"{file_path.name}[{idx}]: 'validation_steps' should be a non-empty list"
            )
            # explanation should be present
            explanation = q.get('explanation')
            assert isinstance(explanation, str) and explanation.strip(), (
                f"{file_path.name}[{idx}]: missing or empty 'explanation'"
            )
            continue

        # 6) YAML editing exercise with correct_yaml
        if "correct_yaml" in q:
            assert isinstance(q.get('correct_yaml'), str) and q['correct_yaml'].strip()
            continue

        # 7) Question with solution_file (and optional citation)
        if "solution_file" in q:
            assert isinstance(q.get('solution_file'), str) and q['solution_file'].strip()
            citation = q.get('citation')
            if citation:
                assert isinstance(citation, str) and citation.startswith(('http://', 'https://'))
            continue

        # 8) Simple question with a response (and optional source)
        if 'response' in q:
            assert isinstance(q.get('response'), str) and q['response'].strip()
            source = q.get('source')
            if source:
                assert isinstance(source, str) and source.startswith(('http://', 'https://'))
            continue

        # Unknown format
        pytest.fail(f"{file_path.name}[{idx}]: unsupported question format keys: {list(q.keys())}")

def test_unique_ids_across_files():
    """Ensure question IDs are unique across all YAML quiz files."""
    seen = {}
    for file_path in get_quiz_files():
        data = load_yaml(file_path)
        questions = data if isinstance(data, list) else data.get("questions", []) or []
        for q in questions:
            id_val = q.get("id")
            if id_val in seen:
                pytest.fail(
                    f"Duplicate question id '{id_val}' found in {file_path.name} and {seen[id_val]}"
                )
            seen[id_val] = file_path.name
