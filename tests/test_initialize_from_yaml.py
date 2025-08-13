import os
import sys
import sqlite3
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path to allow script import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import the function to test
from scripts.initialize_from_yaml import initialize_from_yaml

# Mock database connection
@pytest.fixture
def mock_db():
    with tempfile.NamedTemporaryFile(suffix=".db") as temp_db:
        conn = sqlite3.connect(temp_db.name)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE questions (
                id TEXT PRIMARY KEY,
                prompt TEXT,
                response TEXT,
                source_file TEXT,
                category_id TEXT,
                subject_id TEXT
            )
        """)
        conn.commit()
        yield conn
        conn.close()

# Mock YAML file
@pytest.fixture
def mock_yaml_file():
    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as temp_yaml:
        temp_yaml.write("""
        - id: "1"
          prompt: "What is a Kubernetes Pod?"
          response: "A Pod is the smallest deployable unit in Kubernetes."
        - id: "2"
          prompt: "How do you check the logs of a pod named 'webapp-123'?"
          response: "kubectl logs webapp-123"
        """)
        temp_yaml_path = temp_yaml.name
    yield temp_yaml_path
    os.remove(temp_yaml_path)

# Mock AICategorizer
@pytest.fixture
def mock_ai_categorizer():
    with patch("scripts.initialize_from_yaml.AICategorizer.categorize_question") as mock_categorize:
        def mock_categorize_side_effect(self, question):
            prompt = question['prompt']
            if "Kubernetes Pod" in prompt:
                return {
                    "exercise_category": "basic",
                    "subject_matter": "Core workloads (Pods, ReplicaSets, Deployments; rollouts/rollbacks)"
                }
            elif "logs of a pod" in prompt:
                return {
                    "exercise_category": "command",
                    "subject_matter": "Observability & troubleshooting (logs, describe/events, kubectl debug/ephemeral containers)"
                }
            raise ValueError("Unexpected question to categorize")
        mock_categorize.side_effect = mock_categorize_side_effect
        yield mock_categorize


# Test function
def test_initialize_from_yaml(mock_db, mock_yaml_file, mock_ai_categorizer):
    # Mock the get_db_connection function to return the mock database
    with patch("scripts.initialize_from_yaml.get_db_connection", return_value=mock_db):
        # Mock the get_project_root function to return the directory containing the mock YAML file
        with patch("scripts.initialize_from_yaml.get_project_root", return_value=Path(mock_yaml_file).parent):
            # Run the function
            initialize_from_yaml()

            # Verify the database contents
            cursor = mock_db.cursor()
            cursor.execute("SELECT * FROM questions")
            rows = cursor.fetchall()

            assert len(rows) == 2  # Two questions should be inserted

            # Verify the first question
            assert rows[0][1] == "What is a Kubernetes Pod?"
            assert rows[0][4] == "basic"
            assert rows[0][5] == "Core workloads (Pods, ReplicaSets, Deployments; rollouts/rollbacks)"

            # Verify the second question
            assert rows[1][1] == "How do you check the logs of a pod named 'webapp-123'?"
            assert rows[1][4] == "command"
            assert rows[1][5] == "Observability & troubleshooting (logs, describe/events, kubectl debug/ephemeral containers)"
