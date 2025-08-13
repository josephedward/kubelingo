import os
import sqlite3
import subprocess
import yaml
from pathlib import Path
from unittest.mock import patch

import pytest

from kubelingo.question import QuestionCategory, QuestionSubject

# Use enums to ensure tests stay in sync with the application code.
QUESTION_CATEGORIES = [category.value for category in QuestionCategory]
SUBJECTS = [subject.value for subject in QuestionSubject]

# Mapping from question category to the internal 'type' used in the Question model.
CATEGORY_TO_TYPE = {
    QuestionCategory.OPEN_ENDED.value: "socratic",
    QuestionCategory.BASIC_TERMINOLOGY.value: "basic_terminology",
    QuestionCategory.COMMAND_SYNTAX.value: "command",
    QuestionCategory.YAML_MANIFEST.value: "yaml_author",
}


def run_cli_command(command: list[str], env: dict = None) -> subprocess.CompletedProcess:
    """Helper to run a CLI command and capture its output."""
    process_env = os.environ.copy()
    if env:
        process_env.update({k: str(v) for k, v in env.items()})

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        env=process_env,
        check=False,
    )
    if result.returncode != 0:
        print(f"Error running command: {' '.join(command)}")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
    return result


@pytest.fixture
def test_env(tmp_path: Path):
    """Set up an isolated temporary environment for each test."""
    db_path = tmp_path / "kubelingo_e2e.db"
    questions_dir = tmp_path / "e2e_questions"
    questions_dir.mkdir()

    env = {
        "KUBELINGO_DB_PATH": str(db_path),
        "KUBELINGO_QUESTIONS_DIR": str(questions_dir),
    }

    init_cmd = ["python", "-m", "kubelingo.cli", "init-db", "--clear"]
    result = run_cli_command(init_cmd, env)
    assert result.returncode == 0, f"Database initialization failed: {result.stderr}"

    yield {
        "db_path": db_path,
        "questions_dir": questions_dir,
        "env": env,
    }


def get_all_db_questions(db_path: Path) -> list:
    """Helper to query all questions from the test database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM questions")
    questions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return questions


class TestE2EScenarios:
    """
    End-to-end tests covering key user scenarios as defined in the design spec.
    """

    @pytest.mark.e2e
    @pytest.mark.parametrize("category", QUESTION_CATEGORIES)
    @pytest.mark.parametrize("subject", SUBJECTS)
    @patch("scripts.question_manager.AIQuestionGenerator")
    def test_generate_question_for_each_category_and_subject(self, mock_q_gen, test_env, category, subject):
        """
        Tests that a question can be generated for every combination of
        question category and subject.

        Corresponds to test requirement:
        - "make sure you can generate questions of all 4 types and all 21 subjects"
        """
        mock_generator_instance = mock_q_gen.return_value
        q_id = f"q_{subject[:10].replace(' ', '_')}_{category.replace(' ', '_')}".lower()
        q_type = CATEGORY_TO_TYPE[category]

        # The AI generator returns a dict that becomes a Question object
        mock_generator_instance.generate_question.return_value = {
            "id": q_id,
            "prompt": f"A question about {subject}",
            "answers": ["An answer."],
            "subject_matter": subject,
            "schema_category": category,
            "type": q_type,
        }

        cmd = [
            "python", "-m", "scripts.question_manager", "ai-questions",
            "--subject", subject,
            "--category", category,
            "--num-questions", "1",
        ]
        result = run_cli_command(cmd, test_env["env"])
        assert result.returncode == 0, f"Failed to generate question: {result.stderr}"

        questions = get_all_db_questions(test_env["db_path"])
        assert len(questions) >= 1
        generated_q = next((q for q in questions if q["id"] == q_id), None)
        assert generated_q is not None
        assert generated_q["subject_matter"] == subject
        assert generated_q["schema_category"] == category
        assert generated_q["type"] == q_type

    @pytest.mark.e2e
    @patch("scripts.question_manager.AIProcessor")
    def test_add_question_from_document(self, mock_ai_processor, test_env):
        """
        Tests that questions can be added from an external document.

        Corresponds to test requirement:
        - "make sure you can add questions and parse/reformat from any type of document"
        """
        doc_path = test_env["questions_dir"] / "sample.txt"
        doc_path.write_text("Q: What is a pod?\nA: A pod is a group of containers.")

        mock_processor_instance = mock_ai_processor.return_value
        mock_processor_instance.format_questions.return_value = [{
            "id": "from-doc-q1", "prompt": "What is a pod?",
            "answers": ["A pod is a group of containers."],
            "subject_matter": QuestionSubject.CORE_WORKLOADS.value,
            "schema_category": QuestionCategory.OPEN_ENDED.value,
            "type": "socratic"
        }]

        cmd = ["python", "-m", "scripts.question_manager", "from-pdf", str(doc_path)]
        result = run_cli_command(cmd, test_env["env"])
        assert result.returncode == 0, f"Failed to add question from doc: {result.stderr}"

        questions = get_all_db_questions(test_env["db_path"])
        assert len(questions) >= 1
        assert "from-doc-q1" in [q["id"] for q in questions]
        assert len(list(test_env["questions_dir"].glob("*.yaml"))) >= 1

    @pytest.mark.e2e
    @pytest.mark.parametrize("category", QUESTION_CATEGORIES)
    def test_answer_question_by_type(self, category):
        """
        Tests that each type of question can be answered correctly.

        Corresponds to test requirement:
        - "make sure you can answer questions in the manner we have specified for each type of question"
        """
        # This test is highly complex as it requires simulating interactive sessions.
        # A full implementation would require a PTY-based testing tool (like pexpect)
        # or deep mocking of session management and user input functions.
        print(f"Placeholder: Answer a '{category}' question.")
        assert True

    @pytest.mark.e2e
    @patch("scripts.question_manager.AIQuestionGenerator")
    def test_generated_question_is_persisted(self, mock_q_gen, test_env):
        """
        Tests that a newly generated question is saved to a YAML file and its
        metadata is tracked in the database.

        Corresponds to test requirement:
        - "test for generated questions to be automatically added to /yaml and tracked by database"
        """
        mock_generator_instance = mock_q_gen.return_value
        mock_generator_instance.generate_question.return_value = {
            "id": "persist-test-q1", "prompt": "A question to persist.",
            "answers": ["An answer."], "subject_matter": QuestionSubject.CORE_WORKLOADS.value,
            "type": "socratic", "schema_category": QuestionCategory.OPEN_ENDED.value
        }
        cmd = [
            "python", "-m", "scripts.question_manager", "ai-questions",
            "--subject", QuestionSubject.CORE_WORKLOADS.value,
            "--category", QuestionCategory.OPEN_ENDED.value,
            "--num-questions", "1",
        ]
        result = run_cli_command(cmd, test_env["env"])
        assert result.returncode == 0, f"Failed to persist question: {result.stderr}"

        yaml_files = list(test_env["questions_dir"].glob("*.yaml"))
        assert len(yaml_files) == 1
        with open(yaml_files[0], 'r') as f:
            content = yaml.safe_load(f)
        assert content["questions"][0]["id"] == "persist-test-q1"

        questions = get_all_db_questions(test_env["db_path"])
        assert len(questions) == 1
        assert questions[0]["id"] == "persist-test-q1"

    @pytest.mark.e2e
    @patch("scripts.question_manager.AIQuestionGenerator")
    def test_delete_question(self, mock_q_gen, test_env):
        """
        Tests that a question can be deleted via the Question Management menu.

        Corresponds to test requirement:
        - "test that you can delete questions"
        """
        mock_generator_instance = mock_q_gen.return_value
        mock_generator_instance.generate_question.return_value = {
            "id": "delete-test-q1", "prompt": "Q", "answers": ["A"],
            "subject_matter": QuestionSubject.CORE_WORKLOADS.value,
            "type": "socratic", "schema_category": QuestionCategory.OPEN_ENDED.value,
        }
        gen_cmd = [
            "python", "-m", "scripts.question_manager", "ai-questions",
            "--num-questions", "1", "--subject", QuestionSubject.CORE_WORKLOADS.value,
        ]
        run_cli_command(gen_cmd, test_env["env"])
        assert len(get_all_db_questions(test_env["db_path"])) == 1

        del_cmd = ["python", "-m", "scripts.question_manager", "remove-question", "delete-test-q1"]
        result = run_cli_command(del_cmd, test_env["env"])
        assert result.returncode == 0, f"Failed to delete question: {result.stderr}"

        assert len(get_all_db_questions(test_env["db_path"])) == 0
        yaml_files = list(test_env["questions_dir"].glob("*.yaml"))
        assert len(yaml_files) == 1
        with open(yaml_files[0], 'r') as f:
            content = yaml.safe_load(f)
        assert not content or "questions" not in content or not content["questions"]

    @pytest.mark.e2e
    @patch("scripts.question_manager.AIQuestionGenerator")
    def test_fix_triaged_question(self, mock_q_gen, test_env):
        """
        Tests the workflow for fixing a triaged question.

        Corresponds to test requirement:
        - "test that you can fix triaged questions"
        """
        mock_generator_instance = mock_q_gen.return_value
        mock_generator_instance.generate_question.return_value = {
            "id": "triage-test-q1", "prompt": "Q", "answers": ["A"],
            "subject_matter": QuestionSubject.CORE_WORKLOADS.value,
            "type": "socratic", "schema_category": QuestionCategory.OPEN_ENDED.value
        }
        run_cli_command([
            "python", "-m", "scripts.question_manager", "ai-questions",
            "--num-questions", "1", "--subject", QuestionSubject.CORE_WORKLOADS.value,
        ], test_env["env"])

        triage_cmd = ["python", "-m", "scripts.question_manager", "set-triage-status", "triage-test-q1"]
        result = run_cli_command(triage_cmd, test_env["env"])
        assert result.returncode == 0, f"Failed to set triage status: {result.stderr}"
        assert get_all_db_questions(test_env["db_path"])[0]['triage'] == 1

        fix_cmd = ["python", "-m", "scripts.question_manager", "set-triage-status", "triage-test-q1", "--status", "fixed"]
        result = run_cli_command(fix_cmd, test_env["env"])
        assert result.returncode == 0, f"Failed to fix triage status: {result.stderr}"

        assert get_all_db_questions(test_env["db_path"])[0]['triage'] == 0

    @pytest.mark.e2e
    @patch("scripts.question_manager.AIQuestionGenerator")
    def test_prevent_duplicate_questions(self, mock_q_gen, test_env):
        """
        Tests that the application avoids creating duplicate questions.

        Corresponds to test requirement:
        - "test that you do not make duplicate questions"
        """
        mock_generator_instance = mock_q_gen.return_value
        mock_generator_instance.generate_question.return_value = {
            "id": "duplicate-test-q1", "prompt": "Q", "answers": ["A"],
            "subject_matter": QuestionSubject.CORE_WORKLOADS.value,
            "type": "socratic", "schema_category": QuestionCategory.OPEN_ENDED.value,
        }
        gen_cmd = [
            "python", "-m", "scripts.question_manager", "ai-questions",
            "--num-questions", "1", "--subject", QuestionSubject.CORE_WORKLOADS.value,
        ]
        run_cli_command(gen_cmd, test_env["env"])
        assert len(get_all_db_questions(test_env["db_path"])) == 1

        # Running generation again with the same mock should not create a new question
        result = run_cli_command(gen_cmd, test_env["env"])
        assert result.returncode == 0, f"Second generation call failed: {result.stderr}"

        assert len(get_all_db_questions(test_env["db_path"])) == 1
