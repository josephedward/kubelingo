import pytest
from unittest.mock import patch, MagicMock
import logging
import argparse

from kubelingo.modules.kubernetes.session import NewSession

# Mock questions for the Vim quiz. The category is important.
MOCK_VIM_QUESTIONS = [
    {
        "id": "vim-q1",
        "category": "Vim Commands",
        "prompt": "How do you save the current file and exit Vim?",
        "response": ":wq",
        "explanation": "':wq' writes the changes to the file and quits Vim.",
        "data_file": "vim_quiz.json" # to test review flagging
    }
]

@pytest.fixture
def session():
    """Fixture to create a NewSession instance with a logger."""
    logger = logging.getLogger(__name__)
    session_instance = NewSession(logger)
    # Mock the session manager for testing flag/unflag functionality
    session_instance.session_manager = MagicMock()
    return session_instance


@pytest.fixture
def mock_args():
    """Fixture to create a mock args object pointing to a vim quiz file."""
    args = argparse.Namespace(
        file="vim_quiz.json", # Bypasses interactive menu
        review_only=False,
        category=None,
        num=None,
        docker=False,
        ai_eval=False
    )
    return args

@patch('kubelingo.modules.kubernetes.session.load_questions')
@patch('kubelingo.modules.ai_evaluator.AIEvaluator')
@patch('kubelingo.modules.kubernetes.session.questionary')
@patch('kubelingo.modules.kubernetes.session.PromptSession')
def test_vim_quiz_correct_answer(mock_prompt_session, mock_questionary, mock_ai_evaluator, mock_load_questions, session, mock_args, capsys):
    """
    Test a Vim quiz flow with a correct answer.
    """
    mock_load_questions.return_value = MOCK_VIM_QUESTIONS

    mock_questionary.select.side_effect = [
        MagicMock(ask=lambda: "answer"),
        MagicMock(ask=lambda: "check"),
        MagicMock(ask=lambda: "back"),
    ]
    mock_prompt_instance = mock_prompt_session.return_value
    mock_prompt_instance.prompt.return_value = ":wq"

    mock_ai_instance = mock_ai_evaluator.return_value
    mock_ai_instance.evaluate_command.return_value = {
        'correct': True,
        'reasoning': 'The command is correct.'
    }
    
    session.run_exercises(mock_args)

    captured = capsys.readouterr()
    assert "Correct!" in captured.out
    assert "AI Evaluation: Correct - The command is correct." in captured.out
    assert MOCK_VIM_QUESTIONS[0]['explanation'] in captured.out
    mock_ai_instance.evaluate_command.assert_called_once_with(
        MOCK_VIM_QUESTIONS[0],
        ":wq"
    )
    mock_load_questions.assert_called_with("vim_quiz.json")


@patch('kubelingo.modules.kubernetes.session.load_questions')
@patch('kubelingo.modules.ai_evaluator.AIEvaluator')
@patch('kubelingo.modules.kubernetes.session.questionary')
@patch('kubelingo.modules.kubernetes.session.PromptSession')
def test_vim_quiz_incorrect_answer(mock_prompt_session, mock_questionary, mock_ai_evaluator, mock_load_questions, session, mock_args, capsys):
    """
    Test a Vim quiz flow with an incorrect answer.
    """
    mock_load_questions.return_value = MOCK_VIM_QUESTIONS

    mock_questionary.select.side_effect = [
        MagicMock(ask=lambda: "answer"),
        MagicMock(ask=lambda: "check"),
        MagicMock(ask=lambda: "back"),
    ]
    mock_prompt_instance = mock_prompt_session.return_value
    mock_prompt_instance.prompt.return_value = ":q!"

    mock_ai_instance = mock_ai_evaluator.return_value
    mock_ai_instance.evaluate_command.return_value = {
        'correct': False,
        'reasoning': 'The command is incorrect.'
    }

    session.run_exercises(mock_args)

    captured = capsys.readouterr()
    assert "Incorrect." in captured.out
    assert "AI Evaluation: Incorrect - The command is incorrect." in captured.out
    assert MOCK_VIM_QUESTIONS[0]['explanation'] not in captured.out
    mock_ai_instance.evaluate_command.assert_called_once_with(
        MOCK_VIM_QUESTIONS[0],
        ":q!"
    )
    mock_load_questions.assert_called_with("vim_quiz.json")

@patch('kubelingo.modules.kubernetes.session.load_questions')
@patch('kubelingo.modules.kubernetes.session.questionary')
def test_vim_quiz_flag_question(mock_questionary, mock_load_questions, session, mock_args, capsys):
    """
    Test flagging a question for review in the Vim quiz.
    """
    mock_load_questions.return_value = MOCK_VIM_QUESTIONS

    mock_questionary.select.side_effect = [
        MagicMock(ask=lambda: "flag"),
        MagicMock(ask=lambda: "back"),
    ]
    
    session.run_exercises(mock_args)
    
    captured = capsys.readouterr()
    assert "Question flagged for review." in captured.out
    
    question = MOCK_VIM_QUESTIONS[0]
    session.session_manager.mark_question_for_review.assert_called_once_with(
        question['data_file'], question['category'], question['prompt']
    )
