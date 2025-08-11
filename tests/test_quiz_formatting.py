"""
Tests for question data validation, including schema, formatting, and link validity.
"""
import pytest
import yaml
import re
import requests
from pathlib import Path

# Use the config to get the correct questions directory
from kubelingo.utils.config import QUESTIONS_DIR

URL_REGEX = re.compile(r'https?://[^\s\)"\']+')

def get_question_files():
    """Yield all YAML files from the consolidated questions directory."""
    q_dir = Path(QUESTIONS_DIR)
    if not q_dir.is_dir():
        return []
    files = list(q_dir.glob("**/*.yaml")) + list(q_dir.glob("**/*.yml"))
    return files

def load_yaml_questions(file_path):
    """Load YAML from file_path and return a list of question dicts."""
    try:
        content = file_path.read_text(encoding="utf-8")
        if not content.strip():
            return []
        data = yaml.safe_load(content)
        if data is None:
            return []
        if isinstance(data, list):
            return data
    except yaml.YAMLError as e:
        pytest.fail(f"YAML parsing error in {file_path.name}: {e}")
    return []


# --- Tests for Formatting and Schema ---

@pytest.mark.parametrize("file_path", get_question_files())
def test_yaml_is_list(file_path):
    """Ensures that the YAML file contains a list of questions."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        assert data is None or isinstance(data, list), (
            f"{file_path.name}: Top-level structure must be a list of questions."
        )

@pytest.mark.parametrize("file_path", get_question_files())
def test_unique_ids_within_file(file_path):
    questions = load_yaml_questions(file_path)
    if not questions:
        pytest.skip(f"No questions found in {file_path.name}")
    ids = [q.get("id") for q in questions if q]
    # Check for missing IDs
    assert None not in ids, f"{file_path.name}: Found questions with a missing 'id' field."
    # Check for duplicate IDs
    duplicates = {x for x in ids if ids.count(x) > 1}
    assert not duplicates, f"{file_path.name}: duplicate ids found: {duplicates}"

def test_unique_ids_across_all_files():
    """Ensure question IDs are unique across all YAML quiz files."""
    seen_ids = {}
    for file_path in get_question_files():
        questions = load_yaml_questions(file_path)
        for q in questions:
            if not q: continue
            q_id = q.get("id")
            if q_id in seen_ids:
                pytest.fail(
                    f"Duplicate question id '{q_id}' found in {file_path.name} "
                    f"and {seen_ids[q_id]}"
                )
            seen_ids[q_id] = file_path.name

@pytest.mark.parametrize("file_path", get_question_files())
def test_question_schema(file_path):
    """Validates the basic schema of each question in a file."""
    questions = load_yaml_questions(file_path)
    if not questions:
        pytest.skip(f"No questions found in {file_path.name}")

    for idx, q in enumerate(questions, 1):
        if not q: continue
        assert isinstance(q, dict), f"{file_path.name}[{idx}]: question should be a dict"
        
        # ID is required
        q_id = q.get("id")
        assert q_id and isinstance(q_id, str), f"{file_path.name}[{idx}]: 'id' is required and must be a string."
        
        # Prompt is required
        prompt = q.get("prompt")
        assert prompt and isinstance(prompt, str), f"{file_path.name}[{idx}]: 'prompt' is required and must be a string."


# --- Tests for Link Validity ---

def get_all_links_from_questions():
    """Collects all unique URLs from all question files for test parametrization."""
    all_links = set()
    for file_path in get_question_files():
        questions = load_yaml_questions(file_path)
        for q in questions:
            if not q: continue
            # Extract links from common fields that contain URLs
            for key in ['source', 'citation']:
                if key in q and isinstance(q[key], str):
                    for match in URL_REGEX.findall(q[key]):
                        all_links.add(match)
            # Legacy links in metadata
            if 'metadata' in q and isinstance(q['metadata'], dict):
                metadata = q['metadata']
                if 'links' in metadata and isinstance(metadata['links'], list):
                    for link in metadata['links']:
                         if isinstance(link, str):
                            for match in URL_REGEX.findall(link):
                                all_links.add(match)

    if not all_links:
        return []
    
    return [pytest.param(link, id=link) for link in sorted(list(all_links))]


@pytest.fixture(scope="session")
def requests_session():
    """Provides a reusable requests.Session for the test session."""
    session = requests.Session()
    session.headers.update({"User-Agent": "kubelingo-link-checker/1.0"})
    return session


@pytest.mark.network
@pytest.mark.parametrize("url", get_all_links_from_questions())
def test_question_link_is_valid(url, requests_session):
    """Checks if a documentation link from a question file is valid."""
    try:
        response = requests_session.head(url, allow_redirects=True, timeout=20)
        if response.status_code >= 400:
            response = requests_session.get(url, allow_redirects=True, timeout=20)
        response.raise_for_status()
    except requests.RequestException as e:
        pytest.fail(f"Broken link: {url} ({e})")
