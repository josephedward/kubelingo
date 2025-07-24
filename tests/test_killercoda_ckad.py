import os
import csv
import argparse
import logging
import subprocess

import pytest

from kubelingo.modules.killercoda_ckad.session import NewSession
import kubelingo.modules.killercoda_ckad.session as session_mod


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

    logger = logging.getLogger('killercoda_ckad_test')
    session = NewSession(logger=logger)
    args = argparse.Namespace()

    session.initialize()
    session.run_exercises(args)
    captured = capsys.readouterr().out

    # Verify quiz output (strip ANSI color codes for assertions)
    import re
    clean = re.sub(r'\x1b\[[0-9;]*m', '', captured)
    assert "Killercoda CKAD Quiz" in clean
    assert "Quiz Complete" in clean
    total = len(questions)
    # Summary should report results (matching the total questions count)
    assert f"out of {total}" in clean

def test_multi_step_prompt_template(monkeypatch, questions, capsys):
    """Ensure prompts are rendered as full instructions with answer area"""
    call_count = {'i': 0}
    total = len(questions)
    multi_indices = [idx for idx, (prompt, _) in enumerate(questions) if '\n' in prompt]
    if not multi_indices:
        pytest.skip("No multi-step prompts, skipping multi-step template test")

    def fake_call(cmd, *args, **kwargs):
        tmp_path = cmd[-1]
        idx = call_count['i']
        prompt, expected = questions[idx]
        # Read the pre-filled template
        with open(tmp_path, encoding='utf-8') as f:
            content = f.read()
        # For multi-line prompts, expect full instructions and YAML stub
        if idx in multi_indices:
            # For multi-line prompts, combined into a single instruction line
            lines = [line.strip() for line in prompt.splitlines() if line.strip()]
            single = " ".join(lines)
            assert content.startswith("# Instructions:"), "Missing instructions header"
            assert f"# {single}" in content, f"Missing combined instruction: {single}"
            assert "# Your YAML manifest below:" in content, "Missing YAML stub indicator"
        # Write the expected answer back into the file
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write(expected)
        call_count['i'] += 1
        return 0

    # Patch the subprocess.call used in the session module to intercept editor launches
    monkeypatch.setattr(
        session_mod.subprocess,
        'call',
        fake_call,
        raising=True,
    )
    logger = logging.getLogger('killercoda_multistep_test')
    session = NewSession(logger=logger)
    args = argparse.Namespace()
    session.initialize()
    session.run_exercises(args)
    capsys.readouterr()
    assert call_count['i'] == total