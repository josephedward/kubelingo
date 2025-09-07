import os
import json
import pytest
import kubelingo.cli as cli
from InquirerPy import inquirer
import builtins # Import builtins for monkeypatching input

@pytest.fixture(autouse=True)
def use_tmp_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    yield

@pytest.fixture
def sample_questions():
    return [
        {"question": "Q1", "answer": "A1", "id": "1"},
        {"question": "Q2", "answer": "A2", "id": "2"},
        {"question": "Q3", "answer": "A3", "id": "3"},
    ]

def test_handle_post_answer_retry(monkeypatch, sample_questions):
    monkeypatch.setattr(builtins, 'input', lambda: 'r')
    initial_index = 0
    new_index = cli.handle_post_answer(sample_questions[initial_index], sample_questions, initial_index, 'r')
    assert new_index == initial_index
    assert len(sample_questions) == 3 # Question list should not change

def test_handle_post_answer_correct(monkeypatch, sample_questions, tmp_path):
    monkeypatch.setattr(builtins, 'input', lambda: 'c')
    initial_index = 0
    # Ensure 'questions/correct' directory exists for save_question
    os.makedirs(os.path.join(tmp_path, 'questions', 'correct'), exist_ok=True)
    
    new_index = cli.handle_post_answer(sample_questions[initial_index], sample_questions, initial_index, 'c')
    assert new_index == 0 # Index should remain the same as the next question shifts
    assert len(sample_questions) == 2 # Question should be removed
    assert sample_questions[0]['id'] == '2' # Q2 should now be at index 0

def test_handle_post_answer_missed(monkeypatch, sample_questions, tmp_path):
    monkeypatch.setattr(builtins, 'input', lambda: 'm')
    initial_index = 1
    # Ensure 'questions/missed' directory exists for save_question
    os.makedirs(os.path.join(tmp_path, 'questions', 'missed'), exist_ok=True)

    new_index = cli.handle_post_answer(sample_questions[initial_index], sample_questions, initial_index, 'm')
    assert new_index == 1 % 2 # Index should be 1 % 2 = 1 (Q3 is now at index 1)
    assert len(sample_questions) == 2 # Question should be removed
    assert sample_questions[1]['id'] == '3' # Q3 should now be at index 1

def test_handle_post_answer_delete(monkeypatch, sample_questions):
    monkeypatch.setattr(builtins, 'input', lambda: 'd')
    initial_index = 2
    new_index = cli.handle_post_answer(sample_questions[initial_index], sample_questions, initial_index, 'd')
    assert new_index == 0 # Index should wrap around to 0 if last question removed
    assert len(sample_questions) == 2 # Question should be removed
    assert sample_questions[0]['id'] == '1' # Q1 should still be at index 0

def test_handle_post_answer_advance_empty_input(monkeypatch, sample_questions):
    monkeypatch.setattr(builtins, 'input', lambda: '') # Simulate pressing Enter
    initial_index = 0
    new_index = cli.handle_post_answer(sample_questions[initial_index], sample_questions, initial_index, '')
    assert new_index == 1 # Should advance to the next question
    assert len(sample_questions) == 3 # Question list should not change

def test_handle_post_answer_last_question_removed(monkeypatch):
    questions = [{"question": "Q1", "answer": "A1", "id": "1"}]
    monkeypatch.setattr(builtins, 'input', lambda: 'c')
    # Ensure 'questions/correct' directory exists for save_question
    os.makedirs(os.path.join(os.getcwd(), 'questions', 'correct'), exist_ok=True)

    new_index = cli.handle_post_answer(questions[0], questions, 0, 'c')
    assert new_index is None # Should return None as no questions left
    assert len(questions) == 0 # Question should be removed

def test_quiz_session_advancement(monkeypatch, capsys, sample_questions):
    # Simulate user typing "my answer" then pressing Enter for post-answer menu
    # Then type "q" to quit after the first question
    user_inputs = iter(["my answer", "q"])
    monkeypatch.setattr(builtins, 'input', lambda: next(user_inputs))

    cli.quiz_session(sample_questions)

    captured = capsys.readouterr()
    assert "Quiz session finished." in captured.out
    assert "Question: Q1" in captured.out
    assert "Question: Q2" in captured.out # Corrected assertion
    assert "Question: Q3" not in captured.out # Q3 should not be displayed
    assert len(sample_questions) == 3 # Questions are not removed by free-form answer

def test_quiz_session_all_questions_answered(monkeypatch, capsys, sample_questions):
    # Simulate answering all questions with free-form answers, then quit
    user_inputs = iter(["ans1", "", "ans2", "", "ans3", "", "q"]) # Answer, then Enter for each question, then quit
    monkeypatch.setattr(builtins, 'input', lambda: next(user_inputs))

    cli.quiz_session(sample_questions)

    captured = capsys.readouterr()
    assert "Quiz session finished." in captured.out
    assert "Question: Q1" in captured.out
    assert "Question: Q2" in captured.out
    assert "Question: Q3" in captured.out
    assert len(sample_questions) == 3 # Questions are not removed by free-form answer
