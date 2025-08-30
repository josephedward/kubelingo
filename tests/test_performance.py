import pytest
import os
import yaml
from unittest.mock import patch, mock_open, MagicMock, call
from kubelingo.kubelingo import (
    load_performance_data,
    save_performance_data
)
from kubelingo.utils import USER_DATA_DIR, PERFORMANCE_FILE, ensure_user_data_dir

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

def test_load_performance_data_no_file(mock_os_path_exists, mock_builtins_open, mock_yaml_dump):
    mock_os_path_exists.return_value = False
    mock_open_func = mock_builtins_open # This is the mock_open object
    with patch('kubelingo.kubelingo.ensure_user_data_dir'):
        with patch('kubelingo.kubelingo.os.path.getsize'):
            data = load_performance_data()
            assert data == {}
            mock_os_path_exists.assert_called_once_with(PERFORMANCE_FILE)
            mock_open_func.assert_called_once_with(PERFORMANCE_FILE, 'w')
            mock_yaml_dump.assert_called_once_with({}, mock_open_func.return_value)


def test_load_performance_data_empty_file(mock_os_path_exists, mock_yaml_safe_load, mock_builtins_open):
    mock_os_path_exists.return_value = True
    mock_open_func = mock_builtins_open # This is the mock_open object
    mock_yaml_safe_load.return_value = None
    with patch('kubelingo.kubelingo.ensure_user_data_dir'):
        data = load_performance_data()
        assert data == {}
        mock_os_path_exists.assert_called_once_with(PERFORMANCE_FILE)
        mock_yaml_safe_load.assert_called_once_with(mock_open_func.return_value) # Use .return_value for the file handle
        assert mock_open_func.call_args_list == [call(PERFORMANCE_FILE, 'r'), call(PERFORMANCE_FILE, 'w')]

def test_load_performance_data_valid_file(mock_os_path_exists, mock_yaml_safe_load, mock_builtins_open):
    mock_open_func = mock_builtins_open # This is the mock_open object
    mock_os_path_exists.return_value = True
    expected_data = {'topic1': {'correct_questions': ['q1']}}
    mock_yaml_safe_load.return_value = expected_data
    with patch('kubelingo.kubelingo.ensure_user_data_dir'):
        data = load_performance_data()
        assert data == expected_data
        mock_os_path_exists.assert_called_once_with(PERFORMANCE_FILE)
        mock_open_func.assert_called_once_with(PERFORMANCE_FILE, 'r')
        mock_yaml_safe_load.assert_called_once_with(mock_open_func.return_value)

def test_load_performance_data_yaml_error(mocker):
    mock_exists = mocker.patch('kubelingo.kubelingo.os.path.exists', return_value=True)
    mock_ensure_dir = mocker.patch('kubelingo.kubelingo.ensure_user_data_dir')
    mock_getsize = mocker.patch('kubelingo.kubelingo.os.path.getsize', return_value=100)
    mock_load = mocker.patch('kubelingo.kubelingo.yaml.safe_load', side_effect=yaml.YAMLError)
    mock_dump = mocker.patch('kubelingo.kubelingo.yaml.dump')
    mock_open_func = mocker.patch('builtins.open', mocker.mock_open())

    data = load_performance_data()

    assert data == {}
    mock_exists.assert_called_once_with(PERFORMANCE_FILE)
    assert mock_open_func.call_args_list == [mocker.call(PERFORMANCE_FILE, 'r'), mocker.call(PERFORMANCE_FILE, 'w')]
    mock_load.assert_called_once_with(mock_open_func.return_value.__enter__.return_value)
    mock_dump.assert_called_once_with({}, mock_open_func.return_value.__enter__.return_value)

def test_save_performance_data(mocker):
    mock_ensure_dir = mocker.patch('kubelingo.kubelingo.ensure_user_data_dir')
    mock_dump = mocker.patch('kubelingo.kubelingo.yaml.dump')
    mock_open_func = mocker.patch('builtins.open', mocker.mock_open())

    data_to_save = {'topic1': {'correct_questions': ['q1']}}
    save_performance_data(data_to_save)

    mock_ensure_dir.assert_called_once()
    mock_open_func.assert_called_once_with(PERFORMANCE_FILE, 'w')
    mock_dump.assert_called_once_with(data_to_save, mock_open_func.return_value.__enter__.return_value)