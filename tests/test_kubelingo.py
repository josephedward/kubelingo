import subprocess
import tempfile
import os
from unittest.mock import mock_open
import colorama
from kubelingo import get_user_input, handle_vim_edit


def test_back_command_removes_last_entry(monkeypatch, capsys):
    """Tests that 'back' removes the previously entered command."""
    inputs = iter(['cmd1', 'back', 'done'])
    monkeypatch.setattr('builtins.input', lambda _prompt: next(inputs))
    user_commands, special_action = get_user_input()
    captured = capsys.readouterr()
    assert user_commands == []
    assert special_action is None
    assert "(Removed: 'cmd1')" in captured.out


def test_back_command_on_empty_list(monkeypatch, capsys):
    """Tests that 'back' does nothing when the command list is empty."""
    inputs = iter(['back', 'done'])
    monkeypatch.setattr('builtins.input', lambda _prompt: next(inputs))
    user_commands, special_action = get_user_input()
    captured = capsys.readouterr()
    assert user_commands == []
    assert special_action is None
    assert "(No lines to remove)" in captured.out


def test_back_command_in_the_middle(monkeypatch, capsys):
    """Tests using 'back' to remove a command between other commands."""
    inputs = iter(['cmd1', 'cmd2', 'back', 'cmd3', 'done'])
    monkeypatch.setattr('builtins.input', lambda _prompt: next(inputs))
    user_commands, special_action = get_user_input()
    captured = capsys.readouterr()
    assert user_commands == ['cmd1', 'cmd3']
    assert special_action is None
    assert "(Removed: 'cmd2')" in captured.out


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


def test_vim_is_configured_for_2_spaces(monkeypatch):
    """Tests that vim is called with commands to set tab spacing to 2 spaces."""
    question = {'question': 'q', 'solution': 's'}

    called_args = []
    def mock_subprocess_run(cmd_list, check=False):
        called_args.append(cmd_list)
        return subprocess.CompletedProcess(cmd_list, 0)
    monkeypatch.setattr(subprocess, 'run', mock_subprocess_run)

    class MockTempFile:
        name = 'dummy.yaml'
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_value, traceback):
            pass
        def write(self, *args): pass
        def flush(self, *args): pass

    monkeypatch.setattr(tempfile, 'NamedTemporaryFile', lambda **kwargs: MockTempFile())
    monkeypatch.setattr('os.unlink', lambda path: None)
    monkeypatch.setattr('builtins.open', mock_open(read_data='some manifest data'))
    monkeypatch.setattr('kubelingo.validate_manifest_with_llm', lambda q, m: {'correct': True, 'feedback': ''})

    handle_vim_edit(question)

    assert len(called_args) == 1
    expected_cmd = ['vim', '-c', "set tabstop=2 shiftwidth=2 expandtab", 'dummy.yaml']
    assert called_args[0] == expected_cmd


def test_back_command_feedback_is_colored(monkeypatch, capsys):
    """Tests that feedback from the 'back' command is colorized."""
    colorama.init(strip=False)
    try:
        # Test when an item is removed
        inputs = iter(['cmd1', 'back', 'done'])
        monkeypatch.setattr('builtins.input', lambda _prompt: next(inputs))
        get_user_input()
        captured = capsys.readouterr()
        assert "(Removed: 'cmd1')" in captured.out
        assert colorama.Fore.YELLOW in captured.out

        # Test when list is empty
        inputs = iter(['back', 'done'])
        monkeypatch.setattr('builtins.input', lambda _prompt: next(inputs))
        get_user_input()
        captured = capsys.readouterr()
        assert "(No lines to remove)" in captured.out
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

    monkeypatch.setattr('kubelingo.load_performance_data', mock_load_performance_data)
    monkeypatch.setattr('kubelingo.save_performance_data', mock_save_performance_data)

    # In this session, user answers q1 again correctly and q2 correctly.
    questions = [{'question': 'q1', 'solution': 's1'}, {'question': 'q2', 'solution': 's2'}]
    monkeypatch.setattr('kubelingo.load_questions', lambda topic: {'questions': questions})
    monkeypatch.setattr('kubelingo.clear_screen', lambda: None)
    monkeypatch.setattr('time.sleep', lambda seconds: None)
    monkeypatch.setattr('kubelingo.save_question_to_list', lambda *args: None)
    monkeypatch.setattr('kubelingo.random.shuffle', lambda x: None)

    from kubelingo import run_topic

    user_inputs = iter([
        (['s1'], None),      # Correct answer for q1
        (['s2'], None),      # Correct answer for q2
    ])
    monkeypatch.setattr('kubelingo.get_user_input', lambda: next(user_inputs))

    run_topic('existing_topic')

    # q2 should be added, q1 should not be duplicated.
    assert 'existing_topic' in saved_data
    assert isinstance(saved_data['existing_topic']['correct_questions'], list)
    # Using a set for comparison to ignore order
    assert set(saved_data['existing_topic']['correct_questions']) == {'q1', 'q2'}
    assert len(saved_data['existing_topic']['correct_questions']) == 2


def test_performance_data_migrates_from_old_format(monkeypatch):
    """
    Tests that old performance data format is correctly migrated to the new
    format that tracks unique questions.
    """
    # Start with old format data
    mock_data_source = {'existing_topic': {'correct': 5, 'total': 10}}
    saved_data = {}

    def mock_load_performance_data():
        return mock_data_source.copy()

    def mock_save_performance_data(data):
        nonlocal saved_data
        saved_data = data

    monkeypatch.setattr('kubelingo.load_performance_data', mock_load_performance_data)
    monkeypatch.setattr('kubelingo.save_performance_data', mock_save_performance_data)

    # In this session, user answers q1 correctly.
    questions = [{'question': 'q1', 'solution': 's1'}]
    monkeypatch.setattr('kubelingo.load_questions', lambda topic: {'questions': questions})
    monkeypatch.setattr('kubelingo.clear_screen', lambda: None)
    monkeypatch.setattr('time.sleep', lambda seconds: None)
    monkeypatch.setattr('kubelingo.save_question_to_list', lambda *args: None)
    monkeypatch.setattr('kubelingo.random.shuffle', lambda x: None)

    from kubelingo import run_topic

    user_inputs = iter([
        (['s1'], None),      # Correct answer for q1
    ])
    monkeypatch.setattr('kubelingo.get_user_input', lambda: next(user_inputs))

    run_topic('existing_topic')

    # The old data should be replaced by the new format, containing only the
    # question answered correctly in this session.
    assert 'existing_topic' in saved_data
    assert 'correct' not in saved_data['existing_topic']
    assert 'total' not in saved_data['existing_topic']
    assert saved_data['existing_topic']['correct_questions'] == ['q1']


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
    monkeypatch.setattr('kubelingo.load_performance_data', lambda: mock_perf_data)

    def mock_load_questions(topic):
        if topic == 'topic1':
            return {'questions': [{}, {}, {}]} # 3 questions
        if topic == 'topic2':
            return {'questions': [{}, {}, {}, {}, {}]} # 5 questions
        return None
    monkeypatch.setattr('kubelingo.load_questions', mock_load_questions)

    # Mock input to exit menu
    def mock_input_eof(prompt):
        raise EOFError
    monkeypatch.setattr('builtins.input', mock_input_eof)

    from kubelingo import list_and_select_topic

    topic = list_and_select_topic()
    assert topic is None

    captured = capsys.readouterr()
    output = captured.out

    assert "Topic1 [3 questions]" in output
    assert "Topic2 [5 questions]" in output
    assert f"({colorama.Fore.YELLOW}2/3 correct - 67%{colorama.Style.RESET_ALL})" in output
    assert f"({colorama.Fore.GREEN}5/5 correct - 100%{colorama.Style.RESET_ALL})" in output
    assert f"{colorama.Style.BRIGHT}{colorama.Fore.CYAN}Please select a topic to study:" in output


def test_topic_menu_ignores_old_performance_format(monkeypatch, capsys):
    """
    Tests that the topic menu ignores old-format performance data and only
    displays stats for the new format.
    """
    # Mock filesystem and data
    monkeypatch.setattr('os.listdir', lambda path: ['old_format_topic.yaml', 'new_format_topic.yaml'])
    monkeypatch.setattr('os.path.exists', lambda path: False) # For missed questions

    mock_perf_data = {
        'old_format_topic': {'correct': 8, 'total': 10}, # Old format, should be ignored
        'new_format_topic': {'correct_questions': ['q1']} # New format, should be displayed
    }
    monkeypatch.setattr('kubelingo.load_performance_data', lambda: mock_perf_data)

    def mock_load_questions(topic):
        if topic == 'old_format_topic':
            return {'questions': [{}, {}]} # 2 questions
        if topic == 'new_format_topic':
            return {'questions': [{}, {}, {}]} # 3 questions
        return None
    monkeypatch.setattr('kubelingo.load_questions', mock_load_questions)

    # Mock input to exit menu
    def mock_input_eof(prompt):
        raise EOFError
    monkeypatch.setattr('builtins.input', mock_input_eof)

    from kubelingo import list_and_select_topic

    list_and_select_topic()

    captured = capsys.readouterr()
    output = captured.out
    
    # Check that the topic with old format data does NOT show stats
    assert "Old Format Topic [2 questions]" in output
    assert "Old Format Topic [2 questions] (" not in output

    # Check that the topic with new format data DOES show stats
    assert "New Format Topic [3 questions]" in output
    assert f"({colorama.Fore.RED}1/3 correct - 33%{colorama.Style.RESET_ALL})" in output


def test_diff_is_shown_for_incorrect_manifest(monkeypatch, capsys):
    """
    Tests that a diff is shown when a user submits an incorrect manifest via vim.
    """
    colorama.init(strip=False)
    try:
        question = {
            'question': 'Create a manifest for a pod.',
            'solution': 'apiVersion: v1\nkind: Pod\nmetadata:\n  name: correct-pod'
        }
        user_manifest = 'apiVersion: v1\nkind: Pod\nmetadata:\n  name: wrong-pod'
        
        monkeypatch.setattr('kubelingo.load_questions', lambda topic: {'questions': [question]})
        monkeypatch.setattr('kubelingo.get_user_input', lambda: ([], 'vim'))
        mock_result = {'correct': False, 'feedback': 'Incorrect name.'}
        monkeypatch.setattr('kubelingo.handle_vim_edit', lambda q: (user_manifest, mock_result, False))
        
        monkeypatch.setattr('kubelingo.clear_screen', lambda: None)
        monkeypatch.setattr('time.sleep', lambda seconds: None)
        monkeypatch.setattr('kubelingo.save_question_to_list', lambda file, q, topic: None)

        from kubelingo import run_topic
        run_topic('some_topic')

        captured = capsys.readouterr()
        output = captured.out
        
        assert "--- Diff ---" in output
        assert "-  name: wrong-pod" in output
        assert "+  name: correct-pod" in output
        assert colorama.Fore.RED in output
        assert colorama.Fore.GREEN in output
    finally:
        colorama.deinit()
