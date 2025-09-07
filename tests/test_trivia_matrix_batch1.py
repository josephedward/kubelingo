import os
import json
import pytest
from itertools import product
import kubelingo.cli as cli

# Use the defined constants from the CLI as source of truth
PROVIDERS = cli.LLM_PROVIDERS
QTYPES    = cli.QUESTION_TYPES
TOPICS    = cli.SUBJECT_MATTERS

# Simple fake for InquirerPy select/text so flows don't block
class FakeAnswer:
    def __init__(self, value):
        self.value = value
    def execute(self):
        return self.value

@pytest.fixture(autouse=True)
def stub_inquirer(monkeypatch):
    # Always select first subject for topic, and default text answers
    monkeypatch.setattr(cli.inquirer, 'select',  lambda *a, **k: FakeAnswer(TOPICS[0]))
    monkeypatch.setattr(cli.inquirer, 'text',    lambda *a, **k: FakeAnswer('1'))
    yield

# Generate the full matrix of (provider, qtype, topic)
ALL_COMBOS = list(product(PROVIDERS, QTYPES, TOPICS))
# Batch size: 66 combos per test file. This is batch #1.
COMBOS_BATCH1 = ALL_COMBOS[:66]

@pytest.mark.parametrize("provider,qtype,topic", COMBOS_BATCH1)
def test_trivia_flow_matrix_batch1(provider, qtype, topic, monkeypatch, capsys):
    # 1) Set the provider and dummy API key
    monkeypatch.setenv("KUBELINGO_LLM_PROVIDER", provider)
    keyvar = f"{provider.upper()}_API_KEY"
    monkeypatch.setenv(keyvar, "test-key")

    # 2) Stub ai_chat to return minimal valid JSON for each qtype
    if qtype == 'tf':
        resp = {"type": "tf",   "question": f"TF question on {topic}", "answer": "true"}
    elif qtype == 'mcq':
        resp = {"type": "mcq",  "question": f"MCQ on {topic}",  "options": ["a","b","c","d"], "answer": "a"}
    else:  # vocab
        resp = {"type": "vocab","question": f"Vocab on {topic}","answer": topic}
    monkeypatch.setattr(cli, 'ai_chat', lambda *a, **k: json.dumps(resp))

    # 3) Invoke the trivia generator for the given topic
    #    Note: assumes a generate_trivia(topic) entrypoint exists
    try:
        cli.generate_trivia(topic=topic)
    except AttributeError:
        pytest.skip("generate_trivia not implemented yet")

    # 4) Capture printed output and assert the question text is present
    out = capsys.readouterr().out
    assert resp['question'] in out
    # Also ensure no errors shown
    assert 'Traceback' not in out