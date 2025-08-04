"""
Tests for checking documentation links in the docs/ directory.
"""
import pytest
import requests
import re
from pathlib import Path

# Directory containing documentation files
DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"

# Regex for extracting URLs
URL_REGEX = re.compile(r'https?://[^\s\)"\']+')

def get_doc_files():
    """Yield all markdown files in docs/, excluding hidden/system files."""
    return [p for p in DOCS_DIR.rglob("*.md") if not p.name.startswith('.')]

def extract_links_from_file(file_path):
    """Extract all URLs from a markdown file using a regex."""
    text = file_path.read_text(encoding="utf-8")
    return set(URL_REGEX.findall(text))

def pytest_params_for_links():
    links = set()
    for file_path in get_doc_files():
        links.update(extract_links_from_file(file_path))
    if not links:
        pytest.fail("No documentation links found in docs/ directory")
    return [pytest.param(link, id=link) for link in sorted(links)]

@pytest.fixture(scope="session")
def requests_session():
    session = requests.Session()
    session.headers.update({"User-Agent": "kubelingo-doc-link-checker/1.0"})
    return session

@pytest.mark.network
@pytest.mark.parametrize("url", pytest_params_for_links())
def test_docs_links_valid(url, requests_session):
    """
    Checks if documentation links are reachable and return a 200-level status code.
    """
    try:
        response = requests_session.head(url, allow_redirects=True, timeout=20)
        if response.status_code >= 400:
            response = requests_session.get(url, allow_redirects=True, timeout=20)
        response.raise_for_status()
    except requests.RequestException as e:
        pytest.fail(f"Broken link: {url} ({e})")