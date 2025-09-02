import os
import yaml
import webbrowser
import pytest

import kubelingo.question_manager as qm

class DummySession:
    def __init__(self):
        self.calls = []
    def update_performance(self, question, is_correct, get_norm_fn):
        self.calls.append((question, is_correct))
        return True

def test_mark_correct(monkeypatch, capsys):
    session = DummySession()
    question = {'question': 'Q1'}
    perf_data = {'topic': {'correct_questions': []}}
    # Patch save_performance_data to track calls
    saved = {}
    def fake_save(data):
        saved['data'] = data
    monkeypatch.setattr(qm, 'save_performance_data', fake_save)
    # Call mark_correct
    qm.mark_correct(session, question, perf_data, lambda q: q['question'])
    # Assert session.update_performance called
    assert session.calls == [(question, True)]
    # Assert save_performance_data called with perf_data
    assert saved.get('data') is perf_data
    out = capsys.readouterr().out
    assert 'Question marked correct' in out

def test_mark_incorrect_creates_missed_file(tmp_path, monkeypatch, capsys):
    # Setup path
    miss_file = tmp_path / 'missed.yaml'
    monkeypatch.setattr(qm, 'MISSED_QUESTIONS_FILE', str(miss_file))
    monkeypatch.setattr(qm, 'ensure_user_data_dir', lambda: None)
    # First mark
    question = {'question': 'Test Q'}
    qm.mark_incorrect(question, 'topic1')
    data = yaml.safe_load(miss_file.read_text())
    assert isinstance(data, list) and len(data) == 1
    assert data[0]['question'] == 'Test Q'
    # Second mark (duplicate) should not add
    qm.mark_incorrect(question, 'topic1')
    data2 = yaml.safe_load(miss_file.read_text())
    assert len(data2) == 1
    out = capsys.readouterr().out
    assert 'Question added to missed questions' in out

def test_mark_revisit_calls_issue_manager(monkeypatch, capsys):
    called = {}
    def fake_create_issue(q, topic):
        called['q'] = q; called['topic'] = topic
    monkeypatch.setattr(qm.im, 'create_issue', fake_create_issue)
    question = {'question': 'Q'}
    qm.mark_revisit(question, 'topicX')
    assert called == {'q': question, 'topic': 'topicX'}
    out = capsys.readouterr().out
    assert 'flagged for revisit' in out

def test_mark_delete_calls_remove_question(monkeypatch, capsys):
    # Patch remove_question_from_corpus in kubelingo.kubelingo
    import kubelingo.kubelingo as kg
    monkeypatch.setattr(kg, 'remove_question_from_corpus', lambda q, t: called.update({'q': q, 't': t}))
    called = {}
    question = {'question': 'Qdel'}
    qm.mark_delete(question, 'topicD')
    assert called == {'q': question, 't': 'topicD'}
    out = capsys.readouterr().out
    assert 'Question deleted' in out

def test_open_source_prefers_question_source(monkeypatch, capsys):
    question = {'source': 'http://example.com'}
    monkeypatch.setattr(webbrowser, 'open', lambda url: called.append(url))
    called = []
    qm.open_source(question)
    assert called == ['http://example.com']
    out = capsys.readouterr().out
    assert '🔗 Opening source' in out

def test_open_source_fallback_from_kind(monkeypatch, capsys):
    question = {'requirements': {'kind': 'Pod'}, 'source': None}
    expected = qm.get_source_for_kind('Pod') if hasattr(qm, 'get_source_for_kind') else None
    called = []
    monkeypatch.setattr(webbrowser, 'open', lambda url: called.append(url))
    qm.open_source(question)
    assert called == [expected]

def test_show_menu_outputs(capsys):
    qm.show_menu()
    out = capsys.readouterr().out
    assert 'A) Again' in out
    assert 'F) Forward' in out
    assert 'C) Correct' in out
    assert 'Q) Quit app' in out