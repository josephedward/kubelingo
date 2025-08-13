import json
import pytest
from unittest.mock import MagicMock, patch

from kubelingo.modules.question_generator import AIQuestionGenerator
from kubelingo.question import Question, QuestionCategory, QuestionSubject

# Mapping from enum to the string category expected by generate_questions
CATEGORY_MAP = {
    QuestionCategory.COMMAND_SYNTAX: "Command",
    QuestionCategory.YAML_MANIFEST: "Manifest",
    QuestionCategory.OPEN_ENDED: "socratic",
    QuestionCategory.BASIC_TERMINOLOGY: "Basic",
}

# Create all combinations for parameterization
TEST_CASES = [
    (category, subject)
    for category in QuestionCategory
    for subject in QuestionSubject
]


@pytest.fixture
def mock_llm_client():
    """Fixture for a mocked LLM client."""
    client = MagicMock()
    # Mock the chat_completion to return a valid-looking JSON response
    mock_response = json.dumps([
        {
            "prompt": "Test prompt",
            "answers": ["Test answer"],
            "explanation": "Test explanation"
        }
    ])
    client.chat_completion.return_value = mock_response
    return client


@patch("kubelingo.modules.question_generator.add_question")
@patch("kubelingo.modules.question_generator.AIQuestionGenerator._save_question_to_yaml")
@pytest.mark.parametrize("category_enum, subject_enum", TEST_CASES)
def test_generate_question_for_all_types_and_subjects(
    mock_save_yaml, mock_add_db, mock_llm_client, category_enum, subject_enum
):
    """
    Tests that AIQuestionGenerator can generate a question for every combination
    of QuestionCategory and QuestionSubject.
    """
    generator = AIQuestionGenerator(llm_client=mock_llm_client)

    category_str = CATEGORY_MAP[category_enum]
    subject_str = subject_enum.value

    # Generate one question for the given subject and category
    questions = generator.generate_questions(
        subject=subject_str,
        num_questions=1,
        category=category_str
    )

    # --- Assertions ---
    # 1. Check that the LLM was called
    mock_llm_client.chat_completion.assert_called_once()

    # 2. Check that we got one valid question back
    assert len(questions) == 1
    question = questions[0]
    assert isinstance(question, Question)

    # 3. Check that persistence methods were called
    mock_add_db.assert_called_once()
    mock_save_yaml.assert_called_once()

    # 4. Check that the question has the correct subject and category
    assert question.subject == subject_str
    assert question.schema_category == category_enum

    # 5. Check prompt sent to LLM contains the subject
    call_args = mock_llm_client.chat_completion.call_args
    ai_prompt = call_args[1]['messages'][0]['content']
    assert f"'{subject_str}'" in ai_prompt
