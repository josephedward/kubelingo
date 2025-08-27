

import pytest
from unittest.mock import patch, call
import os
import yaml
import re
from kubelingo.kubelingo import ensure_user_data_dir, save_question_to_list, remove_question_from_list, load_questions_from_list, get_normalized_question_text, normalize_command, clear_screen, handle_keys_menu, handle_config_menu, get_user_input, MISSED_QUESTIONS_FILE, USER_DATA_DIR

os.environ['KUBELINGO_DEBUG'] = 'True' # Enable debug logging

# --- Fixtures for mocking file system (from test_kubelingo_functions.py) ---

@pytest.fixture
def mock_user_data_dir():
    with patch('kubelingo.kubelingo.os.makedirs') as mock_makedirs:
        yield mock_makedirs

@pytest.fixture
def mock_os_path_getsize():
    with patch('kubelingo.kubelingo.os.path.getsize') as mock_getsize:
        yield mock_getsize

@pytest.fixture
def mock_yaml_dump():
    with patch('kubelingo.kubelingo.yaml.dump') as mock_dump:
        yield mock_dump

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
def mock_os_environ(mocker):
    # Patch os.environ with an empty dictionary, and let mocker handle cleanup
    mocker.patch.dict('os.environ', {}, clear=True)
    # Yield os.environ itself, as it's now the mocked dictionary
    yield os.environ, os.environ


def test_ensure_user_data_dir(mock_user_data_dir):
    ensure_user_data_dir()
    mock_user_data_dir.assert_called_once_with(USER_DATA_DIR, exist_ok=True)


# --- Tests for question list management (from test_kubelingo_functions.py) ---

@pytest.fixture
def mock_question_list_file(mock_os_path_exists, mock_yaml_safe_load, mock_yaml_dump, mock_builtins_open):
    # This fixture sets up a mock for a generic list file (e.g., missed_questions.yaml)
    # It returns a tuple: (mock_exists, mock_load, mock_dump, mock_open_func, mock_file_handle)
    # so individual tests can configure behavior.
    yield mock_os_path_exists, mock_yaml_safe_load, mock_yaml_dump, mock_builtins_open[0], mock_builtins_open[1]

def test_save_question_to_list_new_file(mock_question_list_file):
    mock_exists, mock_load, mock_dump, mock_open_func, mock_file_handle = mock_question_list_file
    mock_exists.return_value = False
    question = {'question': 'Test Q', 'solution': 'A'}
    topic = 'test_topic'
    
    save_question_to_list(MISSED_QUESTIONS_FILE, question, topic)
    
    mock_exists.assert_called_once_with(MISSED_QUESTIONS_FILE)
    mock_load.assert_not_called() # No file to load from
    
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
    mock_load.return_value = [question] # Duplicate
    topic = 'test_topic'

    save_question_to_list(MISSED_QUESTIONS_FILE, question, topic)

    mock_exists.assert_called_once_with(MISSED_QUESTIONS_FILE)
    mock_load.assert_called_once_with(mock_file_handle)
    mock_dump.assert_not_called() # Should not save if duplicate
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
    mock_dump.assert_called_once_with([existing_q1], mock_file_handle) # List should remain unchanged
    assert mock_open_func.call_args_list == [call(MISSED_QUESTIONS_FILE, 'r'), call(MISSED_QUESTIONS_FILE, 'w')]

def test_remove_question_from_list_no_file(mock_question_list_file):
    mock_exists, mock_load, mock_dump, mock_open_func, mock_file_handle = mock_question_list_file
    mock_exists.return_value = False
    question_to_remove = {'question': 'Q1', 'solution': 'A'}
    
    remove_question_from_list(MISSED_QUESTIONS_FILE, question_to_remove)
    
    mock_exists.assert_called_once_with(MISSED_QUESTIONS_FILE)
    mock_load.assert_not_called()
    mock_dump.assert_called_once_with([], mock_file_handle) # Should write an empty list
    mock_open_func.assert_called_once_with(MISSED_QUESTIONS_FILE, 'w')

def test_remove_question_from_list_yaml_error(mock_question_list_file):
    mock_exists, mock_load, mock_dump, mock_open_func, mock_file_handle = mock_question_list_file
    mock_exists.return_value = True
    mock_load.side_effect = yaml.YAMLError
    question_to_remove = {'question': 'Q1', 'solution': 'A'}

    remove_question_from_list(MISSED_QUESTIONS_FILE, question_to_remove)
    
    mock_dump.assert_called_once_with([], mock_file_handle) # Should write an empty list
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
    expected_questions = {'question': 'Q1'}
    mock_yaml_safe_load.return_value = expected_questions
    questions = load_questions_from_list(MISSED_QUESTIONS_FILE)
    assert questions == expected_questions
    mock_yaml_safe_load.assert_called_once_with(mock_file_handle)
    mock_open_func.assert_called_once_with(MISSED_QUESTIONS_FILE, 'r')

# --- Tests for get_normalized_question_text (from test_kubelingo_functions.py) ---

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

# --- Tests for normalize_command (from test_kubelingo_functions.py) ---

@pytest.mark.parametrize("input_commands, expected_output", [
    (["kubectl get pods"], ["kubectl get pod"]),
    (["k get po"], ["kubectl get pod"]),
    (["kubectl get deploy -n my-namespace"], ["kubectl get deployment --namespace my-namespace"]),
    (["kubectl get deploy --namespace my-namespace"], ["kubectl get deployment --namespace my-namespace"]),
    (["kubectl run my-pod --image=nginx --port=80"], ["kubectl run my-pod --image=nginx --port=80"]),
    (["kubectl run my-pod --port=80 --image=nginx"], ["kubectl run my-pod --image=nginx --port=80"]),
    (["kubectl create deployment my-app --image=my-image -n default"], ["kubectl create deployment my-app --image=my-image --namespace default"]),
    (["helm install my-release stable/chart -f values.yaml"], ["helm install my-release stable/chart -f values.yaml"]),
    ([""], [""])
    ,(["  kubectl   get   pods  "], ["kubectl get pod"]),
    (["kubectl get svc -o wide"], ["kubectl get service -o wide"]),
    (["kubectl get svc -A"], ["kubectl get service -A"]),
    (["kubectl get all -n kube-system"], ["kubectl get all --namespace kube-system"]),
    (["kubectl get pod my-pod -o yaml --namespace test"], ["kubectl get pod my-pod --namespace test -o yaml"]),
    (["kubectl get pod my-pod --namespace test -o yaml"], ["kubectl get pod my-pod --namespace test -o yaml"]),
])
def test_normalize_command(input_commands, expected_output):
    assert normalize_command(input_commands) == expected_output


# --- Tests for clear_screen (from test_kubelingo_functions.py) ---

def test_clear_screen():
    with patch('os.system') as mock_system:
        clear_screen()
        # Check for Windows or Unix command
        if os.name == 'nt':
            mock_system.assert_called_once_with('cls')
        else:
            mock_system.assert_called_once_with('clear')


# --- Tests for handle_config_menu (from test_kubelingo_functions.py) ---

@pytest.fixture
def mock_handle_config_menu_deps(mock_os_environ):
    mock_environ, mock_environ_values = mock_os_environ
    with patch('kubelingo.kubelingo.clear_screen') as mock_clear_screen:
        with patch('kubelingo.kubelingo.dotenv_values', side_effect=lambda *args, **kwargs: mock_environ) as mock_dotenv_values:
            with patch('kubelingo.kubelingo.set_key') as mock_set_key:
                # Make mock_set_key actually update os.environ
                def _mock_set_key_side_effect(dotenv_path, key_to_set, value_to_set):
                    os.environ[key_to_set] = value_to_set
                mock_set_key.side_effect = _mock_set_key_side_effect
                with patch('getpass.getpass', return_value='mock_getpass_key') as mock_getpass:
                    with patch('time.sleep') as mock_sleep:
                        yield mock_clear_screen, mock_dotenv_values, mock_set_key, mock_getpass, mock_environ, mock_sleep, mock_environ_values

def test_handle_config_menu_set_gemini_key(mock_handle_config_menu_deps, capsys):
    mock_clear_screen, mock_dotenv_values, mock_set_key, mock_getpass, mock_environ, mock_sleep, mock_environ_values = mock_handle_config_menu_deps
    mock_environ["GEMINI_API_KEY"] = "Not Set"
    mock_environ["OPENAI_API_KEY"] = "Not Set"
    mock_environ["OPENROUTER_API_KEY"] = "Not Set"

    with patch('builtins.input', side_effect=['1', 'mock_getpass_key', '5']):
        handle_keys_menu()
    
    mock_set_key.assert_called_once_with(".env", "GEMINI_API_KEY", 'mock_getpass_key')
    assert mock_environ_values["GEMINI_API_KEY"] == 'mock_getpass_key'
    
    captured = capsys.readouterr()
    assert "Gemini API Key saved." in captured.out

def test_handle_config_menu_set_openai_key(mock_handle_config_menu_deps, capsys):
    mock_clear_screen, mock_dotenv_values, mock_set_key, mock_getpass, mock_environ, mock_sleep, mock_environ_values = mock_handle_config_menu_deps
    mock_environ["GEMINI_API_KEY"] = "Not Set"
    mock_environ["OPENAI_API_KEY"] = "Not Set"
    mock_environ["OPENROUTER_API_KEY"] = "Not Set"
    
    with patch('builtins.input', side_effect=['1', '2', 'test_openai_key', '8', '3']):
        from kubelingo.kubelingo import handle_config_menu
        handle_config_menu()
        mock_set_key.assert_called_once_with(".env", "OPENAI_API_KEY", 'test_openai_key')
        assert mock_environ.get("OPENAI_API_KEY") == 'test_openai_key'
        
    captured = capsys.readouterr()
    assert "OpenAI API Key saved." in captured.out


def test_handle_config_menu_invalid_choice(mock_handle_config_menu_deps, capsys):
    mock_clear_screen, mock_dotenv_values, mock_set_key, mock_getpass, mock_environ, mock_sleep, mock_environ_values = mock_handle_config_menu_deps
    mock_environ.clear()  # No keys set

    with patch('builtins.input', side_effect=['invalid', '3']):
        handle_config_menu()

    mock_set_key.assert_not_called()

    captured = capsys.readouterr()
    assert "Invalid choice. Please try again." in captured.out

def test_handle_validation_menu_toggles(mock_handle_config_menu_deps, capsys):
    mock_clear_screen, mock_dotenv_values, mock_set_key, mock_getpass, mock_environ, mock_sleep, mock_environ_values = mock_handle_config_menu_deps
    # Initial config state (new validation toggles default to True if missing)
    mock_environ["KUBELINGO_VALIDATION_YAMLLINT"] = "True"
    mock_environ["KUBELINGO_VALIDATION_KUBECONFORM"] = "True"
    mock_environ["KUBELINGO_VALIDATION_KUBECTL_VALIDATE"] = "True"

    with patch('builtins.input', side_effect=['2', '1', '2', '3', '4', '3']):
        handle_config_menu()

    # Verify that set_key was called to toggle each setting
    calls = [
        call(".env", "KUBELINGO_VALIDATION_YAMLLINT", "False"),
        call(".env", "KUBELINGO_VALIDATION_KUBECONFORM", "False"),
        call(".env", "KUBELINGO_VALIDATION_KUBECTL_VALIDATE", "False"),
    ]
    mock_set_key.assert_has_calls(calls, any_order=True)

# --- Tests for get_user_input (from test_kubelingo_functions.py) ---

def test_get_user_input_done():
    with patch('builtins.input', side_effect=['command1', 'command2', 'done']):
        commands, action = get_user_input()
        assert commands == ['command1', 'command2']
        assert action is None

def test_get_user_input_special_action():
    with patch('builtins.input', side_effect=['command1', 'solution']):
        commands, action = get_user_input()
        assert commands == ['command1']
        assert action == 'solution'

def test_get_user_input_empty_line():
    with patch('builtins.input', side_effect=['', 'command1', 'done']):
        commands, action = get_user_input()
        assert commands == ['command1']
        assert action is None

def test_get_user_input_eof_error():
    with patch('builtins.input', side_effect=EOFError):
        commands, action = get_user_input()
        assert commands == []
        assert action is None
    
def test_get_user_input_prompt_output(capsys):
    # Ensure prompt text is displayed before reading input
    with patch('builtins.input', side_effect=EOFError):
        _ = get_user_input()
    captured = capsys.readouterr()
    expected = "Enter command(s). Type 'done' to check. Special commands: 'solution', 'vim', 'clear', 'menu'."
    assert expected in captured.out
    
def test_get_ai_verdict_fallback(monkeypatch):
    from kubelingo.kubelingo import get_ai_verdict
    # Simulate no AI model configured
    import kubelingo.kubelingo as kmod
    monkeypatch.setattr(kmod, '_get_llm_model', lambda skip_prompt=True: ('', None))
    result = get_ai_verdict('Sample Question', 'user answer', 'suggestion')
    # Fallback feedback when no model
    assert isinstance(result, dict)
    assert result.get('correct') is False
    feedback = result.get('feedback', '')
    assert feedback.startswith('INFO: Set'), "Expected fallback info message"






