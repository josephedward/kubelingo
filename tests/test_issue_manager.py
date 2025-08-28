import os
import yaml
import time
import pytest

from kubelingo import issue_manager


def test_get_normalized_question_text():
    assert issue_manager.get_normalized_question_text({'question': '  Hello World  '}) == 'hello world'
    assert issue_manager.get_normalized_question_text({}) == ''


def test_ensure_user_data_dir(tmp_path, monkeypatch):
    test_dir = tmp_path / "user_data_dir"
    monkeypatch.setattr(issue_manager, 'USER_DATA_DIR', str(test_dir))
    # Directory should not exist initially
    assert not test_dir.exists()
    issue_manager.ensure_user_data_dir()
    assert test_dir.exists() and test_dir.is_dir()


def test_remove_question_from_list_no_file(tmp_path, monkeypatch):
    list_file = tmp_path / "list.yaml"
    # Redirect USER_DATA_DIR so ensure_user_data_dir does not interfere
    user_data = tmp_path / "dummy"
    monkeypatch.setattr(issue_manager, 'USER_DATA_DIR', str(user_data))
    # Remove a question from a non-existent list
    question = {'question': 'Q1'}
    issue_manager.remove_question_from_list(str(list_file), question)
    # File should be created with an empty list
    assert list_file.exists()
    data = yaml.safe_load(list_file.read_text())
    assert data == []


def test_remove_question_from_list_existing(tmp_path, monkeypatch):
    list_file = tmp_path / "list.yaml"
    user_data = tmp_path / "dummy"
    monkeypatch.setattr(issue_manager, 'USER_DATA_DIR', str(user_data))
    # Write initial YAML with two questions
    original = [{'question': 'Q1'}, {'question': 'Q2'}]
    list_file.write_text(yaml.dump(original))
    # Remove Q1 (case/whitespace insensitive)
    issue_manager.remove_question_from_list(str(list_file), {'question': ' q1 '})
    updated = yaml.safe_load(list_file.read_text())
    assert updated == [{'question': 'Q2'}]


def test_remove_question_from_list_bad_yaml(tmp_path, monkeypatch):
    list_file = tmp_path / "list.yaml"
    user_data = tmp_path / "dummy"
    monkeypatch.setattr(issue_manager, 'USER_DATA_DIR', str(user_data))
    # Write invalid YAML
    list_file.write_text(":::")
    # Should not raise, and file reset to empty list
    issue_manager.remove_question_from_list(str(list_file), {'question': 'anything'})
    data = yaml.safe_load(list_file.read_text())
    assert data == []


def test_create_issue_cancel(tmp_path, monkeypatch, capsys):
    issues_file = tmp_path / "issues.yaml"
    missed_file = tmp_path / "missed.yaml"
    questions_dir = tmp_path / "questions"
    user_data = tmp_path / "user_data"
    monkeypatch.setattr(issue_manager, 'ISSUES_FILE', str(issues_file))
    monkeypatch.setattr(issue_manager, 'MISSED_QUESTIONS_FILE', str(missed_file))
    monkeypatch.setattr(issue_manager, 'QUESTIONS_DIR', str(questions_dir))
    monkeypatch.setattr(issue_manager, 'USER_DATA_DIR', str(user_data))
    # Simulate empty input
    monkeypatch.setattr('builtins.input', lambda prompt='': '   ')
    issue_manager.create_issue({'question': 'Test'}, 'topic1')
    out = capsys.readouterr().out
    assert "Issue reporting cancelled" in out
    assert not issues_file.exists()


def test_create_issue_success(tmp_path, monkeypatch, capsys):
    issues_file = tmp_path / "issues.yaml"
    missed_file = tmp_path / "missed.yaml"
    questions_dir = tmp_path / "questions"
    user_data = tmp_path / "user_data"
    monkeypatch.setattr(issue_manager, 'ISSUES_FILE', str(issues_file))
    monkeypatch.setattr(issue_manager, 'MISSED_QUESTIONS_FILE', str(missed_file))
    monkeypatch.setattr(issue_manager, 'QUESTIONS_DIR', str(questions_dir))
    monkeypatch.setattr(issue_manager, 'USER_DATA_DIR', str(user_data))
    # Prepare existing invalid issues file to hit YAML error branch
    issues_file.write_text(":::")
    # Prepare missed questions list
    missed = [{'question': 'Test Q'}, {'question': 'Other Q'}]
    missed_file.write_text(yaml.dump(missed))
    # Prepare topic file with two questions
    topic = 'topic1'
    questions_dir.mkdir(parents=True, exist_ok=True)
    topic_file = questions_dir / f"{topic}.yaml"
    original = {'questions': [{'question': 'Test Q'}, {'question': 'Another Q'}]}
    topic_file.write_text(yaml.dump(original))
    # Monkey-patch input and timestamp
    monkeypatch.setattr('builtins.input', lambda prompt='': 'My issue description')
    monkeypatch.setattr(time, 'asctime', lambda: 'TESTTIME')
    # Run
    issue_manager.create_issue({'question': 'Test Q'}, topic)
    # Verify issues file content
    issues = yaml.safe_load(issues_file.read_text())
    assert isinstance(issues, list) and len(issues) == 1
    new = issues[0]
    assert new['question'] == 'Test Q'
    assert new['issue'] == 'My issue description'
    assert new['timestamp'] == 'TESTTIME'
    assert new['topic'] == topic
    # Verify topic file updated
    data = yaml.safe_load(topic_file.read_text())
    assert data.get('questions') == [{'question': 'Another Q'}]
    # Verify missed questions updated
    updated_missed = yaml.safe_load(missed_file.read_text())
    assert updated_missed == [{'question': 'Other Q'}]
    # Verify output
    out = capsys.readouterr().out
    assert "Issue reported. Thank you!" in out


def test_create_issue_topic_removal_exception(tmp_path, monkeypatch, capsys):
    issues_file = tmp_path / "issues.yaml"
    missed_file = tmp_path / "missed.yaml"
    questions_dir = tmp_path / "questions"
    user_data = tmp_path / "user_data"
    monkeypatch.setattr(issue_manager, 'ISSUES_FILE', str(issues_file))
    monkeypatch.setattr(issue_manager, 'MISSED_QUESTIONS_FILE', str(missed_file))
    monkeypatch.setattr(issue_manager, 'QUESTIONS_DIR', str(questions_dir))
    monkeypatch.setattr(issue_manager, 'USER_DATA_DIR', str(user_data))
    # Create a topic file
    topic = 'topic2'
    questions_dir.mkdir(parents=True, exist_ok=True)
    topic_file = questions_dir / f"{topic}.yaml"
    topic_file.write_text(yaml.dump({'questions': [{'question': 'QX'}]}))
    # Simulate user input and timestamp
    monkeypatch.setattr('builtins.input', lambda prompt='': 'Desc')
    monkeypatch.setattr(time, 'asctime', lambda: 'TT')
    # Monkey-patch YAML safe_load to raise exception for topic removal
    def bad_safe_load(_):
        raise Exception("boom")
    monkeypatch.setattr(issue_manager.yaml, 'safe_load', bad_safe_load)
    # Run; should not raise
    issue_manager.create_issue({'question': 'QX'}, topic)
    # Issues file should be written
    # Use full_load here since safe_load was patched above
    issues = yaml.full_load(issues_file.read_text())
    assert issues[0]['question'] == 'QX'
    # Topic file should remain (exception in removal is suppressed)
    assert topic_file.exists()
    # Output indicates success
    out = capsys.readouterr().out
    assert "Issue reported. Thank you!" in out