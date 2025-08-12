import sqlite3
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from kubelingo.bootstrap import bootstrap_on_startup
from kubelingo.database import get_db_connection, init_db


@pytest.fixture
def temp_project(tmp_path):
    """Creates a temporary project structure for testing."""
    project_root = tmp_path / "kubelingo_project"
    (project_root / ".kubelingo").mkdir(parents=True)
    (project_root / "yaml").mkdir(parents=True)
    return project_root


@pytest.fixture
def temp_db_conn(temp_project):
    """Provides a connection to a temporary, clean database for each test."""
    db_path = temp_project / ".kubelingo" / "test.db"
    # Ensure the DB is initialized with the correct schema before the test runs
    init_db(str(db_path))
    conn = get_db_connection(str(db_path))
    yield conn
    conn.close()


def test_bootstrap_from_yaml_with_mocked_ai(temp_project, temp_db_conn):
    """
    Tests that bootstrap_on_startup correctly loads questions from a YAML file,
    using a mocked AI categorizer to avoid network calls and API errors.
    """
    # 1. Prepare a dummy YAML backup file in the temporary project structure
    yaml_dir = temp_project / "yaml"
    yaml_file = yaml_dir / "consolidated_unique_questions_20250101_000000.yaml"

    questions_data = {
        "questions": [
            {
                "id": "q1-pod",
                "prompt": "What is a Kubernetes Pod?",
                "answer": "It is the smallest deployable unit.",
                "type": "socratic",
                "category": "Core Concepts"
            },
            {
                "id": "q2-get-pods",
                "prompt": "How do you list all pods in the current namespace?",
                "answer": "kubectl get pods",
                "type": "command",
                "category": "CLI Commands"
            }
        ]
    }
    with open(yaml_file, 'w') as f:
        yaml.dump(questions_data, f)

    # 2. Mock external dependencies: AI Categorizer, project root, and DB connection
    mock_categorizer = MagicMock()

    def mock_categorize_question(question):
        prompt = question['prompt']
        if "Pod" in prompt:
            return {'exercise_category': 'basic', 'subject_matter': 'Core Concepts'}
        if "list all pods" in prompt:
            return {'exercise_category': 'command', 'subject_matter': 'Kubectl CLI usage'}
        return None

    mock_categorizer.categorize_question.side_effect = mock_categorize_question

    with patch('kubelingo.bootstrap.get_project_root', return_value=temp_project), \
         patch('kubelingo.bootstrap.get_db_connection', return_value=temp_db_conn), \
         patch('kubelingo.bootstrap.AICategorizer', return_value=mock_categorizer) as mock_ai_class:

        # 3. Run the bootstrap process
        bootstrap_on_startup()

    # 4. Verify that the questions were correctly inserted into the database
    cursor = temp_db_conn.cursor()
    cursor.execute("SELECT id, prompt, category_id, subject_id FROM questions ORDER BY id")
    results = [dict(row) for row in cursor.fetchall()]

    assert len(results) == 2
    assert results[0]['id'] == 'q1-pod'
    assert results[0]['prompt'] == "What is a Kubernetes Pod?"
    assert results[0]['category_id'] == 'basic'
    assert results[0]['subject_id'] == 'Core Concepts'

    assert results[1]['id'] == 'q2-get-pods'
    assert results[1]['prompt'] == "How do you list all pods in the current namespace?"
    assert results[1]['category_id'] == 'command'
    assert results[1]['subject_id'] == 'Kubectl CLI usage'

    # 5. Verify that the AI categorizer was called as expected
    mock_ai_class.assert_called_once()
    assert mock_categorizer.categorize_question.call_count == 2
