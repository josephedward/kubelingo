import pytest
import os
import yaml
from unittest.mock import patch, mock_open, MagicMock, call
from kubelingo.kubelingo import load_performance_data
from kubelingo.performance_tracker import _performance_data_changed, save_performance_data
from kubelingo.utils import USER_DATA_DIR, PERFORMANCE_FILE, ensure_user_data_dir

@pytest.fixture(autouse=True)
def mock_performance_file_paths(mocker):
    test_user_data_dir = os.path.join(os.path.dirname(__file__), 'user_data')
    test_performance_file = os.path.join(test_user_data_dir, 'performance.yaml')
    mocker.patch('kubelingo.utils.USER_DATA_DIR', test_user_data_dir)
    mocker.patch('kubelingo.utils.PERFORMANCE_FILE', test_performance_file)
    mocker.patch('kubelingo.kubelingo.USER_DATA_DIR', test_user_data_dir)
    mocker.patch('kubelingo.kubelingo.PERFORMANCE_FILE', test_performance_file)
    mocker.patch('kubelingo.performance_tracker.PERFORMANCE_FILE', test_performance_file)
    # Ensure the test user_data directory exists
    os.makedirs(test_user_data_dir, exist_ok=True)
    # Clean up after each test
    yield
    # Remove test user_data directory without existence check to avoid interfering with os.path.exists stubs
    import shutil
    try:
        shutil.rmtree(test_user_data_dir)
    except Exception:
        pass

@pytest.fixture
def mock_os_path_exists():
    with patch('os.path.exists') as mock_exists:
        yield mock_exists

@pytest.fixture
def mock_yaml_safe_load():
    with patch('yaml.safe_load') as mock_safe_load:
        yield mock_safe_load

@pytest.fixture
def mock_yaml_dump():
    with patch('yaml.dump') as mock_dump:
        yield mock_dump

def test_load_performance_data_no_file(mock_os_path_exists, mock_yaml_dump, mocker):
    mocker.patch('kubelingo.utils.ensure_user_data_dir') # Patch ensure_user_data_dir directly
    mocker.patch('os.makedirs') # Mock os.makedirs to prevent it from calling os.path.exists multiple times
    mock_open = mocker.patch('builtins.open', mocker.mock_open()) # Patch builtins.open directly
    mock_os_path_exists.return_value = False
    with patch('kubelingo.kubelingo.os.path.getsize'):  # Needed for original load_performance_data logic
        data, loaded_ok = load_performance_data()
        assert data == {}
        assert loaded_ok is True
        # os.path.exists should have been called to check for the performance file
        assert mock_os_path_exists.called
        # The performance file should have been opened for writing and initialized with empty dict
        assert mock_open.called
        # Confirm it was opened in write mode
        called_args, called_kwargs = mock_open.call_args
        assert called_args[1] == 'w'
        mock_yaml_dump.assert_called_once_with({}, mock_open.return_value)

def test_load_performance_data_empty_file(mock_os_path_exists, mock_yaml_safe_load, mock_yaml_dump, mocker):
    mocker.patch('kubelingo.utils.ensure_user_data_dir') # Patch ensure_user_data_dir directly
    mocker.patch('os.makedirs') # Mock os.makedirs
    mock_open = mocker.patch('builtins.open', mocker.mock_open()) # Patch builtins.open directly
    mock_os_path_exists.return_value = True
    mock_yaml_safe_load.return_value = None
    data, loaded_ok = load_performance_data()
    assert data == {}
    assert loaded_ok == True
    # os.path.exists should have been used to check the performance file
    assert mock_os_path_exists.called
    # One of the calls should check a path ending with 'performance.yaml'
    assert any(call_args[0].endswith('performance.yaml') for call_args, _ in mock_os_path_exists.call_args_list)
    mock_yaml_safe_load.assert_called_once_with(mock_open.return_value) # Use .return_value for the file handle
    mock_yaml_dump.assert_not_called()

def test_load_performance_data_valid_file(mock_os_path_exists, mock_yaml_safe_load, mocker):
    mocker.patch('kubelingo.utils.ensure_user_data_dir') # Patch ensure_user_data_dir directly
    mocker.patch('os.makedirs') # Mock os.makedirs
    mock_open = mocker.patch('builtins.open', mocker.mock_open()) # Patch builtins.open directly
    mock_os_path_exists.return_value = True
    expected_data = {'topic1': {'correct_questions': ['q1']}}
    mock_yaml_safe_load.return_value = expected_data
    data, loaded_ok = load_performance_data()
    assert data == expected_data
    assert loaded_ok == True
    # os.path.exists should have been used to check the performance file
    assert mock_os_path_exists.called
    # Ensure a call checked the performance file path
    assert any(call_args[0].endswith('performance.yaml') for call_args, _ in mock_os_path_exists.call_args_list)
    # The performance file should have been opened for reading
    assert mock_open.called
    open_args, open_kwargs = mock_open.call_args
    assert open_args[1] == 'r'
    mock_yaml_safe_load.assert_called_once_with(mock_open.return_value)

def test_load_performance_data_yaml_error(mocker):
    mocker.patch('kubelingo.utils.ensure_user_data_dir') # Patch ensure_user_data_dir directly
    mocker.patch('os.makedirs') # Mock os.makedirs
    mock_exists = mocker.patch('os.path.exists', return_value=True)
    mock_getsize = mocker.patch('os.path.getsize', return_value=100)
    mock_load = mocker.patch('yaml.safe_load', side_effect=yaml.YAMLError)
    mock_dump = mocker.patch('yaml.dump')
    mock_open = mocker.patch('builtins.open', mocker.mock_open()) # Patch builtins.open directly

    data, loaded_ok = load_performance_data()

    assert data == {}
    assert loaded_ok == False
    # os.path.exists should have been used to check the performance file
    assert mock_exists.called
    assert any(call_args[0].endswith('performance.yaml') for call_args, _ in mock_exists.call_args_list)
    mock_load.assert_called_once_with(mock_open.return_value.__enter__.return_value)
    mock_dump.assert_not_called()

def test_save_performance_data(mocker):
    # Import save_performance_data here to ensure it uses the patched open
    from kubelingo.kubelingo import save_performance_data
    # Enable performance data saving by setting module flag
    import kubelingo.performance_tracker as pt
    pt._performance_data_changed = True

    mocker.patch('kubelingo.utils.ensure_user_data_dir') # Patch ensure_user_data_dir directly
    mocker.patch('os.makedirs') # Mock os.makedirs
    mock_dump = mocker.patch('yaml.dump')
    mock_open = mocker.patch('builtins.open', mocker.mock_open()) # Patch builtins.open directly

    data_to_save = {'topic1': {'correct_questions': ['q1']}}
    save_performance_data(data_to_save)

    # The performance file should have been opened for writing
    assert mock_open.called
    open_args, open_kwargs = mock_open.call_args
    assert open_args[1] == 'w'
    mock_dump.assert_called_once_with(data_to_save, mock_open.return_value.__enter__.return_value)