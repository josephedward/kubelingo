import pytest
import json
import os
from unittest.mock import patch, mock_open, MagicMock

# The module to test
from kubelingo.modules.kubernetes import session as k8s_session
from kubelingo.modules.kubernetes.session import NewSession


@pytest.fixture
def mock_logger():
    """Fixture for a mock logger."""
    return MagicMock()


@pytest.fixture
def k8s_session_instance(mock_logger):
    """Fixture for a NewSession instance with a mock logger."""
    return NewSession(logger=mock_logger)


@pytest.fixture
def setup_quiz_files(tmp_path):
    """
    Creates a temporary directory structure with mock quiz files
    and patches the session constants to use them.
    """
    data_dir = tmp_path / "question-data"
    json_dir = data_dir / "json"
    json_dir.mkdir(parents=True)

    # File with a flagged command question
    quiz1_path = json_dir / "quiz1.json"
    quiz1_data = [{"category": "c1", "prompts": [{"prompt": "p1", "response": "r1", "review": True}]}]
    with open(quiz1_path, 'w') as f:
        json.dump(quiz1_data, f)

    # File with no flagged questions
    quiz2_path = json_dir / "quiz2.json"
    quiz2_data = [{"category": "c2", "prompts": [{"prompt": "p2", "response": "r2"}]}]
    with open(quiz2_path, 'w') as f:
        json.dump(quiz2_data, f)

    # Special Vim quiz file with a flagged question
    vim_quiz_path = json_dir / "vim_quiz_data.json"
    vim_data = [{"category": "vim", "prompts": [{"prompt": "pvim", "response": "rvim", "review": True}]}]
    with open(vim_quiz_path, 'w') as f:
        json.dump(vim_data, f)

    # An empty yaml questions file to be excluded
    yaml_questions_path = json_dir / "yaml_edit_questions.json"
    yaml_questions_path.touch()

    # Patch the constants in the session module to point to our temp directory
    with patch.multiple(k8s_session,
                        DATA_DIR=str(data_dir),
                        VIM_QUESTIONS_FILE=str(vim_quiz_path),
                        YAML_QUESTIONS_FILE=str(yaml_questions_path)):
        yield {
            "quiz1": str(quiz1_path),
            "quiz2": str(quiz2_path),
            "vim": str(vim_quiz_path)
        }


def test_get_quiz_files(setup_quiz_files):
    """Tests that _get_quiz_files discovers correct files and excludes special ones."""
    quiz_files = k8s_session._get_quiz_files()
    
    assert len(quiz_files) == 2
    assert os.path.basename(setup_quiz_files['quiz1']) in [os.path.basename(p) for p in quiz_files]
    assert os.path.basename(setup_quiz_files['quiz2']) in [os.path.basename(p) for p in quiz_files]
    assert os.path.basename(setup_quiz_files['vim']) not in [os.path.basename(p) for p in quiz_files]


def test_clear_all_review_flags(setup_quiz_files, mock_logger):
    """Tests that clearing flags removes them from all relevant files."""
    # Pre-condition check: ensure flags exist
    with open(setup_quiz_files['quiz1'], 'r') as f:
        assert 'review' in json.load(f)[0]['prompts'][0]
    with open(setup_quiz_files['vim'], 'r') as f:
        assert 'review' in json.load(f)[0]['prompts'][0]

    # Call the function to be tested
    k8s_session._clear_all_review_flags(mock_logger)

    # Check quiz1.json - flag should be gone
    with open(setup_quiz_files['quiz1'], 'r') as f:
        data = json.load(f)
    assert 'review' not in data[0]['prompts'][0]

    # Check vim_quiz.json - flag should be gone
    with open(setup_quiz_files['vim'], 'r') as f:
        data = json.load(f)
    assert 'review' not in data[0]['prompts'][0]


def test_unmark_question_during_review(setup_quiz_files, k8s_session_instance):
    """
    Integration-style test for the review flow:
    - Select review from the menu.
    - Answer a question.
    - Choose to un-flag it.
    - Verify the file is updated.
    """
    args = MagicMock()
    args.category = None
    args.review_only = False
    args.num = 0

    with patch('kubelingo.modules.kubernetes.session.questionary') as mock_questionary:
        # Simulate menu selections: 1. Choose review, 2. Choose to un-flag
        mock_questionary.select.ask.side_effect = ['review', 'Un-flag for Review', 'Next Question']
        
        with patch('kubelingo.modules.kubernetes.session.PromptSession') as mock_prompt:
            mock_prompt.return_value.prompt.return_value = "some answer"
            
            # Run the quiz. This will use the mocked setup_quiz_files paths.
            k8s_session_instance._run_command_quiz(args)

    # After quiz, check that the flag was removed from the correct file
    with open(setup_quiz_files['quiz1'], 'r') as f:
        data = json.load(f)
    assert 'review' not in data[0]['prompts'][0]
    
    # Check that the other flagged file (vim quiz) was untouched
    with open(setup_quiz_files['vim'], 'r') as f:
        data = json.load(f)
    assert data[0]['prompts'][0]['review'] is True


def test_history_file_location_constants():
    """Verify that history-related constants point to the correct logs/ directory."""
    from kubelingo.modules.kubernetes.session import LOGS_DIR, HISTORY_FILE, ROOT
    
    expected_logs_dir = os.path.join(ROOT, 'logs')
    assert LOGS_DIR == expected_logs_dir
    assert HISTORY_FILE.startswith(expected_logs_dir)
    assert not HISTORY_FILE.startswith(os.path.expanduser('~'))
