import os
import json
import shutil
import tempfile
from click.testing import CliRunner
import pytest

from kubelingo.kubelingo import cli

@pytest.fixture(autouse=True)
def isolate_questions_dir(monkeypatch):
    # Create a temporary directory for QUESTIONS_DIR
    tmpdir = tempfile.mkdtemp()
    monkeypatch.setenv('KUBELINGO_QUESTIONS_DIR', tmpdir)
    yield tmpdir
    shutil.rmtree(tmpdir)

def test_cli_generate_ai_questions_default_topic_count(monkeypatch, isolate_questions_dir):
    runner = CliRunner()
    # Run CLI generate-kind for 'pods'
    result = runner.invoke(cli, ['--generate-kind', 'pods', '--generate-count', '3'])
    assert result.exit_code == 0
    # Should output generation message
    assert 'Generated 3 AI questions for topic' in result.output
    # Check that output file exists
    out_file = os.path.join(isolate_questions_dir, 'pods.json')
    assert os.path.isfile(out_file)
    # Load and verify JSON
    data = json.loads(open(out_file, 'r', encoding='utf-8').read())
    assert isinstance(data, list)
    assert len(data) == 3
    # Each item should have expected keys
    for item in data:
        assert 'id' in item and 'question' in item and 'topic' in item

def test_cli_generate_invalid_topic(monkeypatch, isolate_questions_dir):
    runner = CliRunner()
    # Generate with unknown topic should fallback or error gracefully
    result = runner.invoke(cli, ['--generate-kind', 'unknown_topic', '--generate-count', '2'])
    # Should still succeed but generate default questions
    assert result.exit_code == 0
    assert 'Generated 2 AI questions for topic' in result.output
    out_file = os.path.join(isolate_questions_dir, 'unknown_topic.json')
    assert os.path.isfile(out_file)
    data = json.loads(open(out_file, 'r', encoding='utf-8').read())
    assert len(data) == 2