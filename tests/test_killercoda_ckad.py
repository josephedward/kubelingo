import os
import csv
import argparse
import logging
import subprocess

import pytest

from kubelingo.modules.kubernetes.session import NewSession


@pytest.fixture(scope="module")
def questions():
    # Load and parse CSV to extract prompts and answers
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    csv_file = os.path.join(root, 'killercoda-ckad_072425.csv')
    questions = []
    with open(csv_file, newline='') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 3:
                continue
            raw_prompt = row[1].strip()
            if raw_prompt.startswith("'") and raw_prompt.endswith("'"):
                raw_prompt = raw_prompt[1:-1].strip()
            raw_answer = row[2].strip()
            if raw_answer.startswith("'") and raw_answer.endswith("'"):
                raw_answer = raw_answer[1:-1].strip()
            if not raw_prompt or not raw_answer:
                continue
            questions.append((raw_prompt, raw_answer))
    assert questions, "No questions found in CSV"
    return questions

def test_parse_csv_has_questions(questions):
    # Ensure at least one question was parsed
    assert len(questions) > 0


def test_all_questions_are_single_line(questions):
    """Ensure all question prompts and answers are single-line strings."""
    for prompt, answer in questions:
        assert '\n' not in prompt, f"Multi-line prompt found: {prompt!r}"
        assert '\n' not in answer, f"Multi-line answer found: {answer!r}"


def test_run_exercises_e2e(monkeypatch, capsys, questions):
    # Simulate correct user answers by writing expected content via fake editor
    call_index = {'i': 0}

    def fake_call(cmd, *args, **kwargs):
        # cmd is [editor, tmp_path]
        tmp_path = cmd[-1]
        _, expected = questions[call_index['i']]
        with open(tmp_path, 'w') as f:
            f.write(expected)
        call_index['i'] += 1
        return 0

    monkeypatch.setattr(subprocess, 'call', fake_call)

    # Mock questionary to automate answering
    class MockQuestionary:
        def __init__(self, returns):
            self._returns = iter(returns)
        def ask(self):
            try:
                return next(self._returns)
            except StopIteration:
                return None

    # For each question, simulate: 1. Answer, 2. Check
    questionary_returns = []
    for _ in questions:
        questionary_returns.extend(["answer", "check"])

    def mock_select(*args, **kwargs):
        return MockQuestionary(questionary_returns)

    monkeypatch.setattr("kubelingo.modules.kubernetes.session.questionary.select", mock_select)

    logger = logging.getLogger('killercoda_ckad_test')
    session = NewSession(logger=logger)
    # The killercoda quiz uses these args, provide defaults for the test.
    args = argparse.Namespace(num=0, randomize=False, category=None)

    # The logic was moved to a private method, so we test it directly
    session._run_killercoda_ckad(args)
    captured = capsys.readouterr().out

    # Verify quiz output (strip ANSI color codes for assertions)
    import re
    clean = re.sub(r'\x1b\[[0-9;]*m', '', captured)
    assert "Killercoda CKAD CSV Quiz" in clean
    assert "Quiz Complete" in clean
    total = len(questions)
    # Summary should report results for all questions answered
    assert f"out of {total}" in clean

