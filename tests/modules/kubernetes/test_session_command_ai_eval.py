import os
import tempfile
from pathlib import Path
import pytest

from types import SimpleNamespace
import logging

# Import the session class
from kubelingo.modules.kubernetes.session import NewSession

@pytest.fixture(autouse=True)
def ensure_api_key(monkeypatch):
    # Ensure an API key is present for AI evaluation path
    monkeypatch.setenv('OPENAI_API_KEY', 'testkey')
    yield
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)

class DummyAIEvaluator:
    def evaluate(self, question, transcript):
        # Always mark correct with a dummy reasoning
        return {'correct': True, 'reasoning': 'AI says good'}

@pytest.fixture(autouse=True)
def stub_ai_evaluator(monkeypatch):
    # Stub out the AI evaluator to use our dummy
    import kubelingo.modules.ai_evaluator as ai_mod
    monkeypatch.setattr(ai_mod, 'AIEvaluator', lambda: DummyAIEvaluator())
    yield

def test_ai_evaluation_command(monkeypatch, capsys):
    # Prepare a temporary transcript file
    tmpdir = tempfile.TemporaryDirectory()
    transcript_file = Path(tmpdir.name) / 'transcript.log'
    transcript_file.write_text('dummy transcript')

    # Create a dummy result object with a transcript_path attribute
    result = SimpleNamespace(transcript_path=str(transcript_file), success=False)

    # Create a simple command question dict
    question = {
        'id': 'q1',
        'type': 'command',
        'answers': ['echo hello'],
        'validation_steps': []
    }

    # Instantiate session with a dummy logger
    session = NewSession(logger=logging.getLogger('test'))
    attempted = set()
    correct = set()

    # Call the private answer processing method
    # args is not used for AI path, but signature requires it
    args = SimpleNamespace(ai_eval=True)
    session._check_and_process_answer(args, question, result, 0, attempted, correct)

    # Capture output and assert AI evaluation was invoked
    out = capsys.readouterr().out
    assert 'AI Evaluation: Correct - AI says good' in out
    assert 0 in correct
    tmpdir.cleanup()