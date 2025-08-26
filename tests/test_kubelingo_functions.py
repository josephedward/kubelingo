import pytest
import os
import yaml
from dotenv import dotenv_values
from unittest.mock import patch, mock_open, MagicMock, call
from colorama import Fore, Style
from kubelingo.kubelingo import (
    ensure_user_data_dir,
    load_performance_data,
    save_performance_data,
    save_question_to_list,
    remove_question_from_list,
    load_questions_from_list,
    get_normalized_question_text,
    normalize_command,
    update_question_source_in_yaml,
    create_issue,
    clear_screen,
    load_questions,
    get_user_input,
    _get_llm_model,
    get_ai_verdict,
    validate_manifest_with_llm,
    generate_more_questions,
    USER_DATA_DIR,
    QUESTIONS_DIR,
    MISSED_QUESTIONS_FILE,
    ISSUES_FILE,
    validate_manifest_with_kubectl_dry_run,
    validate_kubectl_command_dry_run
)

PERFORMANCE_FILE = os.path.join("test/user_data", "performance.yaml")
# --- Fixtures for mocking file system ---

@pytest.fixture
def mock_user_data_dir():
    with patch('os.makedirs') as mock_makedirs:
        yield mock_makedirs

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
def mock_builtins_open():
    # Create a mock for the file handle that mock_open would return
    mock_file_handle = MagicMock()
    # Configure mock_open to return our mock_file_handle when called
    with patch('builtins.open', return_value=mock_file_handle) as m_open:
        # Allow entering and exiting the context manager
        m_open.return_value.__enter__.return_value = mock_file_handle
        yield m_open, mock_file_handle

# --- Tests for user_data directory and performance data ---

def test_ensure_user_data_dir(mock_user_data_dir):
    ensure_user_data_dir()
    mock_user_data_dir.assert_called_once_with(USER_DATA_DIR, exist_ok=True)

def test_load_performance_data_no_file(mock_os_path_exists):
    mock_os_path_exists.return_value = False
    data = load_performance_data()
    assert data == {}
    mock_os_path_exists.assert_called_once_with(PERFORMANCE_FILE)

def test_load_performance_data_empty_file(mock_os_path_exists, mock_yaml_safe_load, mock_builtins_open):
    mock_open_func, mock_file_handle = mock_builtins_open
    mock_os_path_exists.return_value = True
    mock_yaml_safe_load.return_value = None
    data = load_performance_data()
    assert data == {}
    mock_yaml_safe_load.assert_called_once_with(mock_file_handle)
    mock_open_func.assert_has_calls([call(PERFORMANCE_FILE, 'r'), call(PERFORMANCE_FILE, 'w')])

def test_load_performance_data_valid_file(mock_os_path_exists, mock_yaml_safe_load, mock_builtins_open):
    mock_open_func, mock_file_handle = mock_builtins_open
    mock_os_path_exists.return_value = True
    expected_data = {'topic1': {'correct_questions': ['q1']}}
    mock_yaml_safe_load.return_value = expected_data
    data = load_performance_data()
    assert data == expected_data
    mock_yaml_safe_load.assert_called_once_with(mock_file_handle)
    mock_open_func.assert_called_once_with(PERFORMANCE_FILE, 'r')

def test_load_performance_data_yaml_error(mock_os_path_exists, mock_yaml_safe_load, mock_builtins_open):
    mock_open_func, mock_file_handle = mock_builtins_open
    mock_os_path_exists.return_value = True
    mock_yaml_safe_load.side_effect = yaml.YAMLError
    data = load_performance_data()
    assert data == {}
    mock_yaml_safe_load.assert_called_once_with(mock_file_handle)
    mock_open_func.assert_has_calls([call(PERFORMANCE_FILE, 'r'), call(PERFORMANCE_FILE, 'w')])

def test_save_performance_data(mock_user_data_dir, mock_yaml_dump, mock_builtins_open):
    mock_open_func, mock_file_handle = mock_builtins_open
    data_to_save = {'topic1': {'correct_questions': ['q1']}}
    save_performance_data(data_to_save)
    mock_user_data_dir.assert_called_once()
    mock_open_func.assert_called_once_with(PERFORMANCE_FILE, 'w')
    mock_yaml_dump.assert_called_once_with(data_to_save, mock_file_handle)

# --- Tests for question list management ---

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

# --- Tests for normalize_command ---

@pytest.mark.parametrize("input_commands, expected_output", [
    (["kubectl get pods"], ["kubectl get pod"]),
    (["k get po"], ["kubectl get pod"]),
    (["kubectl get deploy -n my-namespace"], ["kubectl get deployment --namespace my-namespace"]),
    (["kubectl get deploy --namespace my-namespace"], ["kubectl get deployment --namespace my-namespace"]),
    (["kubectl run my-pod --image=nginx --port=80"], ["kubectl run my-pod --image=nginx --port=80"]),
    (["kubectl run my-pod --port=80 --image=nginx"], ["kubectl run my-pod --image=nginx --port=80"]),
    (["kubectl create deployment my-app --image=my-image -n default"], ["kubectl create deployment my-app --image=my-image --namespace default"]),
    (["helm install my-release stable/chart -f values.yaml"], ["helm install my-release stable/chart -f values.yaml"]),
    ([""], [""]), # Empty command
    (["  kubectl   get   pods  "], ["kubectl get pod"]), # Extra spaces
    (["kubectl get svc -o wide"], ["kubectl get service -o wide"]),
    (["kubectl get svc -A"], ["kubectl get service -A"]),
    (["kubectl get all -n kube-system"], ["kubectl get all --namespace kube-system"]),
    (["kubectl get pod my-pod -o yaml --namespace test"], ["kubectl get pod my-pod --namespace test -o yaml"]),
    (["kubectl get pod my-pod --namespace test -o yaml"], ["kubectl get pod my-pod --namespace test -o yaml"]),
])
def test_normalize_command(input_commands, expected_output):
    assert normalize_command(input_commands) == expected_output

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

# --- Tests for create_issue ---

@pytest.fixture
def mock_create_issue_deps(mock_os_path_exists, mock_yaml_safe_load, mock_yaml_dump, mock_builtins_open):
    with patch('kubelingo.kubelingo.remove_question_from_list') as mock_remove_question_from_list:
        with patch('time.asctime', return_value='mock_timestamp') as mock_asctime:
            yield mock_os_path_exists, mock_yaml_safe_load, mock_yaml_dump, mock_builtins_open[0], mock_builtins_open[1], mock_remove_question_from_list, mock_asctime

def test_create_issue_valid_input(mock_create_issue_deps, capsys):
    mock_exists, mock_load, mock_dump, mock_open_func, mock_file_handle, mock_remove_question_from_list, mock_asctime = mock_create_issue_deps
    mock_exists.return_value = False # No existing issues file
    
    question_dict = {'question': 'Test Question'}
    topic = 'test_topic'
    user_input = "This is a test issue."

    with patch('builtins.input', return_value=user_input):
        create_issue(question_dict, topic)
    
    mock_exists.assert_called_once_with(ISSUES_FILE)
    mock_load.assert_not_called()
    
    expected_issue = {
        'topic': topic,
        'question': question_dict['question'],
        'issue': user_input,
        'timestamp': 'mock_timestamp'
    }
    mock_dump.assert_called_once_with([expected_issue], mock_file_handle)
    mock_open_func.assert_called_once_with(ISSUES_FILE, 'w')
    mock_remove_question_from_list.assert_called_once_with(MISSED_QUESTIONS_FILE, question_dict)
    
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
    
    question_dict = {'question': 'Test Question'}
    topic = 'test_topic'
    user_input = "New issue."

    with patch('builtins.input', return_value=user_input):
        create_issue(question_dict, topic)
    
    mock_exists.assert_called_once_with(ISSUES_FILE)
    mock_load.assert_called_once_with(mock_file_handle)
    
    expected_issue = {
        'topic': topic,
        'question': question_dict['question'],
        'issue': user_input,
        'timestamp': 'mock_timestamp'
    }
    expected_list = [{'issue': 'Old Issue'}, expected_issue]
    mock_dump.assert_called_once_with(expected_list, mock_file_handle)
    assert mock_open_func.call_args_list == [call(ISSUES_FILE, 'r'), call(ISSUES_FILE, 'w')]
    mock_remove_question_from_list.assert_called_once_with(MISSED_QUESTIONS_FILE, question_dict)

# --- Tests for clear_screen ---

def test_clear_screen():
    with patch('os.system') as mock_system:
        clear_screen()
        # Check for Windows or Unix command
        if os.name == 'nt':
            mock_system.assert_called_once_with('cls')
        else:
            mock_system.assert_called_once_with('clear')

# --- Tests for load_questions ---

@pytest.fixture
def mock_load_questions_deps(mock_os_path_exists, mock_yaml_safe_load, mock_builtins_open):
    with patch('os.listdir', return_value=['topic1.yaml', 'topic2.yaml']):
        yield mock_os_path_exists, mock_yaml_safe_load, mock_builtins_open[0], mock_builtins_open[1]

def test_load_questions_file_not_found(mock_load_questions_deps, capsys):
    mock_exists, mock_load, mock_open_func, mock_file_handle = mock_load_questions_deps
    mock_exists.return_value = False
    
    topic = 'non_existent_topic'
    result = load_questions(topic)
    
    assert result is None
    expected_path = os.path.join(QUESTIONS_DIR, f"{topic}.yaml")
    mock_exists.assert_called_once_with(expected_path)
    mock_load.assert_not_called()
    mock_open_func.assert_not_called()
    
    captured = capsys.readouterr()
    assert f"Error: Question file not found at {expected_path}" in captured.out
    assert "Available topics: topic1, topic2" in captured.out

def test_load_questions_file_found(mock_load_questions_deps):
    mock_exists, mock_load, mock_open_func, mock_file_handle = mock_load_questions_deps
    mock_exists.return_value = True
    expected_data = {'questions': [{'question': 'Q1'}]}
    mock_load.return_value = expected_data
    
    topic = 'existing_topic'
    result = load_questions(topic)
    
    assert result == expected_data
    expected_path = os.path.join(QUESTIONS_DIR, f"{topic}.yaml")
    mock_exists.assert_called_once_with(expected_path)
    mock_load.assert_called_once_with(mock_file_handle)
    mock_open_func.assert_called_once_with(expected_path, 'r')

# --- Tests for handle_config_menu ---

@pytest.fixture
def mock_handle_config_menu_deps():
    # Create a mock for os.environ that behaves like a dictionary
    mock_environ_dict = {}
    mock_environ = MagicMock(wraps=mock_environ_dict)
    mock_environ.get.side_effect = mock_environ_dict.get
    mock_environ.__setitem__.side_effect = mock_environ_dict.__setitem__

    with patch('kubelingo.kubelingo.clear_screen') as mock_clear_screen:
        with patch('kubelingo.kubelingo.dotenv_values') as mock_dotenv_values:
            with patch('kubelingo.kubelingo.set_key') as mock_set_key:
                with patch('os.environ', new=mock_environ) as mock_os_environ:
                    with patch('time.sleep') as mock_sleep:
                        yield mock_clear_screen, mock_dotenv_values, mock_set_key, mock_os_environ, mock_sleep

def test_handle_config_menu_set_gemini_key(mock_handle_config_menu_deps, capsys):
    mock_clear_screen, mock_dotenv_values, mock_set_key, mock_os_environ, mock_sleep = mock_handle_config_menu_deps
    mock_dotenv_values.return_value = {"GEMINI_API_KEY": "Not Set", "OPENAI_API_KEY": "Not Set"}
    
    # Simulate user input: 1 (API Keys), 1 (set Gemini), then a key, then 3 (back), 3 (back)
    with patch('builtins.input', side_effect=['1', '1', 'test_gemini_key', '8', '3']):
        mock_set_key.assert_called_once_with(".env", "GEMINI_API_KEY", 'test_gemini_key')
        assert mock_os_environ.get("GEMINI_API_KEY") == 'test_gemini_key'
        
        captured = capsys.readouterr()
        assert "Gemini API Key saved." in captured.out

def test_handle_config_menu_set_openai_key(mock_handle_config_menu_deps, capsys):
    mock_clear_screen, mock_dotenv_values, mock_set_key, mock_os_environ, mock_sleep = mock_handle_config_menu_deps
    mock_dotenv_values.return_value = {"GEMINI_API_KEY": "Not Set", "OPENAI_API_KEY": "Not Set"}
    
    # Simulate user input: 1 (API Keys), 2 (set OpenAI), then a key, then 3 (back), 3 (back)
    # Simulate user input: 1 (API Keys), 2 (set OpenAI), then a key, then 3 (back), 3 (back)
    with patch('builtins.input', side_effect=['1', '2', 'test_openai_key', '8', '3']):
        mock_set_key.assert_called_once_with(".env", "OPENAI_API_KEY", 'test_openai_key')
        assert mock_os_environ.get("OPENAI_API_KEY") == 'test_openai_key'
        
        captured = capsys.readouterr()
        assert "OpenAI API Key saved." in captured.out



def test_handle_config_menu_invalid_choice(mock_handle_config_menu_deps, capsys):
    mock_clear_screen, mock_dotenv_values, mock_set_key, mock_os_environ, mock_sleep = mock_handle_config_menu_deps
    mock_dotenv_values.return_value = {} # No keys set
    
    # Simulate user input: invalid, then 3 (back to main menu)
    with patch('builtins.input', side_effect=['invalid', '3']):
    
        mock_set_key.assert_not_called()
    
    captured = capsys.readouterr()
    assert "Invalid choice. Please try again." in captured.out

def test_handle_validation_menu_toggles(mock_handle_config_menu_deps, capsys):
    mock_clear_screen, mock_dotenv_values, mock_set_key, mock_os_environ, mock_sleep = mock_handle_config_menu_deps
    # Initial config state
    # Initial config state (new validation toggles default to True if missing)
    mock_dotenv_values.return_value = {
        "KUBELINGO_VALIDATION_YAMLLINT": "True",
        "KUBELINGO_VALIDATION_KUBECONFORM": "True",
        "KUBELINGO_VALIDATION_KUBECTL_VALIDATE": "True",
    }

    # Simulate toggling each setting off, then exit menus
    with patch('builtins.input', side_effect=['2', '1', '2', '3', '4', '3']):

        # Verify that set_key was called to toggle each setting
        calls = [
            call(".env", "KUBELINGO_VALIDATION_YAMLLINT", "False"),
            call(".env", "KUBELINGO_VALIDATION_KUBECONFORM", "False"),
            call(".env", "KUBELINGO_VALIDATION_KUBECTL_VALIDATE", "False"),
        ]
        mock_set_key.assert_has_calls(calls, any_order=True)

# --- Tests for get_user_input ---

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

def test_get_user_input_clear_empty(capsys):
    with patch('builtins.input', side_effect=['clear', 'done']):
        commands, action = get_user_input()
        assert commands == []
        assert action is None
        captured = capsys.readouterr()
        assert "(No input to clear)" in captured.out

def test_get_user_input_clear_with_commands(capsys):
    with patch('builtins.input', side_effect=['cmd1', 'cmd2', 'clear', 'done']):
        commands, action = get_user_input()
        assert commands == []
        assert action is None
        captured = capsys.readouterr()
        assert "(Input cleared)" in captured.out

def test_get_user_input_empty_line():
    with patch('builtins.input', side_effect=['', 'command1', 'done']):
        commands, action = get_user_input()
        assert commands == ['command1']
        assert action is None

def test_get_user_input_eof_error():
    with patch('builtins.input', side_effect=EOFError):
        commands, action = get_user_input()
        assert commands == []
        assert action == 'skip'

# --- Tests for LLM Interactions ---

@pytest.fixture
def mock_llm_deps():
    with (
        patch('google.generativeai.configure') as mock_gemini_configure,
        patch('google.generativeai.GenerativeModel') as MockGenerativeModel_class,
        patch('openai.OpenAI') as MockOpenAI_class,
        patch('kubelingo.kubelingo.os.environ', new={}) as mock_environ,
        patch('kubelingo.kubelingo.click.confirm', return_value=False) as mock_click_confirm,
        patch('kubelingo.kubelingo.handle_config_menu') as mock_handle_config_menu,
        patch('requests.post') as mock_requests_post
    ):
        # Configure mock response for OpenRouter health check
        mock_requests_post.return_value.status_code = 200
        mock_requests_post.return_value.json.return_value = {}

        # Configure the class mocks to return specific mock instances
        mock_gemini_model_instance = MagicMock()
        MockGenerativeModel_class.return_value = mock_gemini_model_instance

        mock_openai_client_instance = MagicMock()
        MockOpenAI_class.return_value = mock_openai_client_instance

        yield mock_gemini_configure, MockGenerativeModel_class, mock_gemini_model_instance, MockOpenAI_class, mock_openai_client_instance, mock_environ, mock_click_confirm, mock_handle_config_menu, mock_requests_post

def test_get_llm_model_openrouter_first(mock_llm_deps):
    mock_gemini_configure, MockGenerativeModel_class, mock_gemini_model_instance, MockOpenAI_class, mock_openai_client_instance, mock_environ, mock_click_confirm, mock_handle_config_menu, mock_requests_post = mock_llm_deps
    mock_environ["OPENROUTER_API_KEY"] = "test-or"
    
    llm_type, model = _get_llm_model()
    
    assert llm_type == "openrouter"
    assert model["api_key"] == "test-or"
    mock_requests_post.assert_called_once()

def test_get_llm_model_openrouter_failure_falls_back(mock_llm_deps):
    mock_gemini_configure, MockGenerativeModel_class, mock_gemini_model_instance, MockOpenAI_class, mock_openai_client_instance, mock_environ, mock_click_confirm, mock_handle_config_menu, mock_requests_post = mock_llm_deps
    mock_environ["OPENROUTER_API_KEY"] = "test-or"
    mock_environ["GEMINI_API_KEY"] = "test-gemini"
    mock_requests_post.return_value.raise_for_status.side_effect = Exception("API error")
    mock_gemini_model_instance.generate_content.return_value.text = "test response"
    
    llm_type, model = _get_llm_model()
    
    assert llm_type == "gemini"
    mock_requests_post.assert_called_once()
    assert MockGenerativeModel_class.call_count == 2

@pytest.mark.skipif(
    not dotenv_values().get("GEMINI_API_KEY"),
    reason="Skipping Gemini tests because GEMINI_API_KEY is not set."
)
def test_get_llm_model_gemini_only(mock_llm_deps):
    mock_gemini_configure, MockGenerativeModel_class, mock_gemini_model_instance, MockOpenAI_class, mock_openai_client_instance, mock_environ, mock_click_confirm, mock_handle_config_menu, mock_requests_post = mock_llm_deps
    mock_environ["GEMINI_API_KEY"] = "test_gemini_key"
    
    llm_type, model = _get_llm_model()
    
    mock_gemini_configure.assert_called_once_with(api_key="test_gemini_key")
    assert MockGenerativeModel_class.call_count == 2
    assert MockGenerativeModel_class.call_args_list == [
        call('gemini-1.5-flash-latest'),
        call('gemini-1.5-flash-latest')
    ]
    mock_gemini_model_instance.generate_content.assert_called_once_with("hello", stream=False)
    MockOpenAI_class.assert_not_called()
    assert llm_type == "gemini"
    assert model == mock_gemini_model_instance
    mock_click_confirm.assert_not_called()
    mock_handle_config_menu.assert_not_called()

def test_get_llm_model_openai_only(mock_llm_deps):
    mock_gemini_configure, MockGenerativeModel_class, mock_gemini_model_instance, MockOpenAI_class, mock_openai_client_instance, mock_environ, mock_click_confirm, mock_handle_config_menu, mock_requests_post = mock_llm_deps
    mock_environ["OPENAI_API_KEY"] = "test_openai_key"
    
    llm_type, model = _get_llm_model()
    
    mock_gemini_configure.assert_not_called()
    MockGenerativeModel_class.assert_not_called()
    mock_gemini_model_instance.generate_content.assert_not_called() # No Gemini key, so no call
    MockOpenAI_class.assert_called_once_with(api_key="test_openai_key")
    mock_openai_client_instance.chat.completions.create.assert_called_once_with(model="gpt-3.5-turbo", messages=[{"role": "user", "content": "hello"}], max_tokens=5)
    assert llm_type == "openai"
    assert model == mock_openai_client_instance
    mock_click_confirm.assert_not_called()
    mock_handle_config_menu.assert_not_called()

def test_get_llm_model_both_gemini_preferred(mock_llm_deps):
    mock_gemini_configure, MockGenerativeModel_class, mock_gemini_model_instance, MockOpenAI_class, mock_openai_client_instance, mock_environ, mock_click_confirm, mock_handle_config_menu, mock_requests_post = mock_llm_deps
    mock_environ["GEMINI_API_KEY"] = "test_gemini_key"
    mock_environ["OPENAI_API_KEY"] = "test_openai_key"
    
    llm_type, model = _get_llm_model()
    
    mock_gemini_configure.assert_called_once_with(api_key="test_gemini_key")
    assert MockGenerativeModel_class.call_count == 2
    assert MockGenerativeModel_class.call_args_list == [
        call('gemini-1.5-flash-latest'),
        call('gemini-1.5-flash-latest')
    ]
    mock_gemini_model_instance.generate_content.assert_called_once_with("hello", stream=False)
    MockOpenAI_class.assert_not_called() # Gemini is preferred, so OpenAI should not be initialized
    mock_openai_client_instance.chat.completions.create.assert_not_called() # OpenAI's create method should not be called
    assert llm_type == "gemini"
    assert model == mock_gemini_model_instance
    mock_click_confirm.assert_not_called()
    mock_handle_config_menu.assert_not_called()

def test_get_llm_model_neither(mock_llm_deps):
    mock_gemini_configure, MockGenerativeModel_class, mock_gemini_model_instance, MockOpenAI_class, mock_openai_client_instance, mock_environ, mock_click_confirm, mock_handle_config_menu, mock_requests_post = mock_llm_deps
    # No API keys set
    
    llm_type, model = _get_llm_model()
    
    mock_gemini_configure.assert_not_called()
    MockGenerativeModel_class.assert_not_called()
    mock_gemini_model_instance.generate_content.assert_not_called()
    MockOpenAI_class.assert_not_called()
    mock_openai_client_instance.chat.completions.create.assert_not_called()
    mock_click_confirm.assert_called_once_with(f"{Fore.CYAN}Would you like to configure API keys now?{Style.RESET_ALL}", default=True)
    mock_handle_config_menu.assert_not_called() # Because mock_click_confirm returns False
    assert llm_type is None
    assert model is None
    assert llm_type is None
    assert model is None

@pytest.mark.skipif(
    not dotenv_values().get("GEMINI_API_KEY"),
    reason="Skipping Gemini tests because GEMINI_API_KEY is not set."
)
def test_get_ai_verdict_gemini(mock_llm_deps):
    mock_gemini_configure, MockGenerativeModel_class, mock_gemini_model_instance, MockOpenAI_class, mock_openai_client_instance, mock_environ, mock_click_confirm, mock_handle_config_menu, mock_requests_post = mock_llm_deps
    
    # Patch _get_llm_model to return a configured Gemini model
    with patch('kubelingo.kubelingo._get_llm_model', return_value=("gemini", mock_gemini_model_instance)) as mock_get_llm_model:
        mock_response = MagicMock()
        mock_response.text = "FEEDBACK: Gemini feedback.\nVERDICT: CORRECT"
        mock_gemini_model_instance.generate_content.return_value = mock_response
        
        question = "Q"
        user_answer = "A"
        solution = "S"
        
        result = get_ai_verdict(question, user_answer, solution)
        
        mock_get_llm_model.assert_called_once() # Ensure _get_llm_model was called
        mock_gemini_model_instance.generate_content.assert_called_once() # Assert on the instance's method
        assert result['feedback'] == "Gemini feedback."
        assert result['correct'] == True



def test_get_llm_feedback_openai(mock_llm_deps):
    mock_gemini_configure, MockGenerativeModel_class, mock_gemini_model_instance, MockOpenAI_class, mock_openai_client_instance, mock_environ, mock_click_confirm, mock_handle_config_menu, mock_requests_post = mock_llm_deps
    
    # Patch _get_llm_model to return a configured OpenAI model
    with patch('kubelingo.kubelingo._get_llm_model', return_value=("openai", mock_openai_client_instance)) as mock_get_llm_model:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "FEEDBACK: OpenAI feedback.\nVERDICT: INCORRECT"
        mock_openai_client_instance.chat.completions.create.return_value = mock_response
        
        question = "Q"
        user_answer = "A"
        solution = "S"
        
        result = get_ai_verdict(question, user_answer, solution)
        
        mock_get_llm_model.assert_called_once()
        mock_openai_client_instance.chat.completions.create.assert_called_once()
        assert result['feedback'] == "OpenAI feedback."
        assert result['correct'] == False


def test_get_llm_feedback_no_llm(mock_llm_deps):
    mock_gemini_configure, MockGenerativeModel_class, mock_gemini_model_instance, MockOpenAI_class, mock_openai_client_instance, mock_environ, mock_click_confirm, mock_handle_config_menu, mock_requests_post = mock_llm_deps
    
    # Patch _get_llm_model to return no model
    with patch('kubelingo.kubelingo._get_llm_model', return_value=(None, None)) as mock_get_llm_model:
        result = get_ai_verdict("Q", "A", "S")
        
        mock_get_llm_model.assert_called_once()
        assert result == {'correct': False, 'feedback': "INFO: Set GEMINI_API_KEY, OPENAI_API_KEY, or OPENROUTER_API_KEY for AI-powered validation."}
        MockGenerativeModel_class.assert_not_called()
        MockOpenAI_class.assert_not_called()

def test_get_llm_feedback_gemini_error(mock_llm_deps):
    mock_gemini_configure, MockGenerativeModel_class, mock_gemini_model_instance, MockOpenAI_class, mock_openai_client_instance, mock_environ, mock_click_confirm, mock_handle_config_menu, mock_requests_post = mock_llm_deps
    
    # Patch _get_llm_model to return a configured Gemini model
    with patch('kubelingo.kubelingo._get_llm_model', return_value=("gemini", mock_gemini_model_instance)) as mock_get_llm_model:
        mock_gemini_model_instance.generate_content.side_effect = Exception("Gemini error")
        
        result = get_ai_verdict("Q", "A", "S")
        
        mock_get_llm_model.assert_called_once()
        mock_gemini_model_instance.generate_content.assert_called_once()
        assert result['correct'] == False
        assert "Error getting AI verdict: Gemini error" in result['feedback']

def test_get_llm_feedback_openai_error(mock_llm_deps):
    mock_gemini_configure, MockGenerativeModel_class, mock_gemini_model_instance, MockOpenAI_class, mock_openai_client_instance, mock_environ, mock_click_confirm, mock_handle_config_menu, mock_requests_post = mock_llm_deps
    
    # Patch _get_llm_model to return a configured OpenAI model
    with patch('kubelingo.kubelingo._get_llm_model', return_value=("openai", mock_openai_client_instance)) as mock_get_llm_model:
        mock_openai_client_instance.chat.completions.create.side_effect = Exception("OpenAI error")
        
        result = get_ai_verdict("Q", "A", "S")
        
        mock_get_llm_model.assert_called_once()
        mock_openai_client_instance.chat.completions.create.assert_called_once()
        assert result['correct'] == False
        assert "Error getting AI verdict: OpenAI error" in result['feedback']

@pytest.mark.skipif(
    not dotenv_values().get("GEMINI_API_KEY"),
    reason="Skipping Gemini tests because GEMINI_API_KEY is not set."
)
def test_validate_manifest_with_llm_gemini(mock_llm_deps):
    mock_gemini_configure, MockGenerativeModel_class, mock_gemini_model_instance, MockOpenAI_class, mock_openai_client_instance, mock_environ, mock_click_confirm, mock_handle_config_menu, mock_requests_post = mock_llm_deps
    
    # Patch _get_llm_model to return a configured Gemini model
    with patch('kubelingo.kubelingo._get_llm_model', return_value=("gemini", mock_gemini_model_instance)) as mock_get_llm_model:
        mock_response = MagicMock()
        mock_response.text = "CORRECT\nManifest is valid."
        mock_gemini_model_instance.generate_content.return_value = mock_response
        
        question_dict = {'question': 'Q', 'solution': 'S'}
        user_manifest = "M"
        
        result = validate_manifest_with_llm(question_dict, user_manifest)
        
        mock_get_llm_model.assert_called_once()
        mock_gemini_model_instance.generate_content.assert_called_once()
        assert result == {'correct': True, 'feedback': 'Manifest is valid.'}

def test_validate_manifest_with_llm_openai(mock_llm_deps):
    mock_gemini_configure, MockGenerativeModel_class, mock_gemini_model_instance, MockOpenAI_class, mock_openai_client_instance, mock_environ, mock_click_confirm, mock_handle_config_menu, mock_requests_post = mock_llm_deps
    
    # Patch _get_llm_model to return a configured OpenAI model
    with patch('kubelingo.kubelingo._get_llm_model', return_value=("openai", mock_openai_client_instance)) as mock_get_llm_model:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "INCORRECT\nManifest is missing a field."
        mock_openai_client_instance.chat.completions.create.return_value = mock_response
        
        question_dict = {'question': 'Q', 'solution': 'S'}
        user_manifest = "M"
        
        result = validate_manifest_with_llm(question_dict, user_manifest)
        
        mock_get_llm_model.assert_called_once()
        mock_openai_client_instance.chat.completions.create.assert_called_once()
        assert result == {'correct': False, 'feedback': 'Manifest is missing a field.'}

def test_validate_manifest_with_llm_no_llm(mock_llm_deps):
    mock_gemini_configure, MockGenerativeModel_class, mock_gemini_model_instance, MockOpenAI_class, mock_openai_client_instance, mock_environ, mock_click_confirm, mock_handle_config_menu, mock_requests_post = mock_llm_deps
    
    # Patch _get_llm_model to return no model
    with patch('kubelingo.kubelingo._get_llm_model', return_value=(None, None)) as mock_get_llm_model:
        result = validate_manifest_with_llm({'question': 'Q', 'solution': 'S'}, "M")
        
        mock_get_llm_model.assert_called_once()
        assert result == {'correct': False, 'feedback': "INFO: Set GEMINI_API_KEY or OPENAI_API_KEY for AI-powered manifest validation."}
        MockGenerativeModel_class.assert_not_called()
        MockOpenAI_class.assert_not_called()

def test_validate_manifest_with_llm_gemini_error(mock_llm_deps):
    mock_gemini_configure, MockGenerativeModel_class, mock_gemini_model_instance, MockOpenAI_class, mock_openai_client_instance, mock_environ, mock_click_confirm, mock_handle_config_menu, mock_requests_post = mock_llm_deps
    
    # Patch _get_llm_model to return a configured Gemini model
    with patch('kubelingo.kubelingo._get_llm_model', return_value=("gemini", mock_gemini_model_instance)) as mock_get_llm_model:
        mock_gemini_model_instance.generate_content.side_effect = Exception("Gemini manifest error")
        
        result = validate_manifest_with_llm({'question': 'Q', 'solution': 'S'}, "M")
        
        mock_get_llm_model.assert_called_once()
        mock_gemini_model_instance.generate_content.assert_called_once()
        assert result == {'correct': False, 'feedback': "Error validating manifest with LLM: Gemini manifest error"}

def test_validate_manifest_with_llm_openai_error(mock_llm_deps):
    mock_gemini_configure, MockGenerativeModel_class, mock_gemini_model_instance, MockOpenAI_class, mock_openai_client_instance, mock_environ, mock_click_confirm, mock_handle_config_menu, mock_requests_post = mock_llm_deps
    
    # Patch _get_llm_model to return a configured OpenAI model
    with patch('kubelingo.kubelingo._get_llm_model', return_value=("openai", mock_openai_client_instance)) as mock_get_llm_model:
        mock_openai_client_instance.chat.completions.create.side_effect = Exception("OpenAI manifest error")
        
        result = validate_manifest_with_llm({'question': 'Q', 'solution': 'S'}, "M")
        
        mock_get_llm_model.assert_called_once()
        mock_openai_client_instance.chat.completions.create.assert_called_once()
        assert result == {'correct': False, 'feedback': "Error validating manifest with LLM: OpenAI manifest error"}

@pytest.mark.skipif(
    not dotenv_values().get("GEMINI_API_KEY"),
    reason="Skipping Gemini tests because GEMINI_API_KEY is not set."
)
def test_generate_more_questions_gemini(mock_llm_deps, mock_builtins_open, mock_yaml_safe_load, mock_yaml_dump, capsys):
    mock_gemini_configure, MockGenerativeModel_class, mock_gemini_model_instance, MockOpenAI_class, mock_openai_client_instance, mock_environ, mock_click_confirm, mock_handle_config_menu, mock_requests_post = mock_llm_deps
    mock_open_func, mock_file_handle = mock_builtins_open
    
    # Patch _get_llm_model to return a configured Gemini model
    with patch('kubelingo.kubelingo._get_llm_model', return_value=("gemini", mock_gemini_model_instance)) as mock_get_llm_model:
        mock_response = MagicMock()
        mock_response.text = "```yaml\nquestions:\n  - question: \"New Gemini Q\"\n    solution: \"New Gemini S\"\n    source: \"http://gemini.source.com\"\n```"
        mock_gemini_model_instance.generate_content.return_value = mock_response
        
        mock_yaml_safe_load.side_effect = [{'questions': [{'question': 'New Gemini Q', 'solution': 'New Gemini S', 'source': 'http://gemini.source.com'}]}, {'questions': []}]
        
        existing_question = {'question': 'Old Q', 'solution': 'Old S'}
        topic = 'test_topic'
        
        with patch('random.choice', return_value='command'): # Control question type
            new_q = generate_more_questions(topic, existing_question)
        
        mock_get_llm_model.assert_called_once()
        mock_gemini_model_instance.generate_content.assert_called_once()
        assert new_q == {'question': 'New Gemini Q', 'solution': 'New Gemini S', 'source': 'http://gemini.source.com'}
        
        mock_yaml_safe_load.assert_called_once() # Called for existing topic file
        
        captured = capsys.readouterr()
        assert "New question generated!" in captured.out


def test_generate_more_questions_openai(mock_llm_deps, mock_builtins_open, mock_yaml_safe_load, mock_yaml_dump, capsys):
    mock_gemini_configure, MockGenerativeModel_class, mock_gemini_model_instance, MockOpenAI_class, mock_openai_client_instance, mock_environ, mock_click_confirm, mock_handle_config_menu, mock_requests_post = mock_llm_deps
    mock_open_func, mock_file_handle = mock_builtins_open
    
    # Patch _get_llm_model to return a configured OpenAI model
    with patch('kubelingo.kubelingo._get_llm_model', return_value=("openai", mock_openai_client_instance)) as mock_get_llm_model:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "```yaml\nquestions:\n  - question: \"New OpenAI Q\"\n    solution: \"New OpenAI S\"\n    source: \"http://openai.source.com\"\n```"
        mock_openai_client_instance.chat.completions.create.return_value = mock_response
        
        mock_yaml_safe_load.side_effect = [{'questions': [{'question': 'New OpenAI Q', 'solution': 'New OpenAI S', 'source': 'http://openai.source.com'}]}, {'questions': []}]
        
        existing_question = {'question': 'Old Q', 'solution': 'Old S'}
        topic = 'test_topic'
        
        with patch('random.choice', return_value='manifest'): # Control question type
            new_q = generate_more_questions(topic, existing_question)
        
        mock_get_llm_model.assert_called_once()
        mock_openai_client_instance.chat.completions.create.assert_called_once()
        assert new_q == {'question': 'New OpenAI Q', 'solution': 'New OpenAI S', 'source': 'http://openai.source.com'}
        
        mock_yaml_safe_load.assert_called_once()
        
        captured = capsys.readouterr()
        assert "New question generated!" in captured.out


def test_generate_more_questions_no_llm(mock_llm_deps, capsys):
    mock_gemini_configure, MockGenerativeModel_class, mock_gemini_model_instance, MockOpenAI_class, mock_openai_client_instance, mock_environ, mock_click_confirm, mock_handle_config_menu, mock_requests_post = mock_llm_deps
    
    # Patch _get_llm_model to return no model
    with patch('kubelingo.kubelingo._get_llm_model', return_value=(None, None)) as mock_get_llm_model:
        existing_question = {'question': 'Old Q', 'solution': 'Old S'}
        topic = 'test_topic'
        
        new_q = generate_more_questions(topic, existing_question)
        
        mock_get_llm_model.assert_called_once()
        assert new_q is None
        MockGenerativeModel_class.assert_not_called()
        MockOpenAI_class.assert_not_called()
        
        captured = capsys.readouterr()
        assert "INFO: Set GEMINI_API_KEY or OPENAI_API_KEY environment variables to generate new questions." in captured.out

def test_generate_more_questions_llm_error(mock_llm_deps, capsys):
    mock_gemini_configure, MockGenerativeModel_class, mock_gemini_model_instance, MockOpenAI_class, mock_openai_client_instance, mock_environ, mock_click_confirm, mock_handle_config_menu, mock_requests_post = mock_llm_deps
    
    # Patch _get_llm_model to return a configured Gemini model
    with patch('kubelingo.kubelingo._get_llm_model', return_value=("gemini", mock_gemini_model_instance)) as mock_get_llm_model:
        mock_gemini_model_instance.generate_content.side_effect = Exception("LLM generation error")
        
        existing_question = {'question': 'Old Q', 'solution': 'Old S'}
        topic = 'test_topic'
        
        new_q = generate_more_questions(topic, existing_question)
        
        mock_get_llm_model.assert_called_once()
        mock_gemini_model_instance.generate_content.assert_called_once()
        assert new_q is None
        captured = capsys.readouterr()
        assert "Error generating question: LLM generation error" in captured.out

def test_generate_more_questions_invalid_yaml_response(mock_llm_deps, mock_builtins_open, mock_yaml_safe_load, mock_yaml_dump, capsys):
    mock_gemini_configure, MockGenerativeModel_class, mock_gemini_model_instance, MockOpenAI_class, mock_openai_client_instance, mock_environ, mock_click_confirm, mock_handle_config_menu, mock_requests_post = mock_llm_deps
    
    # Patch _get_llm_model to return a configured Gemini model
    with patch('kubelingo.kubelingo._get_llm_model', return_value=("gemini", mock_gemini_model_instance)) as mock_get_llm_model:
        mock_response = MagicMock()
        mock_response.text = "This is not valid YAML."
        mock_gemini_model_instance.generate_content.return_value = mock_response
        mock_yaml_safe_load.side_effect = yaml.YAMLError("Invalid YAML for testing") # Added line
        
        existing_question = {'question': 'Old Q', 'solution': 'Old S'}
        topic = 'test_topic'
        
        with patch('random.choice', return_value='command'):
            new_q = generate_more_questions(topic, existing_question)
        
        mock_get_llm_model.assert_called_once()
        mock_gemini_model_instance.generate_content.assert_called_once()
        assert new_q is None
        mock_yaml_safe_load.assert_called_once() # Called for parsing invalid YAML
        mock_yaml_dump.assert_not_called()
        
        captured = capsys.readouterr()
        assert "AI failed to generate a valid question. Please try again." in captured.out


class XTestKubectlValidation:
    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        # Mock tempfile.NamedTemporaryFile to control file creation
        with patch('tempfile.NamedTemporaryFile', new_callable=mock_open) as mock_tmp_file:
            self.mock_tmp_file = mock_tmp_file
            self.mock_tmp_file_handle = mock_tmp_file.return_value.__enter__.return_value
            self.mock_tmp_file_handle.name = "/tmp/mock_temp_file.yaml" # Assign a mock name

            # Mock os.unlink for temp file cleanup
            with patch('os.unlink') as mock_unlink:
                self.mock_unlink = mock_unlink
                yield

    # --- Tests for validate_manifest_with_kubectl_dry_run ---

    def test_validate_manifest_valid_yaml(self, capsys):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "pod/test-pod created (dry-run)\n"
        mock_process.stderr = ""

        with patch('subprocess.run', return_value=mock_process) as mock_subprocess_run:
            manifest = "apiVersion: v1\nkind: Pod\nmetadata:\n  name: test-pod\nspec:\n  containers:\n  - name: test-container\n    image: nginx\n"
            success, user_feedback, ai_feedback = validate_manifest_with_kubectl_dry_run(manifest)

            assert success is True
            assert "kubectl dry-run successful!" in user_feedback
            assert "pod/test-pod created (dry-run)" in ai_feedback
            mock_subprocess_run.assert_called_once()
            self.mock_tmp_file.assert_called_once_with(mode='w+', suffix=".yaml", delete=False)
            self.mock_tmp_file_handle.write.assert_called_once_with(manifest)
            self.mock_unlink.assert_called_once_with("/tmp/mock_temp_file.yaml")

    def test_validate_manifest_invalid_yaml(self, capsys):
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stdout = ""
        mock_process.stderr = "Error from server (BadRequest): error when creating \"/tmp/mock_temp_file.yaml\": Pod in version \"v1\" cannot be handled as a Pod: strict decoding error: unknown field \"invalidField\"\n"

        with patch('subprocess.run', return_value=mock_process) as mock_subprocess_run:
            manifest = "apiVersion: v1\nkind: Pod\nmetadata:\n  name: test-pod\ninvalidField: value\nspec:\n  containers:\n  - name: test-container\n    image: nginx\n"
            success, user_feedback, ai_feedback = validate_manifest_with_kubectl_dry_run(manifest)

            assert success is False
            assert "kubectl dry-run failed. Please check your manifest." in user_feedback
            assert "unknown field \"invalidField\"" in ai_feedback
            mock_subprocess_run.assert_called_once()
            self.mock_unlink.assert_called_once()

    def test_validate_manifest_not_kubernetes_yaml(self, capsys):
        manifest = "key: value\nanother_key: another_value\n"
        success, user_feedback, ai_feedback = validate_manifest_with_kubectl_dry_run(manifest)

        assert success is False
        assert "Skipping kubectl dry-run: Not a Kubernetes YAML manifest." in user_feedback
        assert "Skipped: Not a Kubernetes YAML manifest." in ai_feedback
        # Ensure subprocess.run and tempfile operations were not called
        with patch('subprocess.run') as mock_subprocess_run:
            mock_subprocess_run.assert_not_called()
        self.mock_tmp_file.assert_not_called()
        self.mock_unlink.assert_not_called()

    def test_validate_manifest_kubectl_not_found(self, capsys):
        with patch('subprocess.run', side_effect=FileNotFoundError) as mock_subprocess_run:
            manifest = "apiVersion: v1\nkind: Pod\nmetadata:\n  name: test-pod\nspec:\n  containers:\n  - name: test-container\n    image: nginx\n"
            success, user_feedback, ai_feedback = validate_manifest_with_kubectl_dry_run(manifest)

            assert success is False
            assert "Error: 'kubectl' command not found." in user_feedback
            assert "kubectl not found" in ai_feedback
            mock_subprocess_run.assert_called_once()
            self.mock_unlink.assert_called_once()

    def test_validate_manifest_with_leading_comments(self, capsys):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "pod/test-pod created (dry-run)\n"
        mock_process.stderr = ""

        with patch('subprocess.run', return_value=mock_process) as mock_subprocess_run:
            manifest = "# This is a comment\n\napiVersion: v1\nkind: Pod\nmetadata:\n  name: test-pod\nspec:\n  containers:\n  - name: test-container\n    image: nginx\n"
            success, user_feedback, ai_feedback = validate_manifest_with_kubectl_dry_run(manifest)

            assert success is True
            assert "kubectl dry-run successful!" in user_feedback
            mock_subprocess_run.assert_called_once()

    # --- Tests for validate_kubectl_command_dry_run ---

    def test_validate_kubectl_command_valid_run(self, capsys):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "apiVersion: v1\nkind: Pod\nmetadata:\n  creationTimestamp: \n  labels:\n    run: my-pod\n  name: my-pod\nspec:\n  containers:\n  - image: nginx\n    name: my-pod\n    resources: {}\nstatus: {}\n"
        mock_process.stderr = ""

        with patch('subprocess.run', return_value=mock_process) as mock_subprocess_run:
            command_string = "kubectl run my-pod --image=nginx"
            success, user_feedback, ai_feedback = validate_kubectl_command_dry_run(command_string)

            assert success is True
            assert "kubectl dry-run successful!" in user_feedback
            assert "kind: Pod" in ai_feedback
            mock_subprocess_run.assert_called_once_with(
                ["kubectl", "run", "my-pod", "--image=nginx", "--dry-run=client", "-o", "yaml"],
                capture_output=True, text=True, check=False
            )

    def test_validate_kubectl_command_invalid_run(self, capsys):
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stdout = ""
        mock_process.stderr = "Error: unknown flag: --invalid-flag\n"

        with patch('subprocess.run', return_value=mock_process) as mock_subprocess_run:
            command_string = "kubectl run my-pod --image=nginx --invalid-flag"
            success, user_feedback, ai_feedback = validate_kubectl_command_dry_run(command_string)

            assert success is False
            assert "kubectl dry-run failed. Please check your command syntax." in user_feedback
            assert "unknown flag: --invalid-flag" in ai_feedback
            mock_subprocess_run.assert_called_once()

    def test_validate_kubectl_command_skipped_get(self, capsys):
        command_string = "kubectl get pods"
        success, user_feedback, ai_feedback = validate_kubectl_command_dry_run(command_string)

        assert success is True
        assert "Skipping kubectl dry-run: Command type not typically dry-runnable client-side." in user_feedback
        assert "Skipped: Command type not typically dry-runnable client-side." in ai_feedback
        with patch('subprocess.run') as mock_subprocess_run:
            mock_subprocess_run.assert_not_called()

    def test_validate_kubectl_command_skipped_non_kubectl(self, capsys):
        command_string = "ls -l"
        success, user_feedback, ai_feedback = validate_kubectl_command_dry_run(command_string)

        assert success is True
        assert "Skipping kubectl dry-run: Command type not typically dry-runnable client-side." in user_feedback
        assert "Skipped: Command type not typically dry-runnable client-side." in ai_feedback
        with patch('subprocess.run') as mock_subprocess_run:
            mock_subprocess_run.assert_not_called()

    def test_validate_kubectl_command_kubectl_not_found(self, capsys):
        with patch('subprocess.run', side_effect=FileNotFoundError) as mock_subprocess_run:
            command_string = "kubectl run my-pod --image=nginx"
            success, user_feedback, ai_feedback = validate_kubectl_command_dry_run(command_string)

            assert success is False
            assert "Error: 'kubectl' command not found." in user_feedback
            assert "kubectl not found" in ai_feedback
            mock_subprocess_run.assert_called_once()

    def test_validate_kubectl_command_already_has_dry_run_and_output(self, capsys):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "apiVersion: v1\nkind: Pod\nmetadata:\n  name: my-pod\nspec:\n  containers:\n  - image: nginx\n    name: my-pod\n"
        mock_process.stderr = ""

        with patch('subprocess.run', return_value=mock_process) as mock_subprocess_run:
            command_string = "kubectl run my-pod --image=nginx --dry-run=client -o json"
            success, user_feedback, ai_feedback = validate_kubectl_command_dry_run(command_string)

            assert success is True
            assert "kubectl dry-run successful!" in user_feedback
            assert "kind: Pod" in ai_feedback
            mock_subprocess_run.assert_called_once_with(
                ["kubectl", "run", "my-pod", "--image=nginx", "--dry-run=client", "-o", "json"],
                capture_output=True, text=True, check=False
            )

# def test_run_topic_vim_no_solution(capsys):
#     with patch('kubelingo.kubelingo.handle_vim_edit', return_value=(None, "This question does not have a solution to validate against for vim edit.", False)) as mock_handle_vim_edit:
#         # Simulate 'vim' for the first question, then 'done' for the second question
#         with patch('kubelingo.kubelingo.get_user_input', side_effect=[([], 'vim'), (['done'], None)]):
#             # Provide two questions: first without solution, second a dummy
#             mock_questions = [{
#                 'question': 'Test Q without solution',
#                 'starter_manifest': "apiVersion: v1\nkind: Pod\nmetadata:\n  name: test-pod\nspec:\n  containers:\n  - name: my-container\n    image: nginx\n",
#                 'suggestion': []
#             }, {'question': 'Second dummy question'}]
#             with patch('kubelingo.kubelingo.load_questions', return_value={'questions': mock_questions}):
#                 with patch('kubelingo.kubelingo.clear_screen'):
#                     # Simulate 'n' to advance past post-question menus twice
#                     with patch('builtins.input', side_effect=['n', 'n']):
#                         from kubelingo.kubelingo import run_topic
#                         # Call run_topic with a dummy topic, starting at index 0, with performance data and questions
#                         run_topic('dummy_topic', 0, {}, mock_questions)
                        
#                         captured = capsys.readouterr()
#                         # Assert that handle_vim_edit was called and printed its message
#                         assert "This question does not have a solution to validate against for vim edit." in captured.out
#                         assert "TypeError" not in captured.err # Ensure no TypeError
#                         mock_handle_vim_edit.assert_called_once()
#                         # Assert that the "Great job!" message is printed after the second question
#                         assert "Great job! You've completed all questions for this topic." in captured.out
