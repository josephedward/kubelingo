import pytest
from unittest.mock import MagicMock, patch, call

import os
import yaml
import pytest
import random

# Changed import
import kubelingo.question_generator as qg
from kubelingo.kubelingo import _get_llm_model, QUESTIONS_DIR, load_questions, get_normalized_question_text, manifests_equivalent, USER_DATA_DIR, MISSED_QUESTIONS_FILE, save_question_to_list, remove_question_from_list, load_questions_from_list # Added save_question_to_list, remove_question_from_list, load_questions_from_list



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
    expected_questions = {'question': 'Q1'}
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


@pytest.fixture
def mock_yaml_safe_load():
    with patch('kubelingo.question_generator.yaml.safe_load') as mock_load:
        yield mock_load

@pytest.fixture
def mock_yaml_dump():
    with patch('kubelingo.question_generator.yaml.dump') as mock_dump:
        yield mock_dump

@pytest.fixture
def mock_llm_response():
    """Mocks the LLM response for generate_more_questions."""
    with patch('kubelingo.question_generator._get_llm_model') as mock_get_llm_model:
        mock_model = MagicMock()
        mock_get_llm_model.return_value = ('gemini', mock_model)
        mock_model.generate_content.return_value.text = '''
questions:
  - question: "Create a Deployment named 'my-app' with 3 replicas using the nginx image."
    solution: |
      apiVersion: apps/v1
      kind: Deployment
      metadata:
        name: my-app
      spec:
        replicas: 3
        selector:
          matchLabels:
            app: my-app
        template:
          metadata:
            labels:
              app: my-app
          spec:
            containers:
            - name: nginx
              image: nginx
    source: "https://kubernetes.io/docs/concepts/workloads/controllers/deployment/"
    rationale: "Tests basic Deployment creation and scaling."
'''
        yield

@pytest.fixture
def mock_load_questions():
    """Mocks load_questions to return a predefined set of existing questions."""
    with patch('kubelingo.question_generator.load_questions') as mock_load:
        mock_load.return_value = {
            'questions': [
                {'question': 'Existing Q1', 'solution': 'sol1', 'source': 'src1'},
                {'question': 'Existing Q2', 'solution': 'sol2', 'source': 'src2'}
            ]
        }
        yield

@pytest.fixture
def mock_load_questions_with_duplicate():
    """Mocks load_questions to include a question that will be a duplicate of the generated one."""
    with patch('kubelingo.question_generator.load_questions') as mock_load:
        mock_load.return_value = {
            'questions': [
                {'question': 'Existing Q1', 'solution': 'sol1', 'source': 'src1'},
                {"question": "Create a Deployment named 'my-app' with 3 replicas using the nginx image.", "solution": "sol_dup", "source": "src_dup"}
            ]
        }
        yield

def test_generate_more_questions_success(mock_llm_response, mock_load_questions):
    topic = "Deployments"
    question = {'question': 'Example Q', 'solution': 'example sol'}
    new_q = qg.generate_more_questions(topic, question)

    assert new_q is not None
    assert new_q['question'] == "Create a Deployment named 'my-app' with 3 replicas using the nginx image."
    assert 'solution' in new_q
    assert isinstance(new_q['solution'], str)
    assert new_q['source'] == "https://kubernetes.io/docs/concepts/workloads/controllers/deployment/"
    assert new_q['rationale'] == "Tests basic Deployment creation and scaling."

def test_generate_more_questions_no_llm_model():
    with patch('kubelingo.question_generator._get_llm_model') as mock_get_llm_model:
        mock_get_llm_model.return_value = (None, None)
        topic = "Deployments"
        question = {'question': 'Example Q', 'solution': 'example sol'}
        new_q = qg.generate_more_questions(topic, question)
        assert new_q is None

def test_generate_more_questions_invalid_yaml_from_llm(mock_load_questions):
    with patch('kubelingo.question_generator._get_llm_model') as mock_get_llm_model:
        mock_model = MagicMock()
        mock_get_llm_model.return_value = ('gemini', mock_model)
        mock_model.generate_content.return_value.text = 'This is not valid YAML'
        topic = "Deployments"
        question = {'question': 'Example Q', 'solution': 'example sol'}
        new_q = qg.generate_more_questions(topic, question)
        assert new_q is None

def test_generate_more_questions_missing_source(mock_load_questions, mock_googlesearch):
    mock_googlesearch.return_value = ['http://found-source.com']
    with patch('kubelingo.question_generator._get_llm_model') as mock_get_llm_model:
        mock_model = MagicMock()
        mock_get_llm_model.return_value = ('gemini', mock_model)
        mock_model.generate_content.return_value.text = '''
questions:
  - question: "Question without source"
    solution: "some solution"
    rationale: "some rationale"
'''
        topic = "Deployments"
        question = {'question': 'Example Q', 'solution': 'example sol'}
        new_q = qg.generate_more_questions(topic, question)
        assert new_q is not None
        assert 'source' in new_q
        assert new_q['source'] == 'http://found-source.com' # Assuming assign_source finds this

def test_generate_more_questions_duplicate_detected(mock_llm_response, mock_load_questions_with_duplicate):
    topic = "Deployments"
    question = {'question': 'Example Q', 'solution': 'example sol'}
    new_q = qg.generate_more_questions(topic, question)
    assert new_q is None # Expect None because a duplicate was detected

# --- Tests for assign_source function ---

@pytest.fixture
def mock_googlesearch():
    with patch('kubelingo.question_generator.search') as mock_search:
        yield mock_search

# Define mock objects for Fore and Style
class MockFore:
    YELLOW = ""
    RED = ""
    GREEN = ""

class MockStyle:
    RESET_ALL = ""

def test_assign_source_already_has_source(mock_googlesearch):
    question = {'question': 'Test Q', 'source': 'http://example.com'}
    topic = 'test_topic'
    mock_fore = MockFore()
    mock_style = MockStyle()
    mock_genai = MagicMock()
    assigned = qg.assign_source(question, topic, mock_fore, mock_style)
    assert not assigned
    assert question['source'] == 'http://example.com'
    mock_googlesearch.assert_not_called()

def test_assign_source_finds_source(mock_googlesearch):
    mock_googlesearch.return_value = ['http://found-source.com']
    question = {'question': 'Test Q'}
    topic = 'test_topic'
    mock_fore = MockFore()
    mock_style = MockStyle()
    mock_genai = MagicMock()
    assigned = qg.assign_source(question, topic, mock_fore, mock_style)
    assert assigned
    assert question['source'] == 'http://found-source.com'
    mock_googlesearch.assert_called_once_with('kubernetes Test Q', num_results=1)

def test_assign_source_no_source_found(mock_googlesearch):
    mock_googlesearch.return_value = []
    question = {'question': 'Test Q'}
    topic = 'test_topic'
    mock_fore = MockFore()
    mock_style = MockStyle()
    mock_genai = MagicMock()
    assigned = qg.assign_source(question, topic, mock_fore, mock_style)
    assert not assigned
    assert 'source' not in question
    mock_googlesearch.assert_called_once_with('kubernetes Test Q', num_results=1)

def test_assign_source_search_error(mock_googlesearch):
    mock_googlesearch.side_effect = Exception("Network error")
    question = {'question': 'Test Q'}
    topic = 'test_topic'
    with patch('kubelingo.question_generator._get_llm_model') as mock_get_llm_model:
        mock_get_llm_model.return_value = (None, None)
        with patch('builtins.print') as mock_print:
            assigned = qg.assign_source(question, topic, MockFore(), MockStyle())
            assert not assigned
            assert 'source' not in question
            mock_googlesearch.assert_called_once_with('kubernetes Test Q', num_results=1)
            mock_print.assert_called_once_with("Note: Could not find source for a question (AI disabled or search error: Network error).")

def test_assign_source_ai_disabled_no_search_results(mock_googlesearch, capsys):
    mock_googlesearch.return_value = []
    question = {'question': 'Test Q'}
    topic = 'test_topic'
    mock_fore = MockFore()
    mock_style = MockStyle()
    mock_genai = MagicMock()
    assigned = qg.assign_source(question, topic, mock_fore, mock_style)
    assert not assigned
    assert 'source' not in question
    mock_googlesearch.assert_called_once_with('kubernetes Test Q', num_results=1)
    captured = capsys.readouterr()
    assert "Note: Could not find source for a question (AI disabled or search error: Network error)." not in captured.out # No error message for no results

def test_assign_source_ai_disabled_search_error_patched_print(mock_googlesearch):
    mock_googlesearch.side_effect = Exception("Network error")
    question = {'question': 'Test Q'}
    topic = 'test_topic'
    with patch('kubelingo.question_generator._get_llm_model') as mock_get_llm_model:
        mock_get_llm_model.return_value = (None, None)
        with patch('builtins.print') as mock_print:
            assigned = qg.assign_source(question, topic, MockFore(), MockStyle())
            assert not assigned
            assert 'source' not in question
            mock_googlesearch.assert_called_once_with('kubernetes Test Q', num_results=1)
            mock_print.assert_called_once_with("Note: Could not find source for a question (AI disabled or search error: Network error).")

def test_assign_source_ai_disabled_googlesearch_not_installed_patched_print():
    with patch('kubelingo.question_generator.search', None): # Simulate googlesearch not installed
        question = {'question': 'Test Q'}
        topic = 'test_topic'
        with patch('kubelingo.question_generator._get_llm_model') as mock_get_llm_model:
            mock_get_llm_model.return_value = (None, None)
            with patch('builtins.print') as mock_print:
                assigned = qg.assign_source(question, topic, MockFore(), MockStyle())
                assert not assigned
                assert 'source' not in question
                mock_print.assert_called_once_with("Note: Could not find source for a question (googlesearch not installed and AI disabled).")

@pytest.fixture
def mock_llm_model_gemini():
    with patch('kubelingo.question_generator._get_llm_model') as mock_get_llm_model:
        mock_model = MagicMock()
        mock_get_llm_model.return_value = ('gemini', mock_model)
        mock_model.generate_content.return_value.text = '''
questions:
  - question: "New Gemini Q"
    solution: "New Gemini S"
    source: "http://gemini.source.com"
'''
        yield mock_model

@pytest.fixture
def mock_llm_model_openai():
    with patch('kubelingo.question_generator._get_llm_model') as mock_get_llm_model:
        mock_model = MagicMock()
        mock_get_llm_model.return_value = ('openai', mock_model)
        mock_model.chat.completions.create.return_value.choices[0].message.content = '''
questions:
  - question: "New OpenAI Q"
    solution: "New OpenAI S"
    source: "http://openai.source.com"
'''
        yield mock_model

@pytest.fixture
def mock_llm_model_no_llm():
    with patch('kubelingo.question_generator._get_llm_model') as mock_get_llm_model:
        mock_get_llm_model.return_value = (None, None)
        yield

@pytest.fixture
def mock_llm_model_error():
    with patch('kubelingo.question_generator._get_llm_model') as mock_get_llm_model:
        mock_model = MagicMock()
        mock_get_llm_model.return_value = ('gemini', mock_model)
        mock_model.generate_content.side_effect = Exception("LLM generation error")
        yield

@pytest.fixture
def mock_llm_model_invalid_yaml():
    with patch('kubelingo.question_generator._get_llm_model') as mock_get_llm_model:
        mock_model = MagicMock()
        mock_get_llm_model.return_value = ('gemini', mock_model)
        mock_model.generate_content.return_value.text = 'This is not valid YAML.'
        yield

def test_generate_more_questions_gemini(mock_llm_model_gemini, mock_load_questions, mock_yaml_dump, capsys):
    # mock_yaml_safe_load.side_effect = [{'questions': [{'question': 'New Gemini Q', 'solution': 'New Gemini S', 'source': 'http://gemini.source.com'}]}, {'questions': []}]
    # The above line is problematic because it causes the mock to be called multiple times.
    # Instead, we should mock the behavior of load_questions directly if it's called internally.
    # For this test, we assume load_questions is mocked by mock_load_questions fixture.

    existing_question = {'question': 'Old Q', 'solution': 'Old S'}
    topic = 'test_topic'
    
    with patch('random.choice', return_value='command'): # Control question type
        new_q = qg.generate_more_questions(topic, existing_question)
    
    mock_llm_model_gemini.generate_content.assert_called_once()
    assert new_q == {'question': 'New Gemini Q', 'solution': 'New Gemini S', 'source': 'http://gemini.source.com'}
    
    captured = capsys.readouterr()
    assert "New question generated!" in captured.out

def test_generate_more_questions_openai(mock_llm_model_openai, mock_load_questions, mock_yaml_dump, capsys):
    existing_question = {'question': 'Old Q', 'solution': 'Old S'}
    topic = 'test_topic'
    
    with patch('random.choice', return_value='manifest'): # Control question type
        new_q = qg.generate_more_questions(topic, existing_question)
    
    mock_llm_model_openai.chat.completions.create.assert_called_once()
    assert new_q == {'question': 'New OpenAI Q', 'solution': 'New OpenAI S', 'source': 'http://openai.source.com'}
    
    captured = capsys.readouterr()
    assert "New question generated!" in captured.out

def test_generate_more_questions_no_llm(mock_llm_model_no_llm, capsys):
    existing_question = {'question': 'Old Q', 'solution': 'Old S'}
    topic = 'test_topic'
    
    new_q = qg.generate_more_questions(topic, existing_question)
    
    assert new_q is None
    captured = capsys.readouterr()
    assert "INFO: Set GEMINI_API_KEY or OPENAI_API_KEY environment variables to generate new questions." in captured.out

def test_generate_more_questions_llm_error(mock_llm_model_error, capsys):
    existing_question = {'question': 'Old Q', 'solution': 'Old S'}
    topic = 'test_topic'
    
    new_q = qg.generate_more_questions(topic, existing_question)
    
    assert new_q is None
    captured = capsys.readouterr()
    assert "Error generating question: LLM generation error" in captured.out

def test_generate_more_questions_invalid_yaml_response(mock_llm_model_invalid_yaml, mock_load_questions, mock_yaml_safe_load, mock_yaml_dump, capsys):
    mock_yaml_safe_load.side_effect = yaml.YAMLError("Invalid YAML for testing") # Added line
    
    existing_question = {'question': 'Old Q', 'solution': 'Old S'}
    topic = 'test_topic'
    
    with patch('random.choice', return_value='command'):
        new_q = qg.generate_more_questions(topic, existing_question)
    
    assert new_q is None
    captured = capsys.readouterr()
    assert "AI failed to generate a valid question (invalid YAML). Please try again." in captured.out

# Tests from test_questions_schema.py
def test_all_questions_have_required_keys():
    # Use QUESTIONS_DIR from kubelingo.kubelingo
    # questions_dir = os.path.join(os.path.dirname(__file__), '..', 'questions') # Alternative if QUESTIONS_DIR not available
    
    # Ensure the directory exists, though it should for tests
    os.makedirs(QUESTIONS_DIR, exist_ok=True) 
    
    for filename in os.listdir(QUESTIONS_DIR):
        if filename.endswith('.yaml'):
            filepath = os.path.join(QUESTIONS_DIR, filename)
            with open(filepath, 'r') as f:
                if os.path.getsize(filepath) == 0:
                    continue
                data = yaml.safe_load(f)
                if not data or 'questions' not in data:
                    continue

                assert 'questions' in data, f"File {filename} is missing 'questions' key"
                
                for i, q in enumerate(data['questions']):
                    assert 'question' in q, f"'question' key is missing in {q} in file {filename}, question index {i+1}"

# Tests from test_manifest_equivalence.py
def test_block_vs_inline_pod_manifest_equivalence_correct():
    block_yaml = '''
apiVersion: v1
kind: Pod
metadata:
  name: cmd-args
spec:
  containers:
  - name: c
    image: busybox
    command:
    - sh
    - -c
    args:
    - echo hello && sleep 3600
'''
    inline_yaml = '''
apiVersion: v1
kind: Pod
metadata:
  name: different-name
spec:
  containers:
  - name: busybox-container
    image: busybox
    command: ["sh", "-c"]
    args: ["echo hello && sleep 3600"]
'''
    sol_obj = yaml.safe_load(block_yaml)
    user_obj = yaml.safe_load(inline_yaml)
    assert manifests_equivalent(sol_obj, user_obj)

@pytest.mark.parametrize("user_name", ["my-pod", "cmd-args", None])
def test_metadata_name_ignored(user_name):
    sol_yaml = '''
apiVersion: v1
kind: Pod
metadata:
  name: cmd-args
spec:
  containers:
  - name: c
    image: busybox
'''
    sol_obj = yaml.safe_load(sol_yaml)
    user_obj = yaml.safe_load(sol_yaml)
    # Change metadata.name if provided
    if user_name is not None:
        user_obj['metadata']['name'] = user_name
    else:
        # Remove metadata.name entirely
        user_obj['metadata'].pop('name', None)
    assert manifests_equivalent(sol_obj, user_obj)

def test_image_difference_not_equivalent():
    sol_yaml = '''
apiVersion: v1
kind: Pod
metadata:
  name: test-pod
spec:
  containers:
  - name: c
    image: busybox
'''
    user_yaml = '''
apiVersion: v1
kind: Pod
metadata:
  name: test-pod
spec:
  containers:
  - name: c
    image: nginx
'''
    sol_obj = yaml.safe_load(sol_yaml)
    user_obj = yaml.safe_load(user_yaml)
    assert not manifests_equivalent(sol_obj, user_obj)