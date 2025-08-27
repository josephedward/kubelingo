import pytest
import os
import yaml
from unittest.mock import patch, MagicMock, mock_open

@pytest.fixture
def mock_os_path_exists():
    with patch('os.path.exists') as mock_exists:
        yield mock_exists

@pytest.fixture
def mock_os_makedirs():
    with patch('os.makedirs') as mock_makedirs:
        yield mock_makedirs

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
def mock_os_path_getsize():
    with patch('os.path.getsize') as mock_getsize:
        yield mock_getsize

@pytest.fixture
def mock_os_environ(mocker):
    mocker.patch.dict('os.environ', {}, clear=True)
    yield os.environ, os.environ

@pytest.fixture
def setup_user_data_dir(tmp_path, monkeypatch):
    # Create a temporary user_data directory
    user_data_path = tmp_path / "user_data"
    user_data_path.mkdir()
    # Patch kubelingo.USER_DATA_DIR to point to the temporary directory
    monkeypatch.setattr('kubelingo.kubelingo.USER_DATA_DIR', str(user_data_path))
    monkeypatch.setattr('kubelingo.issue_manager.USER_DATA_DIR', str(user_data_path))
    monkeypatch.setattr('kubelingo.question_generator.USER_DATA_DIR', str(user_data_path))
    yield user_data_path

@pytest.fixture
def setup_questions_dir(tmp_path, monkeypatch):
    # Create a temporary questions directory
    questions_path = tmp_path / "questions"
    questions_path.mkdir()
    # Patch kubelingo.QUESTIONS_DIR to point to the temporary directory
    monkeypatch.setattr('kubelingo.kubelingo.QUESTIONS_DIR', str(questions_path))
    monkeypatch.setattr('kubelingo.utils.QUESTIONS_DIR', str(questions_path))
    monkeypatch.setattr('kubelingo.question_generator.QUESTIONS_DIR', str(questions_path))
    monkeypatch.setattr('kubelingo.issue_manager.QUESTIONS_DIR', str(questions_path))
    yield questions_path
