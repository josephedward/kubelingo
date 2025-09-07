import pytest
from cli import question_generator_instance
from question_generator import KubernetesTopics
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_inquirer():
    with patch('cli.inquirer') as mock_inquirer:
        # Create a mock object for the return value of inquirer.select()
        mock_select_return = MagicMock()
        # Configure the execute() method of this mock object to return the desired string
        mock_select_return.execute.side_effect = [
            "Trivia",  # For quiz_type selection
            KubernetesTopics.CONFIGMAPS.value,  # For topic selection
        ]
        # Make inquirer.select() return our mock object
        mock_inquirer.select.return_value = mock_select_return

        # Similarly for inquirer.text()
        mock_text_return = MagicMock()
        mock_text_return.execute.side_effect = [""] * 10  # Enough for multiple questions and commands
        mock_inquirer.text.return_value = mock_text_return

        yield mock_inquirer

def test_trivia_question_diversity(mock_inquirer):
    generated_questions = []
    generated_question_ids = set()

    # Now, let's directly test the question_generator_instance's behavior
    # by calling generate_question multiple times and asserting uniqueness.
    # This is a more direct test of the fix.

    # Clear the set for this direct test
    question_generator_instance._generated_question_ids.clear()

    num_questions_to_generate = 10
    for i in range(num_questions_to_generate):
        question = question_generator_instance.generate_question(
            topic=KubernetesTopics.CONFIGMAPS.value,
            question_type="true_false" # Focus on true/false as it was the repeating type
        )
        assert question is not None
        assert "id" in question
        assert question["id"] not in generated_question_ids
        generated_question_ids.add(question["id"])
        generated_questions.append(question["question"])

    # Assert that all generated questions are unique (by text, as IDs are already checked)
    # This is important because _generate_question_id uses time, which might not be unique enough
    # if called very rapidly, but the _generated_question_ids set should catch it.
    # However, the core problem was the *same question text* repeating.
    assert len(set(generated_questions)) == num_questions_to_generate

    # Also, assert that the _generated_question_ids set in the instance
    # contains all the generated IDs.
    assert len(question_generator_instance._generated_question_ids) == num_questions_to_generate