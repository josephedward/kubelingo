from click.testing import CliRunner
import pytest

from kubelingo.kubelingo import cli

@pytest.mark.skip(reason="integration")
def test_cli_study_kind_positive(monkeypatch):
    runner = CliRunner()
    # Simulate AI provider configured via env
    monkeypatch.setenv('KUBELINGO_LLM_PROVIDER', 'openai')
    # Stub out the QuestionGenerator to avoid AI calls
    from kubelingo.generation.generator import Question
    class DummyQ:
        def generate_question_set(self, count, topic=None):
            return [Question(
                id=str(n), topic=topic, difficulty=None,
                question=f"Q{n}", context_variables={},
                expected_resources=[], success_criteria=[], hints=[], scenario_context={}
            ) for n in range(count)]
    monkeypatch.setattr('kubelingo.generation.generator.QuestionGenerator', lambda: DummyQ())
    result = runner.invoke(cli, ['--study-kind', 'pods', '--study-count', '2'])
    assert result.exit_code == 0
    assert 'Question 1/2: Q0' in result.output
    assert 'Question 2/2: Q1' in result.output