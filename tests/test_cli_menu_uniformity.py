import builtins
import pytest
import kubelingo.cli as cli

class DummyPrompt:
    """Dummy prompt for InquirerPy select executions."""
    def __init__(self, value):
        self._value = value
    def execute(self):
        return self._value

@pytest.mark.parametrize("question", [
    # Free-text style question (no choices)
    {
        'question': 'Define Kubernetes',
        'suggested_answer': 'An open-source container orchestration system.',
        'source': 'doc',
        'id': 'q1',
        'question_type': 'vocab'
    },
    # Multiple-choice style question
    {
        'question': 'Select B',
        'choices': ['A', 'B', 'C'],
        'suggested_answer': 'B',
        'source': 'doc',
        'id': 'q2',
        'question_type': 'multiple choice'
    }
])
def test_question_and_post_answer_menu_uniform(monkeypatch, capsys, question):
    # Stub post_answer_menu to simulate user choice and exit
    monkeypatch.setattr(cli, 'post_answer_menu', lambda *args, **kwargs: 'do not save question')
    # Stub inquirer.select to avoid interactive prompts
    monkeypatch.setattr(cli.inquirer, 'select', lambda *args, **kwargs: DummyPrompt('do not save question'))
    # Stub input to simulate answer command
    monkeypatch.setattr(builtins, 'input', lambda: 'a')

    # Run quiz session with the single test question
    cli.quiz_session([question.copy()])
    out = capsys.readouterr().out

    # The question menu should always display the same options
    assert 'v) vim, b) backward, f) forward, a) answer, s) visit, q) quit' in out

    # After answering, the static post-answer menu should be printed identically
    assert 'r)etry, c)orrect, m)issed, s)ource, d)elete question' in out