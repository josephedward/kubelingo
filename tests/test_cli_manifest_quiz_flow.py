import pytest
import webbrowser
import kubelingo.cli as cli
from rich.console import Console

class FakeAnswer:
    """Fake answer for InquirerPy prompts."""
    def __init__(self, value):
        self._value = value
    def execute(self):
        return self.value

def test_manifest_quiz_flow(monkeypatch, capsys):
    # Mock QuestionGenerator.generate_question to return fixed data
    def mock_generate_question(topic, question_type, include_context=True):
        # Simulate printing question with context variables
        print(f"Question: Test manifest question for {topic} [test-id]")
        print("Documentation: https://example.com/doc")
        print(f"Topic: {topic}")
        print("Context Variables:")
        print("  foo: bar")
        return {
            'id': 'test-id',
            'topic': topic,
            'question_type': question_type,
            'question': f"Test manifest question for {topic} [test-id]",
            'documentation_link': 'https://example.com/doc',
            'context_variables': {'foo': 'bar'},
            'suggested_answer': 'expected-manifest'
        }
    monkeypatch.setattr(cli.QuestionGenerator, 'generate_question', mock_generate_question)
    # Prevent actual browser opens
    monkeypatch.setattr(webbrowser, 'open', lambda url: None)
    # Prepare inquirer responses: select quiz type 'Declarative (Manifests)', select topic 'pods', count '1', then 'a' for answer, then 'c' to exit
    select_responses = iter([
        'Declarative (Manifests)', # Quiz type
        'pods',                    # Topic
        'c'                        # Post-answer menu action (save as correct)
    ])
    text_responses = iter([
        '1',                       # Number of questions
        'a'                        # Answer
    ])
    monkeypatch.setattr(cli.inquirer, 'select', lambda message, choices, default=None, style=None: FakeAnswer(next(select_responses)))
    monkeypatch.setattr(cli.inquirer, 'text', lambda message: FakeAnswer(next(text_responses)))
    # Capture console.print outputs
    printed = []
    mock_console_instance = Console()
    monkeypatch.setattr(mock_console_instance, 'print', lambda *args, **kwargs: printed.append(" ".join(str(a) for a in args)))
    # Run the quiz menu for manifest flow
    cli.quiz_menu()
    # Verify order of outputs contains question, menu, solution, and post-answer menu
    # Combine captured stdout (from print) and console.print outputs
    captured = capsys.readouterr()
    combined = captured.out + "\n".join(printed)
    # Verify question output from fake_generate_question
    assert "Question: Test manifest question for pods [test-id]" in combined
    # Post-question menu should appear
    assert "v)im, c)lear, n)next, p)revious, a)nswer s)ource, q)quit" in combined
    # Solution should be printed
    assert "Solution:" in combined
    # Post-answer menu line should appear
    assert "r)etry, c)orrect, m)issed, s)ource, d)elete question" in combined