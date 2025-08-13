import itertools
import json
from unittest.mock import MagicMock, patch

import pytest

from kubelingo.modules.question_generator import AIQuestionGenerator
from kubelingo.question import Question, QuestionCategory, QuestionSubject


@pytest.fixture
def mock_llm_client():
    """Fixture to create a mock LLM client that returns a predictable response."""
    client = MagicMock()
    mock_response_content = json.dumps([
        {
            "prompt": "Create a pod named 'test-pod'.",
            "answers": ["kubectl run test-pod --image=nginx"],
            "explanation": "This is how you create a pod."
        }
    ])
    client.chat_completion.return_value = mock_response_content
    return client


@patch('kubelingo.modules.question_generator.add_question')
@patch('kubelingo.modules.question_generator.AIQuestionGenerator._save_question_to_yaml')
def test_generate_questions_adds_to_db(
    mock_save_question, mock_add_question, mock_llm_client
):
    """Test that generated questions are added to the database."""
    generator = AIQuestionGenerator(llm_client=mock_llm_client)
    questions = generator.generate_questions(subject="pods", num_questions=1)

    assert len(questions) == 1
    q = questions[0]
    assert q.prompt == "Create a pod named 'test-pod'."
    assert q.answers == ["kubectl run test-pod --image=nginx"]

    # Assert that add_question was called with correct arguments
    mock_add_question.assert_called_once()
    call_args, call_kwargs = mock_add_question.call_args
    assert call_kwargs['id'].startswith('ai-gen-')
    assert call_kwargs['prompt'] == "Create a pod named 'test-pod'."
    assert call_kwargs['answers'] == json.dumps(["kubectl run test-pod --image=nginx"])
    assert call_kwargs['category'] == "Command"
    assert call_kwargs['subject'] == "pods"
    assert call_kwargs['source_file'] == "ai_generated"
    assert call_kwargs['source'] == "ai_generated"
    assert call_kwargs['validator'] == {"type": "ai", "expected": "kubectl run test-pod --image=nginx"}
    mock_save_question.assert_called_once()


@patch('kubelingo.modules.question_generator.add_question')
@patch('kubelingo.modules.question_generator.AIQuestionGenerator._save_question_to_yaml')
def test_generate_questions_with_base_questions_uses_source_file(
    mock_save_question, mock_add_question, mock_llm_client
):
    """Test that generated questions use the source_file from base_questions."""
    mock_response_content = json.dumps([
        {
            "prompt": "Create a pod named 'test-pod-2'.",
            "answers": ["kubectl run test-pod-2 --image=nginx"],
            "explanation": "This is another test explanation."
        }
    ])
    mock_llm_client.chat_completion.return_value = mock_response_content

    base_q = Question(
        id="base-1",
        prompt="base prompt",
        answers=["base response"],
        source_file="my_special_quiz.yaml",
    )

    generator = AIQuestionGenerator(llm_client=mock_llm_client)
    generator.generate_questions(
        subject="pods", num_questions=1, base_questions=[base_q]
    )

    mock_add_question.assert_called_once()
    _, call_kwargs = mock_add_question.call_args
    assert call_kwargs['source_file'] == 'my_special_quiz.yaml'
    mock_save_question.assert_called_once()


# Create all combinations of category and subject to test against.
test_cases = list(itertools.product(QuestionCategory, QuestionSubject))


def get_category_string_for_generator(category_enum: QuestionCategory) -> str:
    """Maps a QuestionCategory enum to the string expected by the generator."""
    if category_enum == QuestionCategory.YAML_MANIFEST:
        return "Manifest"
    if category_enum == QuestionCategory.COMMAND_SYNTAX:
        return "Command"
    if category_enum == QuestionCategory.OPEN_ENDED:
        return "socratic"
    if category_enum == QuestionCategory.BASIC_TERMINOLOGY:
        return "Basic"
    raise ValueError(f"Unknown category: {category_enum}")


@pytest.mark.parametrize("category, subject", test_cases)
@patch("kubelingo.modules.question_generator.add_question", return_value=None)
@patch("kubelingo.modules.question_generator.AIQuestionGenerator._save_question_to_yaml", return_value=None)
def test_generate_question_for_each_category_and_subject(
    mock_save_yaml: MagicMock,
    mock_add_question: MagicMock,
    mock_llm_client: MagicMock,
    category: QuestionCategory,
    subject: QuestionSubject,
):
    """
    Tests that the AIQuestionGenerator can generate a question for every combination
    of QuestionCategory and QuestionSubject, ensuring correct type mapping and persistence.
    """
    if category == QuestionCategory.YAML_MANIFEST:
        mock_yaml_response = json.dumps([
            {
                "prompt": "Create a manifest for a pod named 'test-pod'.",
                "answers": [
                    """apiVersion: v1
kind: Pod
metadata:
  name: test-pod
spec:
  containers:
  - name: nginx
    image: nginx"""
                ],
                "explanation": "This is a basic pod manifest."
            }
        ])
        mock_llm_client.chat_completion.return_value = mock_yaml_response

    generator = AIQuestionGenerator(llm_client=mock_llm_client)
    category_str = get_category_string_for_generator(category)

    questions = generator.generate_questions(
        subject=subject.value,
        num_questions=1,
        category=category_str,
    )

    assert len(questions) == 1
    question = questions[0]

    # Verify the generated question has the correct category and subject
    assert question.schema_category == category, \
        f"Expected category {category.value} but got {question.schema_category.value}"
    assert question.subject_matter == subject, \
        f"Expected subject {subject.value} but got {question.subject_matter.value}"

    # Verify that persistence methods were called
    mock_add_question.assert_called_once()
    mock_save_yaml.assert_called_once()

    # Verify the correct data was passed to the database
    call_args, call_kwargs = mock_add_question.call_args
    assert call_kwargs["subject"] == subject.value
    assert call_kwargs["category"] == category_str
