import pytest
import os
import yaml
from unittest.mock import patch, mock_open, MagicMock, call
from kubelingo.issue_manager import create_issue
from kubelingo.kubelingo import USER_DATA_DIR, MISSED_QUESTIONS_FILE, ISSUES_FILE

# --- Fixtures for mocking file system (copied from test_kubelingo_functions.py) ---
@pytest.fixture
def mock_os_path_exists():
    with patch('kubelingo.kubelingo.os.path.exists') as mock_exists:
        yield mock_exists

@pytest.fixture
def mock_yaml_dump():
    with patch('kubelingo.kubelingo.yaml.dump') as mock_dump:
        yield mock_dump

@pytest.fixture
def mock_yaml_safe_load():
    with patch('kubelingo.kubelingo.yaml.safe_load') as mock_load:
        yield mock_load

@pytest.fixture
def mock_builtins_open(mocker):
    mock_file_handle = mocker.MagicMock()
    m_open = mocker.patch('builtins.open', return_value=mock_file_handle)
    m_open.return_value.__enter__.return_value = mock_file_handle
    yield m_open, mock_file_handle

# --- Fixture specific to create_issue ---
@pytest.fixture
def mock_create_issue_deps(mock_os_path_exists, mock_yaml_safe_load, mock_yaml_dump, mock_builtins_open):
    with patch('kubelingo.issue_manager.remove_question_from_list') as mock_remove_question_from_list:
        with patch('time.asctime', return_value='mock_timestamp') as mock_asctime:
            yield mock_os_path_exists, mock_yaml_safe_load, mock_yaml_dump, mock_builtins_open[0], mock_builtins_open[1], mock_remove_question_from_list, mock_asctime

# --- Tests for create_issue ---
def test_create_issue_valid_input(mock_create_issue_deps, capsys):
    mock_exists, mock_load, mock_dump, mock_open_func, mock_file_handle, mock_remove_question_from_list, mock_asctime = mock_create_issue_deps
    mock_exists.return_value = False # No existing issues file

    original_question_dict = {'question': 'Test Question'}
    topic = 'test_topic'
    user_input = "This is a test issue."

    with patch('builtins.input', return_value=user_input):
        create_issue(original_question_dict, topic)

    mock_exists.assert_called_once_with(ISSUES_FILE)
    mock_load.assert_not_called()

    expected_saved_question = {
        'question': 'Test Question',
        'issue': user_input,
        'timestamp': 'mock_timestamp',
        'topic': topic
    }
    mock_dump.assert_called_once_with([expected_saved_question], mock_file_handle)
    mock_open_func.assert_called_once_with(ISSUES_FILE, 'w')
    mock_remove_question_from_list.assert_called_once_with(MISSED_QUESTIONS_FILE, original_question_dict)

    captured = capsys.readouterr()
    assert "Please describe the issue with the question." in captured.out
    assert "Issue reported. Thank you!" in captured.out

def test_create_issue_empty_input(mock_create_issue_deps, capsys):
    mock_exists, mock_load, mock_dump, mock_open_func, mock_file_handle, mock_remove_question_from_list, mock_asctime = mock_create_issue_deps
    mock_exists.return_value = False

    question_dict = {'question': 'Test Question'}
    topic = 'test_topic'
    user_input = ""

    with patch('builtins.input', return_value=user_input):
        create_issue(question_dict, topic)

    mock_exists.assert_not_called() # No file operations if input is empty
    mock_load.assert_not_called()
    mock_dump.assert_not_called()
    mock_open_func.assert_not_called()
    mock_remove_question_from_list.assert_not_called()

    captured = capsys.readouterr()
    assert "Issue reporting cancelled." in captured.out

def test_create_issue_existing_issues(mock_create_issue_deps, capsys):
    mock_exists, mock_load, mock_dump, mock_open_func, mock_file_handle, mock_remove_question_from_list, mock_asctime = mock_create_issue_deps
    mock_exists.return_value = True
    mock_load.return_value = [{'issue': 'Old Issue'}]

    original_question_dict = {'question': 'Test Question'}
    topic = 'test_topic'
    user_input = "New issue."

    with patch('builtins.input', return_value=user_input):
        create_issue(original_question_dict, topic)

    mock_exists.assert_called_once_with(ISSUES_FILE)
    mock_load.assert_called_once_with(mock_file_handle)

    expected_saved_question = {
        'question': 'Test Question',
        'issue': user_input,
        'timestamp': 'mock_timestamp',
        'topic': topic
    }
    expected_list = [{'issue': 'Old Issue'}, expected_saved_question]
    mock_dump.assert_called_once_with(expected_list, mock_file_handle)
    assert mock_open_func.call_args_list == [call(ISSUES_FILE, 'r'), call(ISSUES_FILE, 'w')]
    mock_remove_question_from_list.assert_called_once_with(MISSED_QUESTIONS_FILE, original_question_dict)
