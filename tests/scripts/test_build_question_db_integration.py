import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure project root is in path for imports to work correctly
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.legacy import build_question_db

class TestBuildQuestionDbIntegration(unittest.TestCase):

    def setUp(self):
        """Set up a temporary environment for the test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.temp_dir.name)

        # 1. Create a mock questions directory and a sample YAML file inside it.
        self.questions_dir = self.root_path / "test-questions"
        self.questions_dir.mkdir()
        self.yaml_file = self.questions_dir / "sample.yaml"
        self.yaml_file.write_text("""
- id: k8s-pod-101
  prompt: What is the basic unit of deployment in Kubernetes?
  answer: A Pod.
  category: "Core Concepts"
  type: socratic
""")

        # 2. Define paths for the database files within the temporary directory.
        self.live_db_path = self.root_path / "kubelingo.db"
        self.master_backup_path = self.root_path / "master.db"
        self.secondary_backup_path = self.root_path / "secondary.db"

        # 3. The backup function in the script expects the parent directory to exist.
        self.master_backup_path.parent.mkdir(exist_ok=True, parents=True)

        # 4. Save original config values from the script's namespace.
        self.original_values = {
            'QUESTIONS_DIR': build_question_db.QUESTIONS_DIR,
            'DATABASE_FILE': build_question_db.DATABASE_FILE,
            'MASTER_DATABASE_FILE': build_question_db.MASTER_DATABASE_FILE,
            'SECONDARY_MASTER_DATABASE_FILE': build_question_db.SECONDARY_MASTER_DATABASE_FILE,
        }

        # 5. Monkeypatch the script's module-level constants to use our temporary paths.
        build_question_db.QUESTIONS_DIR = str(self.questions_dir)
        build_question_db.DATABASE_FILE = str(self.live_db_path)
        build_question_db.MASTER_DATABASE_FILE = str(self.master_backup_path)
        build_question_db.SECONDARY_MASTER_DATABASE_FILE = str(self.secondary_backup_path)

    def tearDown(self):
        """Clean up the temporary environment and restore original config."""
        self.temp_dir.cleanup()
        # Restore original values to avoid side-effects
        for key, value in self.original_values.items():
            setattr(build_question_db, key, value)

    def test_script_creates_and_populates_sqlite_db(self):
        """
        Verifies that build_question_db.py creates a SQLite database,
        populates it from YAML files, and creates backups.
        """
        # Run the main logic of the script
        build_question_db.main()

        # --- Assertions ---

        # 1. Verify the live database was created and populated correctly.
        self.assertTrue(self.live_db_path.exists(), "Live database file was not created.")

        conn = sqlite3.connect(self.live_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT prompt, response, category, schema_category FROM questions WHERE id = 'k8s-pod-101'")
        question_data = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(question_data, "Question 'k8s-pod-101' not found in the database.")
        self.assertEqual(question_data[0], "What is the basic unit of deployment in Kubernetes?")
        self.assertEqual(question_data[1], "A Pod.")
        self.assertEqual(question_data[2], "Core Concepts")
        # Check if 'type: socratic' was correctly mapped to the 'open-ended' schema_category
        self.assertEqual(question_data[3], "open-ended")

        # 2. Verify that the backup database files were created.
        self.assertTrue(self.master_backup_path.exists(), "Master DB backup was not created.")
        self.assertTrue(self.secondary_backup_path.exists(), "Secondary DB backup was not created.")

        # 3. Verify the backup is a valid, non-empty SQLite file containing the data.
        backup_conn = sqlite3.connect(self.master_backup_path)
        backup_cursor = backup_conn.cursor()
        backup_cursor.execute("SELECT COUNT(*) FROM questions")
        count = backup_cursor.fetchone()[0]
        backup_conn.close()
        self.assertEqual(count, 1, "Backup database does not contain the imported question.")
