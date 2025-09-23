import pytest
import cli
import json

class FakeAnswer:
    """Fake answer for InquirerPy text prompt."""
    def __init__(self, value):
        self._value = value
    def execute(self):
        return self._value

class DummySelect:
    def __init__(self, value):
        self._value = value
    def execute(self):
        return self._value

# Helper to mock inquirer.text and inquirer.select
def mock_inquirer(monkeypatch, order_list, text_return_value="test_answer", select_return_value="retry"):
    def fake_text(message):
        order_list.append('text_prompt')
        return FakeAnswer(text_return_value)
    monkeypatch.setattr(cli.inquirer, 'text', fake_text)

    def fake_select(message, choices):
        order_list.append('select_prompt')
        return DummySelect(select_return_value)
    monkeypatch.setattr(cli.inquirer, 'select', fake_select)

# Helper to mock print_menu
def mock_print_menu(monkeypatch, order_list, menu_name):
    original_print_menu = cli.print_menu
    def fake_print_menu(name):
        if name == menu_name:
            order_list.append(f'menu_display_{name}')
        original_print_menu(name)
    monkeypatch.setattr(cli, 'print_menu', fake_print_menu)

# Test for generate_trivia (post_question menu)
@pytest.mark.parametrize("question_type, ai_response_answer", [
    ("tf", "true"),
    ("mcq", "a"),
    ("vocab", "test_vocab_answer"),
])
def test_generate_trivia_post_question_menu_order(monkeypatch, question_type, ai_response_answer):
    order = []
    mock_inquirer(monkeypatch, order, text_return_value=ai_response_answer)
    mock_print_menu(monkeypatch, order, "post_question")
    monkeypatch.setattr(cli.console, 'print', lambda *args, **kwargs: None)
    monkeypatch.setattr(cli.console, 'print_json', lambda *args, **kwargs: None)

    # Mock ai_chat to return different question types
    def mock_ai_chat(system_prompt, user_prompt):
        if question_type == "tf":
            return '{"type": "tf", "question": "Test TF question", "answer": "true"}'
        elif question_type == "mcq":
            return '{"type": "mcq", "question": "Test MCQ question", "options": ["a", "b", "c", "d"], "answer": "a"}'
        elif question_type == "vocab":
            return '{"type": "vocab", "question": "Test Vocab question", "answer": "test_vocab_answer"}'
    monkeypatch.setattr(cli, "ai_chat", mock_ai_chat)

    cli.generate_trivia(topic='pods')

    # The text prompt for the answer should come before the post_question menu display
    assert 'text_prompt' in order
    assert f'menu_display_post_question' in order
    assert order.index('text_prompt') < order.index(f'menu_display_post_question')

# Test for generate_trivia (post_answer menu)
def test_generate_trivia_post_answer_menu_order(monkeypatch):
    order = []
    mock_inquirer(monkeypatch, order, text_return_value="true", select_return_value="retry")
    mock_print_menu(monkeypatch, order, "post_answer")
    monkeypatch.setattr(cli.console, 'print', lambda *args, **kwargs: None)
    monkeypatch.setattr(cli.console, 'print_json', lambda *args, **kwargs: None)

    def mock_ai_chat(system_prompt, user_prompt):
        return '{"type": "tf", "question": "Test TF question", "answer": "true"}'
    monkeypatch.setattr(cli, "ai_chat", mock_ai_chat)

    cli.generate_trivia(topic='pods')

    # The select prompt for post_answer menu should come before the post_answer menu display
    assert 'select_prompt' in order
    assert f'menu_display_post_answer' in order
    assert order.index('select_prompt') < order.index(f'menu_display_post_answer')

# Test for static_quiz (post_question menu)
def test_static_quiz_post_question_menu_order(monkeypatch, tmp_path):
    order = []
    mock_inquirer(monkeypatch, order, text_return_value="test_answer")
    mock_print_menu(monkeypatch, order, "post_question")
    monkeypatch.setattr(cli.console, 'print', lambda *args, **kwargs: None)

    # Create a dummy static question file
    q_content = {"question": "Static test question", "suggestions": ["test_answer"]}
    q_file = tmp_path / "test_static_q.json"
    q_file.write_text(json.dumps(q_content))

    # Mock glob to return our dummy file
    monkeypatch.setattr(cli.glob, 'glob', lambda x: [str(q_file)])
    monkeypatch.setattr(cli.os.path, 'join', lambda *args: '/'.join(args)) # Ensure join works with tmp_path

    cli.static_quiz()

    # The text prompt for the answer should come before the post_question menu display
    assert 'text_prompt' in order
    assert f'menu_display_post_question' in order
    assert order.index('text_prompt') < order.index(f'menu_display_post_question')

# Test for static_quiz (post_answer menu)
def test_static_quiz_post_answer_menu_order(monkeypatch, tmp_path):
    order = []
    mock_inquirer(monkeypatch, order, text_return_value="test_answer", select_return_value="retry")
    mock_print_menu(monkeypatch, order, "post_answer")
    monkeypatch.setattr(cli.console, 'print', lambda *args, **kwargs: None)

    # Create a dummy static question file
    q_content = {"question": "Static test question", "suggestions": ["test_answer"]}
    q_file = tmp_path / "test_static_q.json"
    q_file.write_text(json.dumps(q_content))

    # Mock glob to return our dummy file
    monkeypatch.setattr(cli.glob, 'glob', lambda x: [str(q_file)])
    monkeypatch.setattr(cli.os.path, 'join', lambda *args: '/'.join(args)) # Ensure join works with tmp_path

    cli.static_quiz()

    # The select prompt for post_answer menu should come before the post_answer menu display
    assert 'select_prompt' in order
    assert f'menu_display_post_answer' in order
    assert order.index('select_prompt') < order.index(f'menu_display_post_answer')

# Test for generate_command (post_question menu)
def test_generate_command_post_question_menu_order(monkeypatch):
    order = []
    mock_inquirer(monkeypatch, order, text_return_value="kubectl get pods")
    mock_print_menu(monkeypatch, order, "post_question")
    monkeypatch.setattr(cli.console, 'print', lambda *args, **kwargs: None)
    monkeypatch.setattr(cli.console, 'print_json', lambda *args, **kwargs: None)

    # Mock QuestionGenerator.generate_question
    class MockQuestionGenerator:
        def generate_question(self, topic, include_context):
            return {
                "id": "cmd1",
                "topic": "pods",
                "question": "Generate a command to get all pods.",
                "context_variables": {},
                "documentation_link": None
            }
    monkeypatch.setattr(cli, 'QuestionGenerator', MockQuestionGenerator)
    monkeypatch.setattr(cli, 'question_generator_instance', MockQuestionGenerator())

    # Mock inquirer.select for topic selection
    monkeypatch.setattr(cli.inquirer, 'select', lambda message, choices: DummySelect('pods'))

    cli.generate_command()

    # The text prompt for the command should come before the post_question menu display
    assert 'text_prompt' in order
    assert f'menu_display_post_question' in order
    assert order.index('text_prompt') < order.index(f'menu_display_post_question')

# Test for generate_ai_question_flow (post_question menu)
def test_generate_ai_question_flow_post_question_menu_order(monkeypatch):
    order = []
    mock_inquirer(monkeypatch, order, text_return_value="test_answer")
    mock_print_menu(monkeypatch, order, "post_question")
    monkeypatch.setattr(cli.console, 'print', lambda *args, **kwargs: None)
    monkeypatch.setattr(cli.console, 'print_json', lambda *args, **kwargs: None)
    monkeypatch.setattr(cli.os.environ, 'get', lambda key, default=None: 'mock_key' if 'API_KEY' in key else default)

    def mock_ai_chat(system_prompt, user_prompt):
        return '{"id": "ai1", "topic": "general", "question": "AI generated question", "suggested_answer": "ai_answer"}'
    monkeypatch.setattr(cli, "ai_chat", mock_ai_chat)

    cli.generate_ai_question_flow()

    # The text prompt for the answer should come before the post_question menu display
    assert 'text_prompt' in order
    assert f'menu_display_post_question' in order
    assert order.index('text_prompt') < order.index(f'menu_display_post_question')

# Test for generate_ai_question_flow (post_answer menu)
def test_generate_ai_question_flow_post_answer_menu_order(monkeypatch):
    order = []
    mock_inquirer(monkeypatch, order, text_return_value="test_answer", select_return_value="retry")
    mock_print_menu(monkeypatch, order, "post_answer")
    monkeypatch.setattr(cli.console, 'print', lambda *args, **kwargs: None)
    monkeypatch.setattr(cli.console, 'print_json', lambda *args, **kwargs: None)
    monkeypatch.setattr(cli.os.environ, 'get', lambda key, default=None: 'mock_key' if 'API_KEY' in key else default)

    def mock_ai_chat(system_prompt, user_prompt):
        return '{"id": "ai1", "topic": "general", "question": "AI generated question", "suggested_answer": "ai_answer"}'
    monkeypatch.setattr(cli, "ai_chat", mock_ai_chat)

    cli.generate_ai_question_flow()

    # The select prompt for post_answer menu should come before the post_answer menu display
    assert 'select_prompt' in order
    assert f'menu_display_post_answer' in order
    assert order.index('select_prompt') < order.index(f'menu_display_post_answer')
