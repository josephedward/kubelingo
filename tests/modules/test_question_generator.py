import pytest
from unittest.mock import patch, MagicMock
from kubelingo.modules.question_generator import AIQuestionGenerator
from kubelingo.question import Question


@patch('kubelingo.modules.question_generator.validate_kubectl_syntax')
@patch('kubelingo.modules.question_generator.validate_prompt_completeness')
@patch('kubelingo.modules.question_generator.add_question')
@patch('openai.ChatCompletion.create')
def test_generate_questions_adds_to_db(
    mock_chat_completion, mock_add_question, mock_validate_prompt, mock_validate_syntax
):
    """Test that generated questions are added to the database."""
    # Mock validation to always return valid
    mock_validate_syntax.return_value = {"valid": True}
    mock_validate_prompt.return_value = {"valid": True}

    # Mock OpenAI response
    mock_response_content = """
    [
        {
            "prompt": "Create a pod named 'test-pod'.",
            "response": "kubectl run test-pod --image=nginx"
        }
    ]
    """
    mock_choice = MagicMock()
    mock_choice.message.content = mock_response_content
    mock_chat_completion.return_value.choices = [mock_choice]

    generator = AIQuestionGenerator()
    questions = generator.generate_questions(subject="pods", num_questions=1)

    assert len(questions) == 1
    q = questions[0]
    assert q.prompt == "Create a pod named 'test-pod'."
    assert q.response == "kubectl run test-pod --image=nginx"

    # Assert that add_question was called with correct arguments
    mock_add_question.assert_called_once()
    call_args, call_kwargs = mock_add_question.call_args
    assert call_kwargs['id'].startswith('ai-gen-')
    assert call_kwargs['prompt'] == "Create a pod named 'test-pod'."
    assert call_kwargs['response'] == "kubectl run test-pod --image=nginx"
    assert call_kwargs['category'] == "pods"
    assert call_kwargs['source_file'] == "ai_generated"
    assert call_kwargs['source'] == "ai"
    assert call_kwargs['validator'] == {"type": "ai", "expected": "kubectl run test-pod --image=nginx"}


@patch('kubelingo.modules.question_generator.validate_kubectl_syntax')
@patch('kubelingo.modules.question_generator.validate_prompt_completeness')
@patch('kubelingo.modules.question_generator.add_question')
@patch('openai.ChatCompletion.create')
def test_generate_questions_with_base_questions_uses_source_file(
    mock_chat_completion, mock_add_question, mock_validate_prompt, mock_validate_syntax
):
    """Test that generated questions use the source_file from base_questions."""
    # Mock validation to always return valid
    mock_validate_syntax.return_value = {"valid": True}
    mock_validate_prompt.return_value = {"valid": True}

    # Mock OpenAI response
    mock_response_content = """
    [
        {
            "prompt": "Create a pod named 'test-pod-2'.",
            "response": "kubectl run test-pod-2 --image=nginx"
        }
    ]
    """
    mock_choice = MagicMock()
    mock_choice.message.content = mock_response_content
    mock_chat_completion.return_value.choices = [mock_choice]

    base_q = MagicMock(spec=Question)
    base_q.source_file = "my_special_quiz.yaml"
    base_q.prompt = "base prompt"
    base_q.response = "base response"

    generator = AIQuestionGenerator()
    generator.generate_questions(
        subject="pods", num_questions=1, base_questions=[base_q]
    )

    mock_add_question.assert_called_once()
    _, call_kwargs = mock_add_question.call_args
    assert call_kwargs['source_file'] == 'my_special_quiz.yaml'
