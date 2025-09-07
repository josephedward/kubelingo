import builtins
import pytest

from kubelingo.cli import quiz_session


@pytest.fixture(autouse=True)
def isolate_cwd(tmp_path, monkeypatch):
    # Run each test in isolated temp directory
    monkeypatch.chdir(tmp_path)
    yield

def test_quiz_session_shows_suggested_answer_after_user_input(capfd, monkeypatch):
    # Prepare a single question with a known suggested answer
    question = {
        'id': 'test1',
        'question': 'What is Kubernetes?',
        'suggested_answer': 'A container orchestration platform.',
        'answer': 'A container orchestration platform.',
        'source': 'test_source'
    }
    # Simulate user entering a non-menu input (answer) then quitting
    inputs = iter(['my wrong answer', 'q'])
    monkeypatch.setattr(builtins, 'input', lambda *args: next(inputs))
    # Run the quiz session
    quiz_session([question])
    out = capfd.readouterr().out
    # The suggested answer must always be shown
    assert 'Suggested Answer:' in out
    assert 'A container orchestration platform.' in out

def test_quiz_session_shows_suggested_answer_on_request(capfd, monkeypatch):
    # Prepare a single question with a known suggested answer
    question = {
        'id': 'test2',
        'question': 'Define Pod.',
        'suggested_answer': 'The smallest deployable unit in Kubernetes.',
        'answer': 'The smallest deployable unit in Kubernetes.',
        'source': 'doc_source'
    }
    # Simulate user explicitly requesting suggested answer then quitting
    inputs = iter(['a', 'q'])
    monkeypatch.setattr(builtins, 'input', lambda *args: next(inputs))
    quiz_session([question])
    out = capfd.readouterr().out
    # Explicit 'answer' command should also display the suggested answer
    assert 'Suggested Answer:' in out
    assert 'The smallest deployable unit in Kubernetes.' in out