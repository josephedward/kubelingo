import kubelingo.cli as cli
from kubelingo import llm_utils
from kubelingo.question_generator import QuestionGenerator
import builtins

class DummyPrompt:
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value

class FakeAnswer:
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value

def test_quiz_menu_generates_ai_question(monkeypatch, capsys):
    # Mock inquirer.select for quiz type, topic, and difficulty
    select_choices = iter([
        "True/False",  # Quiz type selection
        "pods"         # Topic selection
    ])
    monkeypatch.setattr(cli.inquirer, 'select', lambda message, choices, default=None, style=None: DummyPrompt(next(select_choices)))

    # Mock inquirer.text for number of questions
    monkeypatch.setattr(cli.inquirer, 'text', lambda message: FakeAnswer("1"))

    # Mock input() for quiz_session
    input_choices = iter([
        "a", # Answer the question
        "s", # Select source option
        "q"  # Quit the quiz session
    ])
    monkeypatch.setattr(builtins, 'input', lambda: next(input_choices))

    # Mock ai_chat to return a valid question
    def mock_ai_chat(system_prompt, user_prompt):
        return '{"question": "Is Kubernetes an open-source container orchestration system?", "expected_resources": ["None"], "success_criteria": ["Answer is true"], "hints": ["Think about its origin"]}'
    monkeypatch.setattr(llm_utils, "ai_chat", mock_ai_chat)

    # Mock QuestionGenerator
    class MockQuestionGenerator:
        def generate_question_set(self, count):
            return [{
                "question": "Is Kubernetes an open-source container orchestration system?",
                "choices": [],
                "answer": "True",
                "suggested_answer": "True",
                "source": "generated",
                "id": "test_id"
            }]
        def _generate_question_id(self):
            return "test_id"

    monkeypatch.setattr(cli, "QuestionGenerator", MockQuestionGenerator)

    # Mock QuestionGenerator._generate_question_id to return a fixed ID
    monkeypatch.setattr(cli.QuestionGenerator, "_generate_question_id", lambda: "test_id")

    # Run the quiz menu
    cli.quiz_menu()

    # Capture output
    captured = capsys.readouterr().out

    # Assert that the question is displayed
    assert "Question: Is Kubernetes an open-source container orchestration system?" in captured