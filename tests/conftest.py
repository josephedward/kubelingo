import pytest
import os
import yaml
from unittest.mock import patch, MagicMock, mock_open
import importlib
import unittest.mock as _um

# Provide pytest-mock style "mocker" fixture for tests
class _SimpleMocker:
    def __init__(self, monkeypatch):
        self._monkeypatch = monkeypatch
        self.patch = _Patch(self)
    def _create_mock_and_patch(self, target, **kwargs):
        parts = target.split('.')
        # Find the longest importable module prefix
        module = None
        rest = []
        for i in range(len(parts) - 1, 0, -1):
            module_name = '.'.join(parts[:i])
            try:
                module = importlib.import_module(module_name)
                rest = parts[i:]
                break
            except ModuleNotFoundError:
                continue
        if module is None:
            raise ImportError(f"Cannot import module from target '{target}'")
        # Traverse attributes to get parent object
        obj = module
        for attr in rest[:-1]:
            obj = getattr(obj, attr)
        attr_name = rest[-1]
        # Create the mock
        new_mock = MagicMock()
        if 'return_value' in kwargs:
            new_mock.return_value = kwargs['return_value']
        if 'side_effect' in kwargs:
            new_mock.side_effect = kwargs['side_effect']
        # Patch the attribute on the object
        self._monkeypatch.setattr(obj, attr_name, new_mock)
        return new_mock
    def mock_open(self, *args, **kwargs):
        return mock_open(*args, **kwargs)
    def MagicMock(self, *args, **kwargs):
        return MagicMock(*args, **kwargs)
    call = _um.call

class _Patch:
    def __init__(self, mocker):
        self._mocker = mocker
    def __call__(self, target, *args, **kwargs):
        # Resolve target to object and attribute
        parts = target.split('.')
        module = None
        rest = []
        for i in range(len(parts) - 1, 0, -1):
            module_name = '.'.join(parts[:i])
            try:
                module = importlib.import_module(module_name)
                rest = parts[i:]
                break
            except ModuleNotFoundError:
                continue
        if module is None:
            raise ImportError(f"Cannot import module from target '{target}'")
        obj = module
        for attr in rest[:-1]:
            obj = getattr(obj, attr)
        attr_name = rest[-1]
        # Determine new object for patch
        if args:
            new_obj = args[0]
        else:
            new_obj = MagicMock()
            if 'return_value' in kwargs:
                new_obj.return_value = kwargs['return_value']
            if 'side_effect' in kwargs:
                new_obj.side_effect = kwargs['side_effect']
        # Apply patch
        self._mocker._monkeypatch.setattr(obj, attr_name, new_obj)
        return new_obj
    def dict(self, target, new_dict=None, clear=False):
        parts = target.split('.')
        module_name = '.'.join(parts[:-1])
        attr_name = parts[-1]
        module = importlib.import_module(module_name)
        if clear:
            setattr(module, attr_name, new_dict)
        else:
            existing = getattr(module, attr_name)
            try:
                existing.update(new_dict or {})
            except Exception:
                setattr(module, attr_name, new_dict)
        return new_dict

@pytest.fixture
def mocker(monkeypatch):
    return _SimpleMocker(monkeypatch)

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
