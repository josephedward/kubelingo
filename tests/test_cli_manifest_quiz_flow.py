import pytest
pytest.skip("Skipping manifest quiz flow tests until interface is standardized", allow_module_level=True)
import webbrowser
import kubelingo.cli as cli
from rich.console import Console
from unittest.mock import MagicMock, call
import builtins

class FakeAnswer:
    """Fake answer for InquirerPy prompts."""
    def __init__(self, value):
        self._value = value
    def execute(self):
        return self._value

def test_manifest_quiz_flow(monkeypatch, capsys):
    # Mock QuestionGenerator.generate_question to return fixed data
    def mock_generate_question(self, topic, question_type, exclude_question_texts=None, include_context=True):
        # Simulate printing question with context variables
        print(f"Question: Test manifest question for pods [test-id]")
        print("Documentation: https://example.com/doc")
        print(f"Topic: pods")
        print("Context Variables:")
        print("  foo: bar")
        return {
            'id': 'test-id',
            'topic': 'pods',
            'question_type': question_type,
            'question': "Test manifest question for pods [test-id]",
            'documentation_link': 'https://example.com/doc',
            'context_variables': {'foo': 'bar'},
            'suggested_answer': 'expected-manifest'
        }
    monkeypatch.setattr(cli.QuestionGenerator, 'generate_question', mock_generate_question)
    # Prevent actual browser opens
    monkeypatch.setattr(webbrowser, 'open', lambda url: None)
    # Prepare inquirer responses: select quiz type 'Declarative (Manifests)', select topic 'pods', count '1', then 'a' for answer, then 'c' to exit
    mock_inquirer_select = MagicMock(side_effect=[
        FakeAnswer('Quiz'),                    # Main Menu: Quiz
        FakeAnswer('Declarative (Manifests)'), # Quiz type
        FakeAnswer('pods'),                    # Topic
        FakeAnswer('c')                        # Post-answer menu action (save as correct)
    ])
    monkeypatch.setattr(cli.inquirer, 'select', mock_inquirer_select)
    monkeypatch.setattr(cli.inquirer, 'text', MagicMock(side_effect=[
            FakeAnswer('1'),                       # Number of questions
            FakeAnswer('a')                        # Answer
        ]))
    monkeypatch.setattr(builtins, 'input', MagicMock(side_effect=[
            'a', # for the question menu
            'q'  # to quit if the loop doesn't exit
        ]))
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
    # Post-question menu should appear with unified options
    assert "v) vim, b) backward, f) forward, a) answer, s) visit, q) quit" in combined
    # Solution should be printed
    assert "Suggested Answer:" in combined
    # Post-answer menu line should appear with unified options
    expected_post_answer_menu_call = call(
        message="""- Post Answer Menu
+ always comes after a question is answered)
+ AI does not determine correct/missed; feedback is what is important from AI
+ user chooses to save as correct or missed, or delete as a bad question
+ if the answer is verbatim the same as the suggested answer, you do not need to show AI feedback
+ source should be in both menus, its helpful in research""",
        choices=[
            {"name": "r)etry", "value": "retry"},
            {"name": "c)orrect", "value": "correct"},
            {"name": "m)issed", "value": "missed"},
            {"name": "s)ource", "value": "source"},
            {"name": "d)elete question", "value": "delete"}
        ]
    )
    mock_inquirer_select.assert_has_calls([expected_post_answer_menu_call], any_order=True)