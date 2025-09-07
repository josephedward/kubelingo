import pytest
import webbrowser
import cli

class FakeAnswer:
    """Fake answer for InquirerPy prompts."""
    def __init__(self, value):
        self._value = value
    def execute(self):
        return self._value

def test_manifest_quiz_flow(monkeypatch, capsys):
    # Stub generate_question to print a known manifest question and return fixed data
    def fake_generate_question(topic, gen=None):
        # Simulate printing question with context variables
        print(f"Question: Test manifest question for {topic} [test-id]")
        print("Documentation: https://example.com/doc")
        print(f"Topic: {topic}")
        print("Context Variables:")
        print("  foo: bar")
        return {
            'id': 'test-id',
            'topic': topic,
            'question': f"Test manifest question for {topic} [test-id]",
            'documentation_link': 'https://example.com/doc',
            'context_variables': {'foo': 'bar'},
            'suggested_answer': 'expected-manifest'
        }
    monkeypatch.setattr(cli, 'generate_question', fake_generate_question)
    # Prevent actual browser opens
    monkeypatch.setattr(webbrowser, 'open', lambda url: None)
    # Prepare inquirer responses: select quiz type 'Manifest', select topic 'pods', then 'a' for answer, then 'c' to exit
    select_responses = ['Manifest', 'pods']
    text_responses = ['a', 'c']
    def fake_select(message, *args, **kwargs):
        if not select_responses:
            pytest.fail(f"No more select responses for prompt: {message}")
        return FakeAnswer(select_responses.pop(0))
    def fake_text(message, *args, **kwargs):
        if not text_responses:
            pytest.fail(f"No more text responses for prompt: {message}")
        return FakeAnswer(text_responses.pop(0))
    monkeypatch.setattr(cli.inquirer, 'select', fake_select)
    monkeypatch.setattr(cli.inquirer, 'text', fake_text)
    # Capture console.print outputs
    printed = []
    monkeypatch.setattr(cli.console, 'print', lambda *args, **kwargs: printed.append(" ".join(str(a) for a in args)))
    # Run the quiz menu for manifest flow
    cli.quiz_menu()
    # Verify order of outputs contains question, menu, solution, and post-answer menu
    # Combine captured stdout (from print) and console.print outputs
    captured = capsys.readouterr()
    combined = captured.out + "\n".join(printed)
    # Verify question output from fake_generate_question
    assert "Question: Test manifest question for pods [test-id]" in combined
    # Post-question menu should appear
    assert cli.QUESTION_MENU_LINE in combined
    # Solution should be printed
    assert "Solution:" in combined
    # Post-answer menu line should appear
    post_answer_line = cli.MENU_DEFINITIONS['post_answer']['line']
    assert post_answer_line in combined