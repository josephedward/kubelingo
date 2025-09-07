import pytest
from cli import is_diverse

@pytest.mark.parametrize("new, recent, expected", [
    # Identical question should not be considered diverse
    ("foo", ["foo"], False),
    # Case-insensitive identical
    ("Foo", ["foo"], False),
    # Recent question is substring of new
    ("This is a Kubernetes test", ["Kubernetes"], False),
    # New question is substring of recent
    ("Pod management basics", ["management"], False),
    # Completely different questions are diverse
    ("What is a service?", ["How to deploy pods?"], True),
    # Partial overlap but not substring should be diverse
    ("Networking fundamentals", ["Net work fundamentals"], True),
    # Empty recent questions always diverse
    ("Any question", [], True),
])
def test_is_diverse_various_cases(new, recent, expected):
    assert is_diverse(new, recent) == expected