import pytest
import os
import yaml
from unittest.mock import patch, mock_open, MagicMock, call
from kubelingo.utils import (
    save_question_to_list,
    remove_question_from_list,
    load_questions_from_list,
    get_normalized_question_text,
    update_question_source_in_yaml,
)
from kubelingo.kubelingo import MISSED_QUESTIONS_FILE, USER_DATA_DIR, QUESTIONS_DIR

# --- Fixtures for mocking file system ---

@pytest.fixture
def mock_os_path_exists():
    with patch('os.path.exists') as mock_exists:
        yield mock_exists

@pytest.fixture
def mock_yaml_safe_load():
    with patch('yaml.safe_load') as mock_load:
        yield mock_load

@pytest.fixture
def mock_yaml_dump():
    with patch('yaml.dump') as mock_dump:
        yield mock_dump

@pytest.fixture
def mock_builtins_open(mocker):
    mock_file_handle = mocker.MagicMock()
    m_open = mocker.patch('builtins.open', return_value=mock_file_handle)
    m_open.return_value.__enter__.return_value = mock_file_handle
    yield m_open, mock_file_handle

@pytest.fixture
def mock_question_list_file(mock_os_path_exists, mock_yaml_safe_load, mock_yaml_dump, mock_builtins_open):
    yield mock_os_path_exists, mock_yaml_safe_load, mock_yaml_dump, mock_builtins_open[0], mock_builtins_open[1]

# --- Tests for question list management ---

def test_save_question_to_list_new_file(mock_question_list_file):
    mock_exists, mock_load, mock_dump, mock_open_func, mock_file_handle = mock_question_list_file
    mock_exists.return_value = False
    question = {'question': 'Test Q', 'solution': 'A'}
    topic = 'test_topic'
    
    save_question_to_list(MISSED_QUESTIONS_FILE, question, topic)
    
    mock_exists.assert_called_once_with(MISSED_QUESTIONS_FILE)
    mock_load.assert_not_called()
    
    expected_question_to_save = question.copy()
    expected_question_to_save['original_topic'] = topic
    mock_dump.assert_called_once_with([expected_question_to_save], mock_file_handle)
    mock_open_func.assert_called_once_with(MISSED_QUESTIONS_FILE, 'w')

def test_save_question_to_list_existing_file_new_question(mock_question_list_file):
    mock_exists, mock_load, mock_dump, mock_open_func, mock_file_handle = mock_question_list_file
    mock_exists.return_value = True
    mock_load.return_value = [{'question': 'Existing Q', 'solution': 'B'}]
    question = {'question': 'New Q', 'solution': 'C'}
    topic = 'test_topic'

    save_question_to_list(MISSED_QUESTIONS_FILE, question, topic)

    mock_exists.assert_called_once_with(MISSED_QUESTIONS_FILE)
    mock_load.assert_called_once_with(mock_file_handle)
    
    expected_question_to_save = question.copy()
    expected_question_to_save['original_topic'] = topic
    expected_list = [{'question': 'Existing Q', 'solution': 'B'}, expected_question_to_save]
    mock_dump.assert_called_once_with(expected_list, mock_file_handle)
    assert mock_open_func.call_args_list == [call(MISSED_QUESTIONS_FILE, 'r'), call(MISSED_QUESTIONS_FILE, 'w')]

def test_save_question_to_list_existing_file_duplicate_question(mock_question_list_file):
    mock_exists, mock_load, mock_dump, mock_open_func, mock_file_handle = mock_question_list_file
    mock_exists.return_value = True
    question = {'question': 'Existing Q', 'solution': 'B'}
    mock_load.return_value = [question]
    topic = 'test_topic'

    save_question_to_list(MISSED_QUESTIONS_FILE, question, topic)

    mock_exists.assert_called_once_with(MISSED_QUESTIONS_FILE)
    mock_load.assert_called_once_with(mock_file_handle)
    mock_dump.assert_not_called()
    mock_open_func.assert_called_once_with(MISSED_QUESTIONS_FILE, 'r')

def test_save_question_to_list_yaml_error(mock_question_list_file):
    mock_exists, mock_load, mock_dump, mock_open_func, mock_file_handle = mock_question_list_file
    mock_exists.return_value = True
    mock_load.side_effect = yaml.YAMLError
    question = {'question': 'New Q', 'solution': 'C'}
    topic = 'test_topic'

    save_question_to_list(MISSED_QUESTIONS_FILE, question, topic)
    
    expected_question_to_save = question.copy()
    expected_question_to_save['original_topic'] = topic
    mock_dump.assert_called_once_with([expected_question_to_save], mock_file_handle)
    assert mock_open_func.call_args_list == [call(MISSED_QUESTIONS_FILE, 'r'), call(MISSED_QUESTIONS_FILE, 'w')]

def test_remove_question_from_list_exists(mock_question_list_file):
    mock_exists, mock_load, mock_dump, mock_open_func, mock_file_handle = mock_question_list_file
    mock_exists.return_value = True
    existing_q1 = {'question': 'Q1', 'solution': 'A'}
    existing_q2 = {'question': 'Q2', 'solution': 'B'}
    mock_load.return_value = [existing_q1, existing_q2]
    
    remove_question_from_list(MISSED_QUESTIONS_FILE, existing_q1)
    
    mock_exists.assert_called_once_with(MISSED_QUESTIONS_FILE)
    mock_load.assert_called_once_with(mock_file_handle)
    mock_dump.assert_called_once_with([existing_q2], mock_file_handle)
    assert mock_open_func.call_args_list == [call(MISSED_QUESTIONS_FILE, 'r'), call(MISSED_QUESTIONS_FILE, 'w')]

def test_remove_question_from_list_not_exists(mock_question_list_file):
    mock_exists, mock_load, mock_dump, mock_open_func, mock_file_handle = mock_question_list_file
    mock_exists.return_value = True
    existing_q1 = {'question': 'Q1', 'solution': 'A'}
    mock_load.return_value = [existing_q1]
    question_to_remove = {'question': 'Non-existent Q', 'solution': 'C'}
    
    remove_question_from_list(MISSED_QUESTIONS_FILE, question_to_remove)
    
    mock_exists.assert_called_once_with(MISSED_QUESTIONS_FILE)
    mock_load.assert_called_once_with(mock_file_handle)
    mock_dump.assert_called_once_with([existing_q1], mock_file_handle)
    assert mock_open_func.call_args_list == [call(MISSED_QUESTIONS_FILE, 'r'), call(MISSED_QUESTIONS_FILE, 'w')]

def test_remove_question_from_list_no_file(mock_question_list_file):
    mock_exists, mock_load, mock_dump, mock_open_func, mock_file_handle = mock_question_list_file
    mock_exists.return_value = False
    question_to_remove = {'question': 'Q1', 'solution': 'A'}
    
    remove_question_from_list(MISSED_QUESTIONS_FILE, question_to_remove)
    
    mock_exists.assert_called_once_with(MISSED_QUESTIONS_FILE)
    mock_load.assert_not_called()
    mock_dump.assert_called_once_with([], mock_file_handle)
    mock_open_func.assert_called_once_with(MISSED_QUESTIONS_FILE, 'w')

def test_remove_question_from_list_yaml_error(mock_question_list_file):
    mock_exists, mock_load, mock_dump, mock_open_func, mock_file_handle = mock_question_list_file
    mock_exists.return_value = True
    mock_load.side_effect = yaml.YAMLError
    question_to_remove = {'question': 'Q1', 'solution': 'A'}

    remove_question_from_list(MISSED_QUESTIONS_FILE, question_to_remove)
    
    mock_dump.assert_called_once_with([], mock_file_handle)
    assert mock_open_func.call_args_list == [call(MISSED_QUESTIONS_FILE, 'r'), call(MISSED_QUESTIONS_FILE, 'w')]

def test_load_questions_from_list_no_file(mock_os_path_exists):
    mock_os_path_exists.return_value = False
    questions = load_questions_from_list(MISSED_QUESTIONS_FILE)
    assert questions == []
    mock_os_path_exists.assert_called_once_with(MISSED_QUESTIONS_FILE)

def test_load_questions_from_list_empty_file(mock_os_path_exists, mock_yaml_safe_load, mock_builtins_open):
    mock_open_func, mock_file_handle = mock_builtins_open
    mock_os_path_exists.return_value = True
    mock_yaml_safe_load.return_value = None
    questions = load_questions_from_list(MISSED_QUESTIONS_FILE)
    assert questions == []
    mock_yaml_safe_load.assert_called_once_with(mock_file_handle)
    mock_open_func.assert_called_once_with(MISSED_QUESTIONS_FILE, 'r')

def test_load_questions_from_list_valid_file(mock_os_path_exists, mock_yaml_safe_load, mock_builtins_open):
    mock_open_func, mock_file_handle = mock_builtins_open
    mock_os_path_exists.return_value = True
    expected_questions = [{'question': 'Q1'}]
    mock_yaml_safe_load.return_value = expected_questions
    questions = load_questions_from_list(MISSED_QUESTIONS_FILE)
    assert questions == expected_questions
    mock_yaml_safe_load.assert_called_once_with(mock_file_handle)
    mock_open_func.assert_called_once_with(MISSED_QUESTIONS_FILE, 'r')

# --- Tests for get_normalized_question_text ---

def test_get_normalized_question_text_basic():
    q = {'question': '  What is Kubernetes?  '}
    assert get_normalized_question_text(q) == 'what is kubernetes?'

def test_get_normalized_question_text_missing_key():
    q = {'not_question': 'abc'}
    assert get_normalized_question_text(q) == ''

def test_get_normalized_question_text_empty_string():
    q = {'question': ''}
    assert get_normalized_question_text(q) == ''

def test_get_normalized_question_text_with_newlines():
    q = {'question': 'What\nis\nKubernetes?\n'}
    assert get_normalized_question_text(q) == 'what\nis\nkubernetes?'

# --- Tests for update_question_source_in_yaml ---

@pytest.fixture
def mock_topic_file(mock_os_path_exists, mock_yaml_safe_load, mock_yaml_dump, mock_builtins_open):
    yield mock_os_path_exists, mock_yaml_safe_load, mock_yaml_dump, mock_builtins_open[0], mock_builtins_open[1]

def test_update_question_source_in_yaml_file_not_found(mock_topic_file, capsys):
    mock_exists, mock_load, mock_dump, mock_open_func, mock_file_handle = mock_topic_file
    mock_exists.return_value = False
    
    topic = 'non_existent_topic'
    updated_question = {'question': 'Q1', 'source': 'new_source'}
    
    update_question_source_in_yaml(topic, updated_question)
    
    expected_path = os.path.join(QUESTIONS_DIR, f"{topic}.yaml")
    mock_exists.assert_called_once_with(expected_path)
    mock_load.assert_not_called()
    mock_dump.assert_not_called()
    mock_open_func.assert_not_called()
    
    captured = capsys.readouterr()
    assert f"Error: Topic file not found at {expected_path}. Cannot update source." in captured.out

def test_update_question_source_in_yaml_question_found(mock_topic_file, capsys):
    mock_exists, mock_load, mock_dump, mock_open_func, mock_file_handle = mock_topic_file
    mock_exists.return_value = True
    
    initial_data = {
        'questions': [
            {'question': 'Q1', 'solution': 'A', 'source': 'old_source'},
            {'question': 'Q2', 'solution': 'B'}
        ]
    }
    mock_load.return_value = initial_data
    
    topic = 'test_topic'
    updated_question = {'question': 'Q1', 'source': 'new_source'}
    
    update_question_source_in_yaml(topic, updated_question)
    
    expected_path = os.path.join(QUESTIONS_DIR, f"{topic}.yaml")
    mock_exists.assert_called_once_with(expected_path)
    mock_load.assert_called_once_with(mock_file_handle)
    
    expected_data = {
        'questions': [
            {'question': 'Q1', 'solution': 'A', 'source': 'new_source'},
            {'question': 'Q2', 'solution': 'B'}
        ]
    }
    mock_dump.assert_called_once_with(expected_data, mock_file_handle)
    mock_open_func.assert_called_once_with(expected_path, 'r+')
    
    captured = capsys.readouterr()
    assert f"Source for question 'Q1' updated in {topic}.yaml." in captured.out

def test_update_question_source_in_yaml_question_not_found(mock_topic_file, capsys):
    mock_exists, mock_load, mock_dump, mock_open_func, mock_file_handle = mock_topic_file
    mock_exists.return_value = True
    
    initial_data = {
        'questions': [
            {'question': 'Q1', 'solution': 'A', 'source': 'old_source'}
        ]
    }
    mock_load.return_value = initial_data
    
    topic = 'test_topic'
    updated_question = {'question': 'Non-existent Q', 'source': 'new_source'}
    
    update_question_source_in_yaml(topic, updated_question)
    
    expected_path = os.path.join(QUESTIONS_DIR, f"{topic}.yaml")
    mock_exists.assert_called_once_with(expected_path)
    mock_load.assert_called_once_with(mock_file_handle)
    mock_dump.assert_not_called()
    mock_open_func.assert_called_once_with(expected_path, 'r+')
    
    captured = capsys.readouterr()
    assert f"Warning: Question 'Non-existent Q' not found in {topic}.yaml. Source not updated." in captured.out

def test_update_question_source_in_yaml_empty_file(mock_topic_file, capsys):
    mock_exists, mock_load, mock_dump, mock_open_func, mock_file_handle = mock_topic_file
    mock_exists.return_value = True
    mock_load.return_value = None
    
    topic = 'test_topic'
    updated_question = {'question': 'Q1', 'source': 'new_source'}
    
    update_question_source_in_yaml(topic, updated_question)
    
    expected_path = os.path.join(QUESTIONS_DIR, f"{topic}.yaml")
    mock_exists.assert_called_once_with(expected_path)
    mock_load.assert_called_once_with(mock_file_handle)
    mock_dump.assert_not_called()
    mock_open_func.assert_called_once_with(expected_path, 'r+')
    
    captured = capsys.readouterr()
    assert f"Warning: Question 'Q1' not found in {topic}.yaml. Source not updated." in captured.out