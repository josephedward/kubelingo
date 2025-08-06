import pytest
import requests
import yaml
import json
import re
from pathlib import Path
from typing import Set, Generator, List

# --- Configuration ---
QUESTION_DATA_DIR = Path(__file__).resolve().parent.parent / "question-data"
# Links that are known to be problematic or should be skipped can be added here.
LINKS_TO_SKIP = {}

# --- Helper Functions ---

def get_quiz_files() -> Generator[Path, None, None]:
    """
    Finds all YAML and JSON quiz files, looking only in the 'yaml' and 'json'
    subdirectories of the question-data directory.
    """
    yaml_dir = QUESTION_DATA_DIR / "yaml"
    if yaml_dir.is_dir():
        yield from yaml_dir.glob("*.yaml")

    json_dir = QUESTION_DATA_DIR / "json"
    if json_dir.is_dir():
        yield from json_dir.glob("*.json")

URL_REGEX = re.compile(r'https?://[^\s\)"\']+')

def extract_links_from_file(file_path: Path) -> Set[str]:
    """Extracts all 'source' and 'citation' URLs from a given quiz file."""
    links = set()
    # Extract 'source' and 'citation' URLs without full YAML parsing to avoid parsing issues
    try:
        text = file_path.read_text(encoding="utf-8")
    except IOError as e:
        pytest.fail(f"Could not read {file_path.relative_to(QUESTION_DATA_DIR.parent)}: {e}")
        return set()
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith('source:') or stripped.startswith('citation:'):
            # Extract URLs from the line
            for match in URL_REGEX.findall(stripped):
                if match not in LINKS_TO_SKIP:
                    links.add(match)

    return links

# --- Pytest Parametrization ---

def get_all_links() -> List[pytest.param]:
    """Collects all unique links from all quiz files for test parametrization."""
    all_links = set()
    for file_path in get_quiz_files():
        all_links.update(extract_links_from_file(file_path))
    
    if not all_links:
        pytest.fail("No documentation links were found in any quiz files.")
    
    # Return a list of links, marked for individual test execution.
    return [pytest.param(link, id=link) for link in sorted(list(all_links))]

# --- Test Case ---

@pytest.mark.network
@pytest.mark.parametrize("url", get_all_links())
def test_documentation_link_is_valid(url: str, requests_session: requests.Session):
    """
    Checks if a documentation link is reachable and returns a 200-level status code.
    This test will be skipped unless run with 'pytest -m network'.
    """
    try:
        # Using a HEAD request is more efficient than GET.
        response = requests_session.head(url, allow_redirects=True, timeout=20)
        response.raise_for_status()  # Fails test if status is 4xx or 5xx
    except requests.RequestException as e:
        pytest.fail(f"Link check failed for {url} with error: {e}")

# --- Fixture for requests.Session ---

@pytest.fixture(scope="session")
def requests_session() -> requests.Session:
    """Provides a reusable requests.Session object for the entire test session."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; kubelingo-link-checker/1.0; +https://github.com/josephedward/kubelingo)"
    })
    return session
