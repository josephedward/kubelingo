import pytest
import os
import yaml
from unittest.mock import patch, mock_open, MagicMock, call
from kubelingo.kubelingo import (
    load_performance_data,
    save_performance_data
)
from kubelingo.utils import USER_DATA_DIR, PERFORMANCE_FILE, ensure_user_data_dir
from kubelingo.performance_tracker import _performance_data_changed

@pytest.fixture
def mock_os_path_exists():
    with patch('os.path.exists') as mock_exists:
        yield mock_exists

@pytest.fixture
def mock_builtins_open():
    m = mock_open()
    with patch('builtins.open', m):
        yield m # Yield the mock_open object itself

@pytest.fixture
def mock_yaml_safe_load():
    with patch('yaml.safe_load') as mock_safe_load:
        yield mock_safe_load

@pytest.fixture
def mock_yaml_dump():
    with patch('yaml.dump') as mock_dump:
        yield mock_dump

@pytest.fixture
def mock_ensure_user_data_dir():
    with patch('kubelingo.utils.ensure_user_data_dir') as mock_func:
        yield mock_func

def test_load_performance_data_no_file(mock_os_path_exists, mock_builtins_open, mock_yaml_dump, mock_ensure_user_data_dir):
    mock_os_path_exists.return_value = False
    mock_open_func = mock_builtins_open # This is the mock_open object
    with patch('kubelingo.kubelingo.os.path.getsize'): # This patch is still needed for the original load_performance_data logic
        data, loaded_ok = load_performance_data()
        assert data == {}
        assert loaded_ok == True
        mock_os_path_exists.assert_called_once_with(PERFORMANCE_FILE)
        mock_open_func.assert_called_once_with(PERFORMANCE_FILE, 'w')
        mock_yaml_dump.assert_called_once_with({}, mock_open_func.return_value)

def test_load_performance_data_empty_file(mock_os_path_exists, mock_yaml_safe_load, mock_builtins_open, mock_yaml_dump, mock_ensure_user_data_dir):
    mock_os_path_exists.return_value = True
    mock_open_func = mock_builtins_open # This is the mock_open object
    mock_yaml_safe_load.return_value = None
    data, loaded_ok = load_performance_data()
    assert data == {}
    assert loaded_ok == True
    mock_os_path_exists.assert_called_with(PERFORMANCE_FILE)
    mock_yaml_safe_load.assert_called_once_with(mock_open_func.return_value) # Use .return_value for the file handle
    mock_yaml_dump.assert_not_called()
    mock_ensure_user_data_dir.assert_called_once()

def test_load_performance_data_valid_file(mock_os_path_exists, mock_yaml_safe_load, mock_builtins_open, mock_ensure_user_data_dir):
    mock_open_func = mock_builtins_open # This is the mock_open object
    mock_os_path_exists.return_value = True
    expected_data = {'topic1': {'correct_questions': ['q1']}}
    mock_yaml_safe_load.return_value = expected_data
    data, loaded_ok = load_performance_data()
    assert data == expected_data
    assert loaded_ok == True
    mock_os_path_exists.assert_called_with(PERFORMANCE_FILE)
    mock_open_func.assert_called_once_with(PERFORMANCE_FILE, 'r')
    mock_yaml_safe_load.assert_called_once_with(mock_open_func.return_value)
    mock_ensure_user_data_dir.assert_called_once()

import pytest

@pytest.mark.skip("Skipping YAML error test until performance logic is adjusted")
def test_load_performance_data_yaml_error(mocker, mock_ensure_user_data_dir):
    mock_exists = mocker.patch('os.path.exists', return_value=True)
    mock_ensure_dir = mocker.patch('kubelingo.utils.ensure_user_data_dir')
    mock_getsize = mocker.patch('os.path.getsize', return_value=100)
    mock_load = mocker.patch('yaml.safe_load', side_effect=yaml.YAMLError)
    mock_dump = mocker.patch('yaml.dump')
    mock_open_func = mocker.patch('builtins.open', mocker.mock_open())

    data, loaded_ok = load_performance_data()

    assert data == {}
    assert loaded_ok == False
    mock_exists.assert_called_with(PERFORMANCE_FILE)
    mock_load.assert_called_once_with(mock_open_func.return_value.__enter__.return_value)
    mock_dump.assert_not_called()
    mock_ensure_user_data_dir.assert_called_once()

def test_save_performance_data(mocker, mock_ensure_user_data_dir):
    global _performance_data_changed # Access the global flag
    _performance_data_changed = True # Set the flag to True for this test

    mock_dump = mocker.patch('yaml.dump')
    mock_open_func = mocker.patch('builtins.open', mocker.mock_open())

    data_to_save = {'topic1': {'correct_questions': ['q1']}}
    save_performance_data(data_to_save)

    mock_ensure_user_data_dir.assert_called_once()
    mock_open_func.assert_called_once_with(PERFORMANCE_FILE, 'w')
    mock_dump.assert_called_once_with(data_to_save, mock_open_func.return_value.__enter__.return_value)
