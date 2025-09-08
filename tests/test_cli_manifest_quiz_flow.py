import pytest
import webbrowser
import kubelingo.cli as cli
from rich.console import Console
from unittest.mock import MagicMock, call, patch
import builtins
import os

class FakeAnswer:
    """Fake answer for InquirerPy prompts."""
    def __init__(self, value):
        self._value = value
    def execute(self):
        return self._value

def test_manifest_editor_flow(monkeypatch, capsys):
    # Mock QuestionGenerator.generate_question_set (though not directly used in this flow, it's good practice to mock)
    original_manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: my-pod
spec:
  containers:
  - name: my-container
    image: nginx:latest"""
    
    modified_manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: my-pod-modified
spec:
  containers:
  - name: my-container
    image: nginx:1.20"""

    def mock_generate_question_set(self, count, question_type, subject_matter):
        return [{
            'id': 'test-manifest-id',
            'topic': subject_matter,
            'question_type': question_type,
            'question': "Edit the following manifest to change the pod name and image version:",
            'suggested_answer': original_manifest
        }]
    monkeypatch.setattr(cli.QuestionGenerator, 'generate_question_set', mock_generate_question_set)
    
    # Prevent actual browser opens
    monkeypatch.setattr(webbrowser, 'open', lambda url: None)

    # Mock _open_manifest_editor to allow assertions on its calls, while still executing its original logic
    original_open_manifest_editor = cli._open_manifest_editor
    mock_open_manifest_editor = MagicMock(side_effect=original_open_manifest_editor)
    monkeypatch.setattr(cli, '_open_manifest_editor', mock_open_manifest_editor)

    # Mock os.system to prevent actual editor from opening and simulate writing to the temp file
    def write_modified(command):
        # Extract the temporary file path from the command
        parts = command.split()
        temp_file_path = parts[-1]  # Assuming the last part is the file path
        # Simulate the editor writing the modified content to the temp file
        with open(temp_file_path, 'w') as f:
            f.write(modified_manifest)
    mock_os_system = MagicMock(side_effect=write_modified)
    monkeypatch.setattr(os, 'system', mock_os_system)
    
    # Mock tempfile.NamedTemporaryFile to control the temporary file path and ensure it's cleaned up
    mock_tmp_file = MagicMock()
    mock_tmp_file.name = os.path.join(os.getcwd(), 'tests', 'test_manifest.yaml')  # A dummy path for testing
    mock_tmp_file.__enter__.return_value = mock_tmp_file
    mock_tmp_file.__exit__.return_value = None # Ensure __exit__ is called
    # Patch both local and stdlib tempfile.NamedTemporaryFile used in the function
    import tempfile as std_tempfile
    monkeypatch.setattr(std_tempfile, 'NamedTemporaryFile', MagicMock(return_value=mock_tmp_file))
    monkeypatch.setattr(cli.tempfile, 'NamedTemporaryFile', MagicMock(return_value=mock_tmp_file))
    
    # Mock os.remove to prevent actual file deletion during test cleanup
    monkeypatch.setattr(os, 'remove', MagicMock())
    
    # Mock ai_chat (though not directly used in this flow, it's good practice to mock)
    mock_ai_chat = MagicMock(return_value="AI feedback: Good changes!")
    monkeypatch.setattr(cli, 'ai_chat', mock_ai_chat)
    monkeypatch.setattr(cli._llm_utils, 'ai_chat', mock_ai_chat) # Also mock the internal usage

    # Prepare inquirer responses:
    # 1. Main Menu: Quiz
    # 2. Quiz Type: Declarative (Manifests)
    # 3. Subject Matter: pods
    mock_inquirer_select = MagicMock(side_effect=[
        FakeAnswer('Quiz'),                    # Main Menu: Quiz
        FakeAnswer('Declarative (Manifests)'), # Quiz type
        FakeAnswer('core_workloads'),            # Topic
        FakeAnswer('Exit')                     # Main Menu: Exit (to terminate the main loop)
    ])
    monkeypatch.setattr(cli.inquirer, 'select', mock_inquirer_select)
    # Provide number of questions for manifest flow
    monkeypatch.setattr(cli.inquirer, 'text', MagicMock(side_effect=[FakeAnswer('1')]))
    # No builtins.input for post-answer menu in this flow

    # Capture console.print outputs
    printed = []
    mock_console_instance = Console()
    monkeypatch.setattr(mock_console_instance, 'print', lambda *args, **kwargs: printed.append(" ".join(str(a) for a in args)))

    # Run the main CLI application (will exit via SystemExit on 'Exit')
    with pytest.raises(SystemExit):
        cli.main()

    # Assertions
    # Verify that _open_manifest_editor was called
    mock_open_manifest_editor.assert_called_once()
    
    # Verify that os.system was called with the editor command
    mock_os_system.assert_called_once()
    args, kwargs = mock_os_system.call_args
    assert args[0].startswith(os.environ.get('EDITOR', 'vim'))
    assert args[0].endswith(mock_tmp_file.name)

    # Verify output contains user's answer
    captured = capsys.readouterr()
    combined_output = captured.out + "\n".join(printed)
    assert "Your answer:" in combined_output
    assert modified_manifest in combined_output

    # AI chat should NOT be called in this flow, as it exits after manifest editing
    mock_ai_chat.assert_not_called()

    # The quiz session finished message should NOT be present in this flow
    assert "Quiz session finished." not in combined_output

@pytest.mark.parametrize("user_input,expected_msg,unexpected_msg", [
    # Correct YAML should yield Correct!
    ("correct_manifest", "Correct!", "Suggested Answer:"),
    # Incorrect YAML should yield Suggested Answer
    ("incorrect_manifest", "Suggested Answer:", "Correct!"),
])
def test_manifest_quiz_flow_yaml_handling(monkeypatch, capsys, user_input, expected_msg, unexpected_msg):
    # Prepare manifest variants
    correct_manifest = (
        "apiVersion: v1\nkind: Pod\nmetadata:\n  name: test-pod"
    )
    incorrect_manifest = correct_manifest + "\nextra: field"
    # Mock question generation
    def mock_generate(self, *args, **kwargs):
        return [{
            "question": "Test manifest question",
            "suggested_answer": correct_manifest,
        }]
    monkeypatch.setattr(cli.QuestionGenerator, "generate_question_set", mock_generate)
    # Mock editor to return appropriate content
    if user_input == "correct_manifest":
        monkeypatch.setattr(cli, "_open_manifest_editor", lambda template="": correct_manifest)
    else:
        monkeypatch.setattr(cli, "_open_manifest_editor", lambda template="": incorrect_manifest)
    # Simulate main menu and quiz menu selections: Quiz -> Declarative (Manifests) -> topic -> Exit
    selects = [
        FakeAnswer("Quiz"),
        FakeAnswer("Declarative (Manifests)"),
        FakeAnswer("general"),
        FakeAnswer("Exit"),
    ]
    monkeypatch.setattr(cli.inquirer, "select", MagicMock(side_effect=selects))
    # Provide count=1
    monkeypatch.setattr(cli.inquirer, "text", MagicMock(side_effect=[FakeAnswer("1")]))
    # Run main and exit
    with pytest.raises(SystemExit):
        cli.main()
    out = capsys.readouterr().out
    assert expected_msg in out
    assert unexpected_msg not in out

def test_manifest_quiz_flow_invalid_yaml(monkeypatch, capsys):
    # Prepare invalid YAML
    invalid_manifest = "apiVersion: v1\nkind Pod\nmetadata name: missing"
    correct_manifest = "apiVersion: v1\nkind: Pod"
    # Mock generation
    def mock_generate(self, *args, **kwargs):
        return [{
            "question": "Test manifest question",
            "suggested_answer": correct_manifest,
        }]
    monkeypatch.setattr(cli.QuestionGenerator, "generate_question_set", mock_generate)
    # Editor returns invalid YAML
    monkeypatch.setattr(cli, "_open_manifest_editor", lambda template="": invalid_manifest)
    # Simulate selections
    selects = [FakeAnswer("Quiz"), FakeAnswer("Declarative (Manifests)"), FakeAnswer("general"), FakeAnswer("Exit")]
    monkeypatch.setattr(cli.inquirer, "select", MagicMock(side_effect=selects))
    monkeypatch.setattr(cli.inquirer, "text", MagicMock(side_effect=[FakeAnswer("1")]))
    # Run main
    with pytest.raises(SystemExit):
        cli.main()
    out = capsys.readouterr().out
    assert "Invalid YAML provided:" in out
    assert "Suggested Answer:" in out

def test_manifest_quiz_flow_invalid_count(monkeypatch, capsys):
    # Simulate invalid count
    monkeypatch.setattr(cli.QuestionGenerator, "generate_question_set", lambda self, *args, **kwargs: [])
    selects = [
        FakeAnswer("Quiz"),
        FakeAnswer("Declarative (Manifests)"),
        FakeAnswer("general"),
        FakeAnswer("Back"),  # Back to quiz menu
        FakeAnswer("Exit"),
    ]
    monkeypatch.setattr(cli.inquirer, "select", MagicMock(side_effect=selects))
    monkeypatch.setattr(cli.inquirer, "text", MagicMock(side_effect=[FakeAnswer("0")]))
    with pytest.raises(SystemExit):
        cli.main()
    out = capsys.readouterr().out
    assert "Invalid number. Returning to quiz menu." in out

def test_manifest_quiz_flow_multiple_questions(monkeypatch, capsys):
    # Test multi-question flow
    correct_manifest = "apiVersion: v1\nkind: Pod"
    # Mock generation returning count items
    def mock_generate(self, *args, **kwargs):
        count = kwargs.get('count', args[0] if args else 0)
        return [{"question": f"Question {i}", "suggested_answer": correct_manifest} for i in range(count)]
    monkeypatch.setattr(cli.QuestionGenerator, "generate_question_set", mock_generate)
    # Editor returns correct manifest for each
    monkeypatch.setattr(cli, "_open_manifest_editor", lambda template="": correct_manifest)
    # Simulate selections
    selects = [FakeAnswer("Quiz"), FakeAnswer("Declarative (Manifests)"), FakeAnswer("general"), FakeAnswer("Exit")]
    monkeypatch.setattr(cli.inquirer, "select", MagicMock(side_effect=selects))
    monkeypatch.setattr(cli.inquirer, "text", MagicMock(side_effect=[FakeAnswer("3")]))
    with pytest.raises(SystemExit):
        cli.main()
    out = capsys.readouterr().out
    assert out.count("Correct!") == 3

@pytest.mark.parametrize("editor_return, expected_correct", [
    # Correct YAML: editor returns exactly suggested
    ("apiVersion: v1\nkind: Pod\nmetadata:\n  name: my-pod", True),
    # Incorrect YAML: valid YAML but differs
    ("apiVersion: v1\nkind: Pod\nmetadata:\n  name: other-pod", False),
])
def test_manifest_quiz_flow_correctness(
    monkeypatch, capsys, editor_return, expected_correct
):
    # Prepare a suggested manifest
    suggested = "apiVersion: v1\nkind: Pod\nmetadata:\n  name: my-pod"
    # Stub QuestionGenerator to return one manifest question
    def mock_generate(self, count, question_type, subject_matter):
        return [{
            'question': "Edit the following Pod manifest:",
            'suggested_answer': suggested,
            'answer': suggested,
            'topic': subject_matter
        }]
    monkeypatch.setattr(cli.QuestionGenerator, 'generate_question_set', mock_generate)
    # Stub editor to return editor_return
    monkeypatch.setattr(cli, '_open_manifest_editor', lambda template='': editor_return)
    # Simulate user flow: Quiz -> Manifest -> pods -> Exit
    seq = [
        FakeAnswer('Quiz'),
        FakeAnswer('Declarative (Manifests)'),
        FakeAnswer('pods'),
        FakeAnswer('Exit')
    ]
    monkeypatch.setattr(cli.inquirer, 'select', MagicMock(side_effect=seq))
    monkeypatch.setattr(cli.inquirer, 'text', MagicMock(side_effect=[FakeAnswer('1')]))
    # Capture exit
    with pytest.raises(SystemExit):
        cli.main()
    out = capsys.readouterr().out
    # Check that editor was invoked and output includes question and answer
    assert "Question: Edit the following Pod manifest:" in out
    assert editor_return in out
    if expected_correct:
        assert "Correct!" in out
        assert "Suggested Answer:" not in out
    else:
        assert "Suggested Answer:" in out
        assert suggested in out

def test_manifest_quiz_flow_invalid_yaml(monkeypatch, capsys):
    suggested = "apiVersion: v1\nkind: Pod\nmetadata:\n  name: my-pod"
    # Stub QG
    # Stub QuestionGenerator to return one manifest question regardless of args
    monkeypatch.setattr(
        cli.QuestionGenerator,
        'generate_question_set',
        lambda self, *args, **kwargs: [{
            'question': "Edit Pod manifest:",
            'suggested_answer': suggested,
            'answer': suggested,
            'topic': kwargs.get('subject_matter', None) or (args[2] if len(args) >= 3 else None)
        }]
    )
    # Editor returns invalid YAML
    invalid = "apiVersion: v1\nkind Pod metadata name my-pod"
    monkeypatch.setattr(cli, '_open_manifest_editor', lambda template='': invalid)
    # Flow: Quiz -> Manifest -> pods -> Exit
    seq = [FakeAnswer('Quiz'), FakeAnswer('Declarative (Manifests)'), FakeAnswer('pods'), FakeAnswer('Exit')]
    monkeypatch.setattr(cli.inquirer, 'select', MagicMock(side_effect=seq))
    monkeypatch.setattr(cli.inquirer, 'text', MagicMock(side_effect=[FakeAnswer('1')]))
    with pytest.raises(SystemExit):
        cli.main()
    out = capsys.readouterr().out
    # For invalid or unparsable YAML, fall back to showing suggested answer
    assert "Suggested Answer:" in out
    assert suggested in out
    assert "Correct!" not in out

def test_manifest_quiz_flow_invalid_count(monkeypatch, capsys):
    # Stub QG to not be called
    monkeypatch.setattr(cli.QuestionGenerator, 'generate_question_set', lambda *args, **kwargs: [])
    # Flow: Quiz -> Manifest -> pods -> Back -> Exit
    selects = [FakeAnswer('Quiz'), FakeAnswer('Declarative (Manifests)'), FakeAnswer('pods'), FakeAnswer('Back'), FakeAnswer('Exit')]
    monkeypatch.setattr(cli.inquirer, 'select', MagicMock(side_effect=selects))
    # Invalid count '0'
    monkeypatch.setattr(cli.inquirer, 'text', MagicMock(side_effect=[FakeAnswer('0')]))
    with pytest.raises(SystemExit):
        cli.main()
    out = capsys.readouterr().out
    assert "Invalid number. Returning to quiz menu." in out

def test_manifest_quiz_flow_multiple_questions(monkeypatch, capsys):
    suggestions = [
        "apiVersion: v1\nkind: Pod\nmetadata:\n  name: pod1",
        "apiVersion: v1\nkind: Pod\nmetadata:\n  name: pod2",
    ]
    # Stub QG to return two questions with different suggested answers
    def mock_gen(self, count, question_type, subject_matter):
        return [
            {'question': 'Q1', 'suggested_answer': suggestions[0], 'answer': suggestions[0], 'topic': subject_matter},
            {'question': 'Q2', 'suggested_answer': suggestions[1], 'answer': suggestions[1], 'topic': subject_matter},
        ]
    monkeypatch.setattr(cli.QuestionGenerator, 'generate_question_set', mock_gen)
    # Editor returns each suggestion in order
    monkeypatch.setattr(cli, '_open_manifest_editor', MagicMock(side_effect=suggestions))
    # Flow: Quiz -> Manifest -> pods -> Exit
    seq = [FakeAnswer('Quiz'), FakeAnswer('Declarative (Manifests)'), FakeAnswer('pods'), FakeAnswer('Exit')]
    monkeypatch.setattr(cli.inquirer, 'select', MagicMock(side_effect=seq))
    monkeypatch.setattr(cli.inquirer, 'text', MagicMock(side_effect=[FakeAnswer('2')]))
    with pytest.raises(SystemExit):
        cli.main()
    out = capsys.readouterr().out
    # Both questions should be printed and marked correct
    assert out.count("Correct!") == 2
    assert out.count("Question: Q1") == 1
    assert out.count("Question: Q2") == 1

def test_manifest_editor_flow_no_changes(monkeypatch, capsys):
    # Mock QuestionGenerator.generate_question_set
    original_manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: my-pod
spec:
  containers:
  - name: my-container
    image: nginx:latest"""
    
    def mock_generate_question_set(self, count, question_type, subject_matter):
        return [{
            'id': 'test-manifest-id-no-changes',
            'topic': subject_matter,
            'question_type': question_type,
            'question': "Edit the following manifest (no changes expected):",
            'suggested_answer': original_manifest
        }]
    monkeypatch.setattr(cli.QuestionGenerator, 'generate_question_set', mock_generate_question_set)
    
    # Prevent actual browser opens
    monkeypatch.setattr(webbrowser, 'open', lambda url: None)

    # Mock _open_manifest_editor to allow assertions on its calls, while still executing its original logic
    original_open_manifest_editor = cli._open_manifest_editor
    mock_open_manifest_editor = MagicMock(side_effect=original_open_manifest_editor)
    monkeypatch.setattr(cli, '_open_manifest_editor', mock_open_manifest_editor)

    # Mock os.system to prevent actual editor from opening and simulate writing to the temp file
    def write_original(command):
        # Extract the temporary file path from the command
        parts = command.split()
        temp_file_path = parts[-1]  # Assuming the last part is the file path
        # Simulate the editor writing the original content to the temp file (no changes)
        with open(temp_file_path, 'w') as f:
            f.write(original_manifest)
    mock_os_system = MagicMock(side_effect=write_original)
    monkeypatch.setattr(os, 'system', mock_os_system)
    
    # Mock tempfile.NamedTemporaryFile to control the temporary file path and ensure it's cleaned up
    mock_tmp_file = MagicMock()
    mock_tmp_file.name = os.path.join(os.getcwd(), 'tests', 'test_manifest_no_changes.yaml')  # A dummy path for testing
    mock_tmp_file.__enter__.return_value = mock_tmp_file
    mock_tmp_file.__exit__.return_value = None # Ensure __exit__ is called
    import tempfile as std_tempfile
    monkeypatch.setattr(std_tempfile, 'NamedTemporaryFile', MagicMock(return_value=mock_tmp_file))
    monkeypatch.setattr(cli.tempfile, 'NamedTemporaryFile', MagicMock(return_value=mock_tmp_file))
    
    # Mock os.remove to prevent actual file deletion during test cleanup
    monkeypatch.setattr(os, 'remove', MagicMock())
    
    # Mock ai_chat (should NOT be called in this scenario)
    mock_ai_chat = MagicMock(return_value="AI feedback: Good changes!")
    monkeypatch.setattr(cli, 'ai_chat', mock_ai_chat)
    monkeypatch.setattr(cli._llm_utils, 'ai_chat', mock_ai_chat) # Also mock the internal usage

    # Prepare inquirer responses:
    mock_inquirer_select = MagicMock(side_effect=[
        FakeAnswer('Quiz'),                    # Main Menu: Quiz
        FakeAnswer('Declarative (Manifests)'), # Quiz type
        FakeAnswer('core_workloads'),            # Topic
        FakeAnswer('Exit')                     # Main Menu: Exit
    ])
    monkeypatch.setattr(cli.inquirer, 'select', mock_inquirer_select)
    monkeypatch.setattr(cli.inquirer, 'text', MagicMock(side_effect=[FakeAnswer('1')]))

    # Capture console.print outputs
    printed = []
    mock_console_instance = Console()
    monkeypatch.setattr(mock_console_instance, 'print', lambda *args, **kwargs: printed.append(" ".join(str(a) for a in args)))

    # Run the main CLI application
    with pytest.raises(SystemExit):
        cli.main()

    # Assertions
    mock_open_manifest_editor.assert_called_once()
    mock_os_system.assert_called_once()
    args, kwargs = mock_os_system.call_args
    assert args[0].startswith(os.environ.get('EDITOR', 'vim'))
    assert args[0].endswith(mock_tmp_file.name)

    captured = capsys.readouterr()
    combined_output = captured.out + "\n".join(printed)
    # Should show the prompt and the original manifest back as answer
    assert "Your answer:" in combined_output
    assert original_manifest in combined_output
    assert "Correct!" in combined_output

    # AI chat should NOT be called if the answer is verbatim
    mock_ai_chat.assert_not_called()
    assert "Quiz session finished." not in combined_output
