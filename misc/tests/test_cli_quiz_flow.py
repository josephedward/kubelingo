import pytest
from unittest.mock import MagicMock, patch
from InquirerPy import inquirer

import cli
from question_generator import KubernetesTopics

class DummyPrompt:
    def __init__(self, value):
        self.value = value
    def execute(self):
        return self.value

@pytest.fixture(autouse=True)
def isolate_last_generated_q(monkeypatch):
    # Ensure last_generated_q is reset before each test
    cli.last_generated_q = None
    yield
    cli.last_generated_q = None

@pytest.fixture
def mock_ai_chat_tf(monkeypatch):
    # Mock ai_chat to return a True/False question
    def _mock_ai_chat(system_prompt, user_prompt):
        return '{"type": "tf", "question": "True or False: Kubernetes is open source.", "answer": "true"}'
    monkeypatch.setattr(cli, "ai_chat", _mock_ai_chat)

@pytest.fixture
def mock_ai_chat_vocab(monkeypatch):
    # Mock ai_chat to return a vocab question
    def _mock_ai_chat(system_prompt, user_prompt):
        return '{"type": "vocab", "question": "What is a Pod?", "answer": "Smallest deployable unit"}'
    monkeypatch.setattr(cli, "ai_chat", _mock_ai_chat)

@pytest.fixture
def mock_inquirer_select(monkeypatch):
    # Mock inquirer.select for topic selection and post-answer menu
    mock_select = MagicMock()
    monkeypatch.setattr(inquirer, 'select', mock_select)
    return mock_select

@pytest.fixture
def mock_inquirer_text(monkeypatch):
    # Mock inquirer.text for user answers
    mock_text = MagicMock()
    monkeypatch.setattr(inquirer, 'text', mock_text)
    return mock_text

@pytest.fixture
def mock_print_menus(monkeypatch):
    # Mock print_question_menu and print_post_answer_menu to track calls
    mock_q_menu = MagicMock()
    mock_a_menu = MagicMock()
    monkeypatch.setattr(cli, 'print_question_menu', mock_q_menu)
    monkeypatch.setattr(cli, 'print_post_answer_menu', mock_a_menu)
    return mock_q_menu, mock_a_menu

def test_trivia_flow_correct_answer_and_quit(
    capsys, mock_ai_chat_tf, mock_inquirer_select, mock_inquirer_text, mock_print_menus
):
    mock_q_menu, mock_a_menu = mock_print_menus

    # Simulate user selecting 'Trivia' and 'pods'
    mock_inquirer_select.side_effect = [
        DummyPrompt("Trivia"), # Quiz type selection
        DummyPrompt(KubernetesTopics.PODS.value), # Topic selection
        DummyPrompt("do not save question") # Post-answer menu action (label for 'd')
    ]
    # Simulate user answering 'True'
    mock_inquirer_text.return_value = DummyPrompt("True")

    # Run the quiz menu (which calls generate_trivia)
    cli.quiz_menu()

    captured = capsys.readouterr()

    # Assert question menu was shown before answer
    mock_q_menu.assert_called_once()
    # Assert post-answer menu was shown after answer
    mock_a_menu.assert_called_once()

    # Assert correct message and post-answer menu options are displayed
    assert "Correct!" in captured.out
    assert "r) retry" in captured.out
    assert "c) correct" in captured.out
    assert "m) missed" in captured.out
    assert "d) delete" in captured.out # New label

    # Assert question menu is NOT shown after answer
    # This is tricky with capsys, but we can check for its header if it were printed
    assert "v) vim" not in captured.out
    assert "b) backward" not in captured.out

    # Assert last_generated_q is recorded (correctness tracked via output)
    assert cli.last_generated_q is not None

def test_trivia_flow_incorrect_answer_and_retry(
    capsys, mock_ai_chat_tf, mock_inquirer_select, mock_inquirer_text, mock_print_menus
):
    mock_q_menu, mock_a_menu = mock_print_menus

    # Simulate user selecting 'Trivia' and 'pods'
    # Then answering 'False' (incorrect)
    # Then selecting 'retry' from post-answer menu
    # Then answering 'True' (correct)
    # Then selecting 'do not save question' to exit
    mock_inquirer_select.side_effect = [
        DummyPrompt("Trivia"), # Quiz type selection
        DummyPrompt(KubernetesTopics.PODS.value), # Topic selection
        DummyPrompt("retry"), # Post-answer menu action
        DummyPrompt("do not save question") # Post-answer menu action to quit
    ]
    mock_inquirer_text.side_effect = [
        DummyPrompt("False"), # First answer (incorrect)
        DummyPrompt("True")   # Second answer (correct, after retry)
    ]

    cli.quiz_menu()

    captured = capsys.readouterr()

    # Assert incorrect message
    assert "Wrong. Expected 'true'." in captured.out
    # Assert correct message after retry
    assert "Correct!" in captured.out

    # Assert question menu was shown before each answer
    assert mock_q_menu.call_count == 2 # Once for each question presentation
    # Assert post-answer menu was shown after each answer
    assert mock_a_menu.call_count == 2 # Once after incorrect, once after correct

    # Assert last_generated_q is recorded for the final correct answer
    assert cli.last_generated_q is not None

def test_trivia_flow_question_menu_before_answer_and_help(
    capsys, mock_ai_chat_tf, mock_inquirer_select, mock_inquirer_text, mock_print_menus
):
    mock_q_menu, mock_a_menu = mock_print_menus

    # Simulate user selecting 'Trivia' and 'pods'
    mock_inquirer_select.side_effect = [
        DummyPrompt("Trivia"), # Quiz type selection
        DummyPrompt(KubernetesTopics.PODS.value), # Topic selection
        DummyPrompt("do not save question") # Post-answer menu action
    ]
    mock_inquirer_text.side_effect = [
        DummyPrompt("?"),    # Request help
        DummyPrompt("True")  # Actual answer
    ]

    cli.quiz_menu()

    captured = capsys.readouterr()

    # Assert question menu was shown initially and after '?'
    assert mock_q_menu.call_count == 2
    # Assert post-answer menu was shown after answer
    mock_a_menu.assert_called_once()

    # Verify question menu options are in output (from initial display and '?' command)
    assert "v) vim" in captured.out
    assert "b) backward" in captured.out
    assert "f) forward" in captured.out
    assert "a) answer" in captured.out
    assert "s) visit" in captured.out
    assert "q) quit" in captured.out

    # Assert correct message
    assert "Correct!" in captured.out

def test_trivia_flow_no_question_menu_after_answer(
    capsys, mock_ai_chat_tf, mock_inquirer_select, mock_inquirer_text, mock_print_menus
):
    mock_q_menu, mock_a_menu = mock_print_menus

    # Simulate user selecting 'Trivia' and 'pods'
    mock_inquirer_select.side_effect = [
        DummyPrompt("Trivia"), # Quiz type selection
        DummyPrompt(KubernetesTopics.PODS.value), # Topic selection
        DummyPrompt("do not save question") # Post-answer menu action
    ]
    mock_inquirer_text.return_value = DummyPrompt("True")

    cli.quiz_menu()

    captured = capsys.readouterr()

    # Assert question menu was shown only once (before the answer)
    mock_q_menu.assert_called_once()
    # Assert post-answer menu was shown once (after the answer)
    mock_a_menu.assert_called_once()

    # Check that the question menu header/options do not appear after the answer
    # This is a bit indirect, but we can check the order of calls and content
    # The 'Correct!' message should appear before the post-answer menu, and no question menu in between.
    correct_idx = captured.out.find("Correct!")
    post_answer_menu_idx = captured.out.find("r) retry") # First option of post-answer menu

    assert correct_idx != -1
    assert post_answer_menu_idx != -1
    assert correct_idx < post_answer_menu_idx

    # Ensure no question menu options appear between 'Correct!' and 'r) retry'
    segment = captured.out[correct_idx:post_answer_menu_idx]
    assert "v) vim" not in segment
    assert "b) backward" not in segment
    assert "f) forward" not in segment
    assert "a) answer" not in segment
    assert "s) visit" not in segment
    assert "q) quit" not in segment

@patch('cli._open_manifest_editor')
def test_manifest_quiz_vim_editor(
    mock_open_manifest_editor, capsys, mock_inquirer_select, mock_inquirer_text
):
    # Mock _open_manifest_editor to return some content
    mock_open_manifest_editor.return_value = "apiVersion: v1\nkind: Pod"

    # Simulate user selecting 'Manifest' quiz type, 'deployments' topic,
    # then typing 'v' for vim, and 'quit' to exit the quiz loop.
    mock_inquirer_select.side_effect = [
        DummyPrompt("Manifest"), # Quiz type selection
        DummyPrompt(KubernetesTopics.DEPLOYMENTS.value) # Topic selection
    ]
    mock_inquirer_text.side_effect = [
        DummyPrompt("v"), # User types 'v' for vim
        DummyPrompt("quit") # User types 'quit' to exit the quiz loop
    ]

    cli.quiz_menu()

    captured = capsys.readouterr()

    # Assert that _open_manifest_editor was called once
    mock_open_manifest_editor.assert_called_once()

    # Assert that the "Manifest edited:" message is printed
    assert "Manifest edited:" in captured.out
    assert "apiVersion: v1\nkind: Pod" in captured.out # Verify content from mock is printed
    assert "No manifest to edit in this mode." not in captured.out # Ensure old message is gone