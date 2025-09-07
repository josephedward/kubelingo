import pytest

from cli import suggest_command
from question_generator import QuestionGenerator, KubernetesTopics


@pytest.mark.parametrize("topic", [t.value for t in KubernetesTopics])
def test_suggest_command_handles_empty_vars(topic):
    """Test that suggest_command doesn't raise and returns a string even with empty vars."""
    suggestion = suggest_command(topic, {})
    assert isinstance(suggestion, str)


def test_suggest_command_with_context_vars():
    """Test suggest_command with actual context variables derived from templates."""
    qg = QuestionGenerator()
    for topic in KubernetesTopics:
        templates = qg.question_templates.get(topic.value, [])
        for template in templates:
            ctx = qg._generate_context_variables(template)
            # skip if no vars required
            try:
                suggestion = suggest_command(topic.value, ctx)
            except Exception as e:
                pytest.fail(f"suggest_command raised {e} for topic {topic.value} with vars {ctx}")
            assert isinstance(suggestion, str)