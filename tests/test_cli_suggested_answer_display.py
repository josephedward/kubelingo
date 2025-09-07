import builtins
import pytest

import kubelingo.cli as cli


@pytest.fixture(autouse=True)
def stub_dependencies(monkeypatch):
    # Stub ai_chat to prevent external calls and feedback generation
    monkeypatch.setattr(cli, 'ai_chat', lambda *args, **kwargs: '')
    # Stub handle_post_answer to exit the quiz after first question
    monkeypatch.setattr(cli, 'handle_post_answer', lambda question, questions, idx: None)
    yield


def test_quiz_session_always_shows_suggested_answer(monkeypatch, capsys):
    # Prepare a single question with a known answer
    question = {
        'question': 'What is the meaning of life?',
        'answer': '42',
        # suggested_answer key may be empty or missing, but answer should be used
        # omit suggested_answer to exercise fallback to 'answer'
    }
    # Stub input() to simulate user providing any answer and then exit
    inputs = iter(['wrong answer'])
    monkeypatch.setattr(builtins, 'input', lambda: next(inputs))

    # Run quiz_session with our single question
    cli.quiz_session([question])
    captured = capsys.readouterr()

    # Verify that the Suggested Answer header is printed
    assert 'Suggested Answer:' in captured.out
    # Verify that the actual answer value (fallback) is shown
    assert '42' in captured.out