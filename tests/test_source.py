import pytest
import os
import yaml
from unittest.mock import patch, MagicMock
from kubelingo.kubelingo import update_question_source_in_yaml
from kubelingo.utils import QUESTIONS_DIR

@pytest.fixture
def mock_os_path_exists():
    with patch('kubelingo.kubelingo.os.path.exists') as mock_exists:
        yield mock_exists

@pytest.fixture
def mock_yaml_safe_load():
    with patch('kubelingo.kubelingo.yaml.safe_load') as mock_load:
        yield mock_load

@pytest.fixture
def mock_builtins_open(mocker):
    # Create a mock for the file handle that mock_open would return
    mock_file_handle = mocker.MagicMock()
    m_open = mocker.patch('builtins.open', return_value=mock_file_handle)
    # Allow entering and exiting the context manager
    m_open.return_value.__enter__.return_value = mock_file_handle
    yield m_open, mock_file_handle

@pytest.fixture
def mock_yaml_dump():
    with patch('kubelingo.kubelingo.yaml.dump') as mock_dump:
        yield mock_dump

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
    mock_dump.assert_not_called() # Should not dump if question not found
    mock_open_func.assert_called_once_with(expected_path, 'r+')
    
    captured = capsys.readouterr()
    assert f"Warning: Question 'Non-existent Q' not found in {topic}.yaml. Source not updated." in captured.out

def test_update_question_source_in_yaml_empty_file(mock_topic_file, capsys):
    mock_exists, mock_load, mock_dump, mock_open_func, mock_file_handle = mock_topic_file
    mock_exists.return_value = True
    mock_load.return_value = None # Empty YAML file
    
    topic = 'test_topic'
    updated_question = {'question': 'Q1', 'source': 'new_source'}
    
    update_question_source_in_yaml(topic, updated_question)
    
    expected_path = os.path.join(QUESTIONS_DIR, f"{topic}.yaml")
    mock_exists.assert_called_once_with(expected_path)
    mock_load.assert_called_once_with(mock_file_handle)
    mock_dump.assert_not_called() # Should not dump if question not found in empty file
    mock_open_func.assert_called_once_with(expected_path, 'r+')
    
    captured = capsys.readouterr()
    assert f"Warning: Question 'Q1' not found in {topic}.yaml. Source not updated." in captured.out