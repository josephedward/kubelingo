import os
import csv
import argparse
import logging

import pytest

from kubelingo.modules.killercoda_ckad.session import NewSession
import kubelingo.modules.killercoda_ckad.session as kc_sess


def test_multistep_template(tmp_path, monkeypatch, capsys):
    # Create a CSV with a two-step prompt and a two-line answer
    csv_path = tmp_path / 'test_killercoda.csv'
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        # row: [*, prompt, answer]
        writer.writerow(['', 'Step1\nStep2', 'cmd1\ncmd2'])

    # Override CSV path
    monkeypatch.setenv('KILLERCODA_CSV', str(csv_path))

    # Prepare a dummy temp file to capture template output
    template_file = tmp_path / 'template.txt'
    class DummyTempFile:
        def __init__(self, mode='w', delete=False, suffix=None):
            self.name = str(template_file)
        def close(self):
            pass

    # Monkeypatch NamedTemporaryFile, subprocess.call, and unlink to preserve template
    monkeypatch.setattr(kc_sess.tempfile, 'NamedTemporaryFile', DummyTempFile)
    monkeypatch.setattr(kc_sess.subprocess, 'call', lambda *args, **kwargs: 0)
    monkeypatch.setattr(kc_sess.os, 'unlink', lambda path: None)

    # Run the session
    session = NewSession(logger=logging.getLogger('test'))
    args = argparse.Namespace()
    assert session.initialize() is True
    session.run_exercises(args)

    # Read the generated template and verify it shows instructions and YAML stub
    content = template_file.read_text().splitlines()
    # First line should be the instructions header
    assert content[0] == '# Instructions:'
    # Next line should combine the prompt lines into one instruction
    assert content[1] == '# Step1 Step2'
    # Should include a YAML manifest stub indicator
    assert any(line.strip() == '# Your YAML manifest below:' for line in content)