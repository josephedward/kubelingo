import pytest
pytest.skip("JSON-based review flow deprecated; flagging uses YAML and separate store", allow_module_level=True)
import pytest
pytest.skip("JSON-based review flow deprecated; using YAML-only and id-based flagging", allow_module_level=True)
import json
from unittest.mock import MagicMock

from kubelingo.modules.base.session import SessionManager
from kubelingo.modules.kubernetes.session import load_questions


def test_review_flow(tmp_path):
    """
    Tests the full review flag lifecycle:
    1. Initialize data with one item flagged.
    2. Mark a second item for review.
    3. Verify both items are flagged.
    4. Un-mark the original item.
    5. Verify only the second item remains flagged.
    """
    data_file = tmp_path / "testdata.json"

    # Initial data state: 'bar' is flagged for review.
    initial_data = [{
        'category': 'TestCat',
        'prompts': [
            {'prompt': 'foo', 'response': 'foo', 'type': 'command'},
            {'prompt': 'bar', 'response': 'bar', 'type': 'command', 'review': True}
        ]
    }]
    with open(data_file, 'w') as f:
        json.dump(initial_data, f, indent=2)

    logger = MagicMock()
    session_manager = SessionManager(logger)

    # --- Mark 'foo' for review ---
    session_manager.mark_question_for_review(str(data_file), 'TestCat', 'foo')

    # Verify both 'foo' and 'bar' are now flagged.
    qs = load_questions(str(data_file))
    flagged = sorted([q['prompt'] for q in qs if q.get('review')])
    assert flagged == ['bar', 'foo']

    # --- Unmark 'bar' for review ---
    session_manager.unmark_question_for_review(str(data_file), 'TestCat', 'bar')

    # Verify only 'foo' remains flagged.
    qs2 = load_questions(str(data_file))
    flagged2 = [q['prompt'] for q in qs2 if q.get('review')]
    assert flagged2 == ['foo']
