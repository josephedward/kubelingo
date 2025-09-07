import os
import json
import pytest
from unittest.mock import patch, MagicMock
import kubelingo.cli as cli
from InquirerPy import inquirer

@pytest.fixture(autouse=True)
def use_tmp_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Ensure the questions directory exists for saving questions
    questions_dir = tmp_path / 'questions' / 'stored'
    questions_dir.mkdir(parents=True, exist_ok=True)
    questions_dir = tmp_path / 'questions' / 'correct'
    questions_dir.mkdir(parents=True, exist_ok=True)
    questions_dir = tmp_path / 'questions' / 'missed'
    questions_dir.mkdir(parents=True, exist_ok=True)
    yield

import copy
# ... (rest of imports)

@pytest.fixture
def mock_questions():
    return copy.deepcopy([
        {"id": "q1", "question": "Question 1", "answer": "Answer 1", "question_type": "tf"},
        {"id": "q2", "question": "Question 2", "answer": "Answer 2", "question_type": "tf"},
        {"id": "q3", "question": "Question 3", "answer": "Answer 3", "question_type": "tf"},
    ])

@patch('builtins.print')
@patch('builtins.input')
@patch('kubelingo.cli.post_answer_menu')
@patch('kubelingo.cli.save_question')
@patch('rich.console.Console.print')
@patch('kubelingo.llm_utils.ai_chat') # Patch ai_chat
def test_quiz_session_advances_after_direct_answer(
    mock_ai_chat, mock_console_print, mock_save_question, mock_post_answer_menu, mock_input, mock_print, mock_questions
):
    mock_ai_chat.return_value = "AI feedback simulation." # Return a dummy value
    # Simulate user typing an answer and then choosing to advance (e.g., 'r' for retry, then 'n' for next)
    # Or, more simply, just typing an answer and letting handle_post_answer move to the next.
    # For this test, we want to ensure the 'else' block correctly calls handle_post_answer
    # and the quiz advances.
    mock_input.side_effect = [
        "user_answer_1", # Answer for Q1
        "user_answer_2", # Answer for Q2
        "q"              # Quit after Q2
    ]
    mock_post_answer_menu.side_effect = ["n", "n"] # Always choose 'n' (next question) in post-answer menu

    cli.quiz_session(mock_questions)

    # Assert that questions were displayed
    mock_print.assert_any_call("\nQuestion: Question 1")
    mock_print.assert_any_call("\nQuestion: Question 2")
    # Assert that the quiz session finished
    mock_print.assert_any_call("Quiz session finished.")
    # Assert that handle_post_answer was called twice (once for each answer)
    assert mock_post_answer_menu.call_count == 2

@patch('builtins.print')
@patch('builtins.input')
@patch('kubelingo.cli.post_answer_menu')
@patch('kubelingo.cli.save_question')
@patch('rich.console.Console.print')
@patch('kubelingo.llm_utils.ai_chat') # Patch ai_chat
def test_quiz_session_terminates_after_initial_count(
    mock_ai_chat, mock_console_print, mock_save_question, mock_post_answer_menu, mock_input, mock_print, mock_questions
):
    mock_ai_chat.return_value = "AI feedback simulation." # Return a dummy value
    # Test with 3 questions, and ensure it ends after 3 answers
    mock_input.side_effect = [
        "answer_q1", # Answer for Q1
        "answer_q2", # Answer for Q2
        "answer_q3", # Answer for Q3
    ]
    mock_post_answer_menu.side_effect = ["n", "n", "n"] # Always choose 'n' (next question)

    cli.quiz_session(mock_questions)

    # Assert that all 3 questions were displayed
    mock_print.assert_any_call("\nQuestion: Question 1")
    mock_print.assert_any_call("\nQuestion: Question 2")
    mock_print.assert_any_call("\nQuestion: Question 3")
    # Assert that the quiz session finished
    mock_print.assert_any_call("Quiz session finished.")
    # Assert that handle_post_answer was called 3 times
    assert mock_post_answer_menu.call_count == 3

@patch('builtins.print')
@patch('builtins.input')
@patch('kubelingo.cli.post_answer_menu')
@patch('kubelingo.cli.save_question')
@patch('rich.console.Console.print')
def test_quiz_session_with_question_removal(
    mock_console_print, mock_save_question, mock_post_answer_menu, mock_input, mock_print, mock_questions
):
    # Simulate answering Q1 and marking it correct, then quitting
    mock_input.side_effect = [
        "answer_q1", # Answer for Q1
        "q"          # Quit
    ]
    mock_post_answer_menu.side_effect = ["c"] # Mark Q1 correct

    cli.quiz_session(mock_questions)

    # Assert Q1 was displayed
    mock_print.assert_any_call("\nQuestion: Question 1")
    # Assert save_question was called for Q1
    mock_save_question.assert_called_once_with(
        {"id": "q1", "question": "Question 1", "answer": "Answer 1", "question_type": "tf", "user_answer": "answer_q1"},
        os.path.join(os.getcwd(), 'questions', 'correct')
    )
    # Assert the quiz session finished
    mock_print.assert_any_call("Quiz session finished.")
    # Assert that handle_post_answer was called once
    assert mock_post_answer_menu.call_count == 1

@patch('builtins.print')
@patch('builtins.input')
@patch('kubelingo.cli.post_answer_menu')
@patch('kubelingo.cli.save_question')
@patch('rich.console.Console.print')
def test_quiz_session_terminates_when_all_removed(
    mock_console_print, mock_save_question, mock_post_answer_menu, mock_input, mock_print, mock_questions
):
    # Simulate answering Q1 and marking it correct, then Q2 and marking it correct, then Q3 and marking it correct
    mock_input.side_effect = [
        "answer_q1", # Answer for Q1
        "answer_q2", # Answer for Q2
        "answer_q3", # Answer for Q3
    ]
    mock_post_answer_menu.side_effect = ["c", "c", "c"] # Mark all correct

    cli.quiz_session(mock_questions)

    # Assert all questions were displayed
    mock_print.assert_any_call("\nQuestion: Question 1")
    mock_print.assert_any_call("\nQuestion: Question 2")
    mock_print.assert_any_call("\nQuestion: Question 3")
    # Assert save_question was called for all 3 questions
    assert mock_save_question.call_count == 3
    # Assert the quiz session finished
    mock_print.assert_any_call("Quiz session finished.")
    # Assert that handle_post_answer was called 3 times
    assert mock_post_answer_menu.call_count == 3
    # Ensure the quiz ended because all questions were removed, not by 'q'
    assert "Quiz session finished." in [call.args[0] for call in mock_print.call_args_list]
    assert "Exiting Kubelingo. Goodbye!" not in [call.args[0] for call in mock_print.call_args_list]
