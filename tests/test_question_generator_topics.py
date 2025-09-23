import pytest

from kubelingo.question_generator import QuestionGenerator
from kubelingo.cli_shim import KubernetesTopics


@pytest.mark.parametrize("topic", [t.value for t in KubernetesTopics])
def test_generate_question_for_each_topic(topic):
    """Test that generate_question produces a valid question for each topic without errors."""
    qg = QuestionGenerator()
    # Generate multiple questions to cover randomness
    for _ in range(5):
        question = qg.generate_question(kind=topic, count=1)
        if isinstance(question, list):
            question = question[0]
        assert isinstance(question, dict)
        assert question.get('topic') == topic
        assert 'id' in question and question['id']
        assert 'question' in question and isinstance(question['question'], str)
        assert 'context_variables' in question and isinstance(question['context_variables'], dict)
        # Ensure no duplicate IDs in same generator instance
        # IDs are managed internally; uniqueness across calls not guaranteed here
