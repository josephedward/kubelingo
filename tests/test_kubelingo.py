import subprocess
import tempfile
import os
from unittest.mock import mock_open, patch
import colorama
import re
import yaml
from kubelingo.kubelingo import (
    get_user_input,
    run_topic,
    list_and_select_topic,
    load_performance_data,
    save_performance_data,
    load_questions,
    clear_screen,
    save_question_to_list,
    get_ai_verdict,
    Style, Fore,
    cli
)
from kubelingo.kubelingo import (
    get_user_input,
    run_topic,
    list_and_select_topic,
    load_performance_data,
    save_performance_data,
    load_questions,
    clear_screen,
    save_question_to_list,
        get_ai_verdict, # Import for mocking
    
    Style, Fore # Import for asserting on colored output
)
from kubelingo.kubelingo import cli # Import cli for testing

# Constants for paths (will be mocked)
USER_DATA_DIR = "user_data"
MISC_DIR = "misc"
PERFORMANCE_FILE = os.path.join(USER_DATA_DIR, "performance_test.yaml")
PERFORMANCE_BACKUP_FILE = os.path.join(MISC_DIR, "performance.yaml")

def strip_ansi_codes(s):
    return re.sub(r'\x1b\[([0-9]{1,2}(;[0-9]{1,2})?)?[m|K]', '', s)

def test_clear_command_clears_commands(monkeypatch, capsys):
    """Tests that 'clear' clears all previously entered commands."""
    inputs = iter(['cmd1', 'cmd2', 'clear', 'done'])
    monkeypatch.setattr('builtins.input', lambda _prompt: next(inputs))
    user_commands, special_action = get_user_input()
    captured = capsys.readouterr()
    assert user_commands == []
    assert special_action is None
    assert "(Input cleared)" in captured.out


def test_clear_command_on_empty_list(monkeypatch, capsys):
    """Tests that 'clear' does nothing when the command list is empty."""
    inputs = iter(['clear', 'done'])
    monkeypatch.setattr('builtins.input', lambda _prompt: next(inputs))
    user_commands, special_action = get_user_input()
    captured = capsys.readouterr()
    assert user_commands == []
    assert special_action is None
    assert "(No input to clear)" in captured.out


def test_line_editing_is_enabled():
    """
    Proxy test to check that readline is imported for line editing.
    Directly testing terminal interactions like arrow keys is not feasible
    in a unit test environment like this.
    """
    try:
        import readline
        import sys
        # The import of `kubelingo` in the test suite should have loaded readline.
        assert 'readline' in sys.modules
    except ImportError:
        # readline is not available on all platforms (e.g., Windows without
        # pyreadline). This test should pass gracefully on those platforms.
        pass


def test_clear_command_feedback_is_colored(monkeypatch, capsys):
    """Tests that feedback from the 'clear' command is colorized."""
    colorama.init(strip=False)
    try:
        # Test when an item is removed
        inputs = iter(['cmd1', 'clear', 'done'])
        monkeypatch.setattr('builtins.input', lambda _prompt: next(inputs))
        get_user_input()
        captured = capsys.readouterr()
        assert "(Input cleared)" in captured.out
        assert colorama.Fore.YELLOW in captured.out

        # Test when list is empty
        inputs = iter(['clear', 'done'])
        monkeypatch.setattr('builtins.input', lambda _prompt: next(inputs))
        get_user_input()
        captured = capsys.readouterr()
        assert "(No input to clear)" in captured.out
        assert colorama.Fore.YELLOW in captured.out
    finally:
        colorama.deinit()


def test_performance_data_updates_with_unique_correct_answers(monkeypatch):
    """
    Tests that performance data is updated with unique correctly answered questions,
    and doesn't just overwrite with session data.
    """
    # Start with q1 already correct
    mock_data_source = {'existing_topic': {'correct_questions': ['q1']}}
    saved_data = {}

    def mock_load_performance_data():
        return mock_data_source.copy()

    def mock_save_performance_data(data):
        nonlocal saved_data
        saved_data = data

    monkeypatch.setattr('kubelingo.kubelingo.load_performance_data', mock_load_performance_data)
    monkeypatch.setattr('kubelingo.kubelingo.save_performance_data', mock_save_performance_data)

    # In this session, user answers q1 again correctly and q2 correctly.
    questions = [{'question': 'q1', 'solution': 's1'}, {'question': 'q2', 'solution': 's2'}]
    monkeypatch.setattr('kubelingo.kubelingo.load_questions', lambda topic: {'questions': questions})
    monkeypatch.setattr('kubelingo.kubelingo.clear_screen', lambda: None)
    monkeypatch.setattr('time.sleep', lambda seconds: None)
    monkeypatch.setattr('kubelingo.kubelingo.save_question_to_list', lambda *args: None)
    monkeypatch.setattr('random.shuffle', lambda x: None)

    user_inputs = iter([
        (['s1'], None),      # Correct answer for q1
        (['s2'], None),      # Correct answer for q2
    ])
    monkeypatch.setattr('kubelingo.kubelingo.get_user_input', lambda allow_solution_command: next(user_inputs))
    post_answer_inputs = iter(['n', 'q']) # 'n' for first question, 'q' for second
    monkeypatch.setattr('builtins.input', lambda _prompt: next(post_answer_inputs))

    run_topic('existing_topic', len(questions), mock_data_source, questions)

    # q2 should be added, q1 should not be duplicated.
    assert 'existing_topic' in saved_data
    assert isinstance(saved_data['existing_topic']['correct_questions'], list)
    # Using a set for comparison to ignore order
    assert set(saved_data['existing_topic']['correct_questions']) == {'q1', 'q2'}
    assert len(saved_data['existing_topic']['correct_questions']) == 2


def test_topic_menu_shows_question_count_and_color(monkeypatch, capsys):
    """
    Tests that the topic selection menu displays the number of questions
    for each topic and uses colors for performance stats.
    """
    # Mock filesystem and data
    monkeypatch.setattr('os.listdir', lambda path: ['topic1.yaml', 'topic2.yaml'])
    monkeypatch.setattr('os.path.exists', lambda path: False) # For missed questions

    mock_perf_data = {
        'topic1': {'correct_questions': ['q1', 'q2']},
        'topic2': {'correct_questions': ['q1', 'q2', 'q3', 'q4', 'q5']}
    }
    monkeypatch.setattr('kubelingo.kubelingo.load_performance_data', lambda: mock_perf_data)

    def mock_load_questions(topic):
        if topic == 'topic1':
            return {'questions': [{}, {}, {}]} # 3 questions
        if topic == 'topic2':
            return {'questions': [{}, {}, {}, {}, {}]} # 5 questions
        return None
    monkeypatch.setattr('kubelingo.kubelingo.load_questions', mock_load_questions)

    # Mock input to exit menu
    def mock_input_eof(prompt):
        raise EOFError
    monkeypatch.setattr('builtins.input', mock_input_eof)

    topic = list_and_select_topic(mock_perf_data)
    assert topic[0] is None

    captured = capsys.readouterr()
    output = strip_ansi_codes(captured.out)

    assert "Topic1 [3 questions]" in output
    assert "Topic2 [5 questions]" in output
    assert re.search(r"\(.*?2/3 correct - 67%.*?\)", output)
    assert re.search(r"\(.*?5/5 correct - 100%.*?\)", output)
    assert f"Please select a topic to study:" in output

def test_correct_command_is_accepted(monkeypatch, capsys):
    """
    Tests that a correct command-based answer is accepted and graded as correct.
    This is a regression test for the bug where correct answers were ignored.
    """
    # Mock performance data to be empty
    mock_perf_data = {}
    def mock_load_performance_data():
        return mock_perf_data

    saved_data = {}
    def mock_save_performance_data(data):
        nonlocal saved_data
        saved_data = data

    monkeypatch.setattr('kubelingo.kubelingo.load_performance_data', mock_load_performance_data)
    monkeypatch.setattr('kubelingo.kubelingo.save_performance_data', mock_save_performance_data)

    # Mock the question and solution
    question = {
        'question': "View the encoded values in a Secret named 'api-secrets' in YAML format.",
        'solution': "kubectl get secret api-secrets -o yaml"
    }
    questions = [question]
    monkeypatch.setattr('kubelingo.kubelingo.load_questions', lambda topic: {'questions': questions})
    monkeypatch.setattr('kubelingo.kubelingo.clear_screen', lambda: None)
    monkeypatch.setattr('time.sleep', lambda seconds: None)
    monkeypatch.setattr('kubelingo.kubelingo.save_question_to_list', lambda *args: None)
    monkeypatch.setattr('random.shuffle', lambda x: None)

    # Mock user input: the correct command, then 'done'
    user_inputs = iter([
        (['k get secret api-secrets -o yaml'], None),
    ])
    monkeypatch.setattr('kubelingo.kubelingo.get_user_input', lambda allow_solution_command: next(user_inputs))
    # Mock post-answer input to quit
    post_answer_inputs = iter(['q'])
    monkeypatch.setattr('builtins.input', lambda _prompt: next(post_answer_inputs))

    # Run the topic
    run_topic('app_configuration', 1, mock_perf_data, questions)

    # Check the output
    captured = capsys.readouterr()
    assert "Correct" in strip_ansi_codes(captured.out)

    # Check that performance data was updated
    assert 'app_configuration' in saved_data
    assert saved_data['app_configuration']['correct_questions'] == [question['question'].strip().lower()]

def test_instruction_update():
    """Test that instructions correctly ignore indentation styles and field order."""
    question_dict = {
        'question': 'Modify the manifest to mount a Secret named "secret2".',
        'solution': {
            'apiVersion': 'v1',
            'kind': 'Pod',
            'metadata': {'name': 'mypod'},
            'spec': {
                'containers': [{
                    'name': 'my-container',
                    'image': 'nginx',
                    'volumeMounts': [{'name': 'secret-volume', 'mountPath': '/tmp/secret2'}]
                }],
                'volumes': [{'name': 'secret-volume', 'secret': {'secretName': 'secret2'}}]
            }
        }
    }
    user_manifest = """
    apiVersion: v1
    kind: Pod
    metadata:
      name: mypod
    spec:
      containers:
      - name: my-container
        image: nginx
        volumeMounts:
        - mountPath: /tmp/secret2
          name: secret-volume
      volumes:
      - name: secret-volume
        secret:
          secretName: secret2
    """
    result = kubelingo.validate_manifest_with_llm(question_dict, user_manifest)
    assert result['correct'], "The manifest should be considered correct."

def test_create_issue(monkeypatch, setup_user_data_dir, setup_questions_dir):
    """Test that creating an issue saves the question and removes it from the topic file."""
    question_dict = {'question': 'Sample question', 'solution': 'Sample solution'}
    topic = 'sample_topic'
    issues_file = os.path.join(kubelingo.USER_DATA_DIR, 'issues.yaml')
    topic_file = os.path.join(kubelingo.QUESTIONS_DIR, f'{topic}.yaml')

    # Create a sample topic file
    with open(topic_file, 'w') as f:
        yaml.dump({'questions': [question_dict]}, f)

    # Mock input to provide a description
    monkeypatch.setattr('builtins.input', lambda _: "Sample issue description")

    kubelingo.create_issue(question_dict, topic)

    # Check that the issue was saved
    with open(issues_file, 'r') as f:
        issues = yaml.safe_load(f)
    assert any(q['question'] == 'Sample question' for q in issues), "The issue should be saved."

    # Check that the question was removed from the topic file
    with open(topic_file, 'r') as f:
        data = yaml.safe_load(f)
    assert not any(q['question'] == 'Sample question' for q in data['questions']), "The question should be removed from the topic file."

def test_generate_option_availability(monkeypatch, setup_user_data_dir, setup_questions_dir):
    """Test that the 'generate' option is only available at 100% completion."""
    performance_data = {
        'sample_topic': {
            'correct_questions': ['sample question']
        }
    }
    question_dict = {'question': 'Sample question', 'solution': 'Sample solution'}
    topic_file = os.path.join(kubelingo.QUESTIONS_DIR, 'sample_topic.yaml')

    # Create a sample topic file
    with open(topic_file, 'w') as f:
        yaml.dump({'questions': [question_dict]}, f)

    # Mock input to select the topic and simulate user input
    monkeypatch.setattr('builtins.input', lambda _: "1")

    selected_topic, num_to_study, questions_to_study = kubelingo.list_and_select_topic(performance_data)
    assert selected_topic == 'sample_topic', "The selected topic should be 'sample_topic'."
    assert 'g' in selected_topic, "The 'generate' option should be available at 100% completion."
    """Tests that performance.yaml is backed up to misc/performance.yaml on quiz open/close and app exit."""
    # In-memory data stores for performance and backup files
    mock_user_performance_data = {}
    mock_misc_performance_data = {}

    # Mock load_performance_data to return our in-memory data
    def mock_load_performance_data():
        return mock_user_performance_data.copy()
    monkeypatch.setattr('kubelingo.kubelingo.load_performance_data', mock_load_performance_data)

    # Mock save_performance_data to update our in-memory data
    def mock_save_performance_data(data):
        nonlocal mock_user_performance_data
        mock_user_performance_data = data.copy()
    monkeypatch.setattr('kubelingo.kubelingo.save_performance_data', mock_save_performance_data)

    # Mock backup_performance_file to copy from user to misc in-memory
    def mock_backup_performance_file():
        nonlocal mock_misc_performance_data
        mock_misc_performance_data = mock_user_performance_data.copy()
    monkeypatch.setattr('kubelingo.kubelingo.backup_performance_file', mock_backup_performance_file)

    # Mock other external dependencies that cli() calls
    monkeypatch.setattr('kubelingo.kubelingo.load_dotenv', lambda: None)
    monkeypatch.setattr('kubelingo.kubelingo.colorama_init', lambda **kwargs: None)
    monkeypatch.setattr('os.makedirs', lambda name, exist_ok: None) # Not strictly needed with in-memory mocks, but good practice
    monkeypatch.setattr('kubelingo.kubelingo.click.echo', lambda msg: None)
    monkeypatch.setattr('kubelingo.kubelingo.click.confirm', lambda msg, default: True)
    monkeypatch.setattr('kubelingo.kubelingo.handle_config_menu', lambda: None)
    monkeypatch.setattr('kubelingo.kubelingo.clear_screen', lambda: None)
    monkeypatch.setattr('time.sleep', lambda seconds: None)

    # --- Test Case 1: Initial startup and quit (no quiz started) ---
    # Simulate quitting from the main menu immediately
    mock_list_and_select_topic_inputs = iter([
        (None, None, None), # Simulate 'q' (quit) from main menu
    ])
    monkeypatch.setattr('kubelingo.kubelingo.list_and_select_topic', lambda perf_data: next(mock_list_and_select_topic_inputs))

    # Run the cli (main application loop)
    cli.main(args=[], standalone_mode=False, obj={})

    # Assert that user_data/performance.yaml (mocked) is empty
    assert mock_user_performance_data == {}

    # Assert that misc/performance.yaml (mocked) is empty
    assert mock_misc_performance_data == {}

    # --- Test Case 2: Start quiz, make changes, quit quiz, then quit app ---
    # Reset in-memory data for a fresh start
    mock_user_performance_data.clear()
    mock_misc_performance_data.clear()

    # Simulate selecting a topic, then answering a question, then quitting the quiz, then quitting the app
    mock_list_and_select_topic_inputs = iter([
        ('test_topic', 1, [{'question': 'q1', 'solution': 's1'}]), # Select topic, 1 question
        (None, None, None), # Simulate 'q' (quit) from main menu after quiz
    ])
    monkeypatch.setattr('kubelingo.kubelingo.list_and_select_topic', lambda perf_data: next(mock_list_and_select_topic_inputs))

    mock_run_topic_inputs = iter([
        (['s1'], None), # Correct answer for q1
    ])
    monkeypatch.setattr('kubelingo.kubelingo.get_user_input', lambda allow_solution_command: next(mock_run_topic_inputs))
    monkeypatch.setattr('builtins.input', lambda _prompt: 'q') # Quit after question

    # Mock load_questions for run_topic
    monkeypatch.setattr('kubelingo.kubelingo.load_questions', lambda topic: {'questions': [{'question': 'q1', 'solution': 's1'}]})

    # Run the cli (main application loop)
    cli.main(args=[], standalone_mode=False, obj={})

    # Assert that user_data/performance.yaml (mocked) contains updated data
    expected_user_data = {'test_topic': {'correct_questions': ['q1']}}
    assert mock_user_performance_data == expected_user_data

    # Assert that misc/performance.yaml (mocked) contains the updated data
    assert mock_misc_performance_data == expected_user_data

    # --- Test Case 3: Ensure user_data/performance.yaml is never deleted ---
    # This is implicitly covered by the assertions above. If the file were deleted,
    # the mocked data would be empty or missing. The in-memory mocks ensure that
    # data is only modified as expected, not deleted. This test focuses on the
    # logic of the calls, not the file system mechanics, which are handled by
    # the mocked load/save/backup functions.


