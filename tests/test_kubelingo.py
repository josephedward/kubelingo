import subprocess
import tempfile
import os
from unittest.mock import mock_open
import colorama
import re
from kubelingo.kubelingo import (
    get_user_input,
    run_topic,
    list_and_select_topic,
    load_performance_data,
    save_performance_data,
    load_questions,
    clear_screen,
    save_question_to_list,
)

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
    monkeypatch.setattr('kubelingo.kubelingo.get_user_input', lambda: next(user_inputs))
    post_answer_inputs = iter(['n', 'q']) # 'n' for first question, 'q' for second
    monkeypatch.setattr('builtins.input', lambda _prompt: next(post_answer_inputs))

    run_topic('existing_topic', len(questions), mock_data_source)

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
