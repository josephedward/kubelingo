import pytest
import os
import yaml
from unittest.mock import patch, mock_open, MagicMock, call
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
    handle_config_menu,
    get_user_input,
    USER_DATA_DIR,
    MISSED_QUESTIONS_FILE,
    PERFORMANCE_FILE,
    ISSUES_FILE
)

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
    mock_open_func.assert_called_once_with(PERFORMANCE_FILE, 'r')

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
    mock_open_func.assert_called_once_with(PERFORMANCE_FILE, 'r')

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
    (["kubectl run my-pod --port=80 --image=nginx"], ["kubectl run my-pod --image=nginx --port=80"] # Flag sorting
    ),(["kubectl create deployment my-app --image=my-image -n default"], ["kubectl create deployment my-app --image=my-image --namespace default"]),
    (["helm install my-release stable/chart -f values.yaml"], ["helm install my-release stable/chart -f values.yaml"]),
    ([""], [""] # Empty command
    ),(["  kubectl   get   pods  "], ["kubectl get pod"] # Extra spaces
    ),(["kubectl get svc -o wide"], ["kubectl get service -o wide"] # Short flag with value
    ),(["kubectl get svc -A"], ["kubectl get service -A"] # Short flag without value
    ),(["kubectl get all -n kube-system"], ["kubectl get all --namespace kube-system"] # 'all' is not an alias, should remain
    ),(["kubectl get pod my-pod -o yaml --namespace test"], ["kubectl get pod my-pod --namespace test -o yaml"] # Positional args before flags
    ),(["kubectl get pod my-pod --namespace test -o yaml"], ["kubectl get pod my-pod --namespace test -o yaml"])
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
    
    mock_exists.assert_called_once_with(f"questions/{topic}.yaml")
    mock_load.assert_not_called()
    mock_dump.assert_not_called()
    mock_open_func.assert_not_called()
    
    captured = capsys.readouterr()
    assert f"Error: Topic file not found at questions/{topic}.yaml. Cannot update source." in captured.out

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
    
    mock_exists.assert_called_once_with(f"questions/{topic}.yaml")
    mock_load.assert_called_once_with(mock_file_handle)
    
    expected_data = {
        'questions': [
            {'question': 'Q1', 'solution': 'A', 'source': 'new_source'},
            {'question': 'Q2', 'solution': 'B'}
        ]
    }
    mock_dump.assert_called_once_with(expected_data, mock_file_handle)
    mock_open_func.assert_called_once_with(f"questions/{topic}.yaml", 'r+')
    
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
    
    mock_exists.assert_called_once_with(f"questions/{topic}.yaml")
    mock_load.assert_called_once_with(mock_file_handle)
    mock_dump.assert_not_called() # Should not dump if question not found
    mock_open_func.assert_called_once_with(f"questions/{topic}.yaml", 'r+')
    
    captured = capsys.readouterr()
    assert f"Warning: Question 'Non-existent Q' not found in {topic}.yaml. Source not updated." in captured.out

def test_update_question_source_in_yaml_empty_file(mock_topic_file, capsys):
    mock_exists, mock_load, mock_dump, mock_open_func, mock_file_handle = mock_topic_file
    mock_exists.return_value = True
    mock_load.return_value = None # Empty YAML file
    
    topic = 'test_topic'
    updated_question = {'question': 'Q1', 'source': 'new_source'}
    
    update_question_source_in_yaml(topic, updated_question)
    
    mock_exists.assert_called_once_with(f"questions/{topic}.yaml")
    mock_load.assert_called_once_with(mock_file_handle)
    mock_dump.assert_not_called() # Should not dump if question not found in empty file
    mock_open_func.assert_called_once_with(f"questions/{topic}.yaml", 'r+')
    
    captured = capsys.readouterr()
    assert f"Warning: Question 'Q1' not found in {topic}.yaml. Source not updated." in captured.out

# --- Tests for create_issue ---

@pytest.fixture
def mock_create_issue_deps(mock_os_path_exists, mock_yaml_safe_load, mock_yaml_dump, mock_builtins_open):
    with patch('kubelingo.kubelingo.remove_question_from_list') as mock_remove_question_from_list,
         patch('time.asctime', return_value='mock_timestamp'):
        yield mock_os_path_exists, mock_yaml_safe_load, mock_yaml_dump, mock_builtins_open[0], mock_builtins_open[1], mock_remove_question_from_list

def test_create_issue_valid_input(mock_create_issue_deps, capsys):
    mock_exists, mock_load, mock_dump, mock_open_func, mock_file_handle, mock_remove_question_from_list = mock_create_issue_deps
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
    mock_exists, mock_load, mock_dump, mock_open_func, mock_file_handle, mock_remove_question_from_list = mock_create_issue_deps
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
    mock_exists, mock_load, mock_dump, mock_open_func, mock_file_handle, mock_remove_question_from_list = mock_create_issue_deps
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
    mock_exists.assert_called_once_with(f"questions/{topic}.yaml")
    mock_load.assert_not_called()
    mock_open_func.assert_not_called()
    
    captured = capsys.readouterr()
    assert f"Error: Question file not found at questions/{topic}.yaml" in captured.out
    assert "Available topics: topic1, topic2" in captured.out

def test_load_questions_file_found(mock_load_questions_deps):
    mock_exists, mock_load, mock_open_func, mock_file_handle = mock_load_questions_deps
    mock_exists.return_value = True
    expected_data = {'questions': [{'question': 'Q1'}]}
    mock_load.return_value = expected_data
    
    topic = 'existing_topic'
    result = load_questions(topic)
    
    assert result == expected_data
    mock_exists.assert_called_once_with(f"questions/{topic}.yaml")
    mock_load.assert_called_once_with(mock_file_handle)
    mock_open_func.assert_called_once_with(f"questions/{topic}.yaml", 'r')

# --- Tests for handle_config_menu ---

@pytest.fixture
def mock_handle_config_menu_deps():
    with patch('kubelingo.kubelingo.clear_screen') as mock_clear_screen,
         patch('dotenv.dotenv_values', return_value={}) as mock_dotenv_values,
         patch('dotenv.set_key') as mock_set_key,
         patch('os.environ') as mock_environ,
         patch('time.sleep') as mock_sleep:
        yield mock_clear_screen, mock_dotenv_values, mock_set_key, mock_environ, mock_sleep

def test_handle_config_menu_set_gemini_key(mock_handle_config_menu_deps, capsys):
    mock_clear_screen, mock_dotenv_values, mock_set_key, mock_environ, mock_sleep = mock_handle_config_menu_deps
    mock_dotenv_values.return_value = {"GEMINI_API_KEY": "Not Set", "OPENAI_API_KEY": "Not Set"}
    
    # Simulate user input: 1 (set Gemini), then a key, then 3 (back to main menu)
    with patch('builtins.input', side_effect=['1', 'test_gemini_key', '3']):
        handle_config_menu()
    
    mock_clear_screen.assert_called() # Called multiple times in the loop
    mock_dotenv_values.assert_called() # Called multiple times in the loop
    mock_set_key.assert_called_once_with(".env", "GEMINI_API_KEY", 'test_gemini_key')
    assert mock_environ.get("GEMINI_API_KEY") == 'test_gemini_key' # Check if os.environ was updated
    mock_sleep.assert_called() # Called after each action
    
    captured = capsys.readouterr()
    assert "Set Gemini API Key" in captured.out
    assert "Gemini API Key saved." in captured.out

def test_handle_config_menu_set_openai_key(mock_handle_config_menu_deps, capsys):
    mock_clear_screen, mock_dotenv_values, mock_set_key, mock_environ, mock_sleep = mock_handle_config_menu_deps
    mock_dotenv_values.return_value = {"GEMINI_API_KEY": "Not Set", "OPENAI_API_KEY": "Not Set"}
    
    # Simulate user input: 2 (set OpenAI), then a key, then 3 (back to main menu)
    with patch('builtins.input', side_effect=['2', 'test_openai_key', '3']):
        handle_config_menu()
    
    mock_clear_screen.assert_called()
    mock_dotenv_values.assert_called()
    mock_set_key.assert_called_once_with(".env", "OPENAI_API_KEY", 'test_openai_key')
    assert mock_environ.get("OPENAI_API_KEY") == 'test_openai_key'
    mock_sleep.assert_called() 
    
    captured = capsys.readouterr()
    assert "Set OpenAI API Key" in captured.out
    assert "OpenAI API Key saved." in captured.out

def test_handle_config_menu_invalid_choice(mock_handle_config_menu_deps, capsys):
    mock_clear_screen, mock_dotenv_values, mock_set_key, mock_environ, mock_sleep = mock_handle_config_menu_deps
    mock_dotenv_values.return_value = {"GEMINI_API_KEY": "Not Set", "OPENAI_API_KEY": "Not Set"}
    
    # Simulate user input: invalid, then 3 (back to main menu)
    with patch('builtins.input', side_effect=['invalid', '3']):
        handle_config_menu()
    
    mock_clear_screen.assert_called()
    mock_dotenv_values.assert_called()
    mock_set_key.assert_not_called()
    mock_sleep.assert_called()
    
    captured = capsys.readouterr()
    assert "Invalid choice. Please try again." in captured.out

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