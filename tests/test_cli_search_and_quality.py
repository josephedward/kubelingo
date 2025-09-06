import os
import pytest
from click.testing import CliRunner

import kubelingo.question_search as qs
from kubelingo.kubelingo import cli, TOPIC_SEARCH_MAPPING

def test_search_for_quality_questions_calls_search_for_each_topic(monkeypatch):
    # Record calls to search_for_questions
    calls = []
    def fake_search(topic_name, question_type=None, subject=None):
        calls.append((topic_name, question_type, subject))
        return []
    monkeypatch.setattr(qs, 'search_for_questions', fake_search)
    # Execute quality search
    qs.search_for_quality_questions()
    # Determine expected topics (skip None mappings)
    expected_topics = [t for t, info in qs.TOPIC_REPO_MAPPING.items() if info is not None]
    called_topics = set([c[0] for c in calls])
    assert set(expected_topics) == called_topics
    # For manifest topics, ensure calls for each subject
    for topic_name, info in qs.TOPIC_REPO_MAPPING.items():
        if info is None:
            continue
        qtype = info.get('question_type')
        subjects = info.get('subjects')
        if qtype == 'manifest' and subjects:
            # Should be called for each subject
            subj_calls = [c for c in calls if c[0] == topic_name]
            called_subjects = sorted(set([c[2] for c in subj_calls]))
            assert sorted(subjects) == called_subjects
        else:
            # Single call with subject=None
            subj_calls = [c for c in calls if c[0] == topic_name]
            assert len(subj_calls) == 1
            assert subj_calls[0][2] is None

def test_cli_search_flag_invokes_search_for_quality_questions(monkeypatch):
    runner = CliRunner()
    called = []
    # Monkeypatch search_for_quality_questions to record invocation
    def fake_quality():
        called.append(True)
    monkeypatch.setattr(qs, 'search_for_quality_questions', fake_quality)
    # Invoke CLI with --search flag
    result = runner.invoke(cli, ['--search'])
    # Should call our fake_quality and exit code 0
    assert called, "search_for_quality_questions was not called"
    assert result.exit_code == 0

def test_topic_search_mapping_question_types_valid():
    # Ensure TOPIC_SEARCH_MAPPING has valid question_type values
    valid = {'command', 'manifest'}
    for topic, info in TOPIC_SEARCH_MAPPING.items():
        qtype = info.get('question_type')
        assert qtype in valid, f"Invalid question_type '{qtype}' for topic '{topic}'"