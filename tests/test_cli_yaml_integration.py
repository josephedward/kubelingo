import pytest
import json
from unittest.mock import patch, Mock

# Import the function to be tested and the path to the data file from the CLI module.
# This makes the test robust against changes in file locations.
from kubelingo.modules.kubernetes.session import NewSession, YAML_QUESTIONS_FILE

# Load the test data once to get the list of questions and correct solutions.
with open(YAML_QUESTIONS_FILE, 'r') as f:
    yaml_questions_data = json.load(f)

# Flatten the list of questions to make them easier to iterate through in the test.
all_prompts = []
for section in yaml_questions_data:
    for prompt in section.get('prompts', []):
        if prompt.get('question_type') == 'yaml_edit':
            all_prompts.append(prompt)

correct_yaml_solutions = [p['correct_yaml'] for p in all_prompts]
num_questions = len(correct_yaml_solutions)

# A stateful callable class to simulate the editor for `subprocess.run`.
# This allows us to provide a different "edited" file for each question.
class MockEditor:
    def __init__(self, solutions):
        self.solutions_iterator = iter(solutions)
        self.call_count = 0

    def __call__(self, cmd, check=True):
        """
        This method is the mock for `subprocess.run`. It simulates a user
        editing a file and saving the correct content.
        """
        self.call_count += 1
        tmp_file_path = cmd[1]
        try:
            solution = next(self.solutions_iterator)
            with open(tmp_file_path, 'w', encoding='utf-8') as f:
                f.write(solution)
        except StopIteration:
            raise AssertionError("MockEditor was called more times than there are solutions.")

def test_yaml_editing_e2e_flow(capsys):
    """
    Tests the end-to-end flow of the YAML editing mode.
    - Mocks the editor subprocess to simulate correct answers for all questions.
    - Mocks user input to auto-continue through all exercises.
    - Verifies that the full session flow and output are correct.
    """
    # Instantiate our mock editor with the correct solutions.
    mock_editor_instance = MockEditor(correct_yaml_solutions)

    # Mock user input to automatically answer 'y' to "Continue?" prompts.
    # There will be (num_questions - 1) such prompts.
    user_inputs = ['y'] * (num_questions - 1)

    # The function is now a method on the NewSession class
    session = NewSession(logger=Mock())
    # Mock CLI args, though they are not used by this specific method
    mock_args = Mock()

    # Patch subprocess in the module where it's used
    with patch('kubelingo.modules.kubernetes.session.subprocess.run', side_effect=mock_editor_instance) as mock_run, \
         patch('builtins.input', side_effect=user_inputs) as mock_input:
        
        session._run_yaml_editing_mode(mock_args)

    # --- Assertions ---
    # Assert that the editor was called once for each question.
    assert mock_editor_instance.call_count == num_questions

    # Assert that input was called to prompt for continuing after each question except the last one.
    assert mock_input.call_count == num_questions - 1

    # Assert on the captured standard output.
    captured = capsys.readouterr()
    output = captured.out
    
    # Check for session start and end banners.
    assert "=== Kubelingo YAML Editing Mode ===" in output
    assert "=== YAML Editing Session Complete ===" in output
    
    # Check that each question's prompt, success message, and explanation were printed.
    for i, prompt_data in enumerate(all_prompts, 1):
        prompt_text = prompt_data['prompt']
        explanation_text = prompt_data['explanation']

        # Verify that the prompt from cli.py is present
        assert f"Exercise {i}/{num_questions}: {prompt_text}" in output
        
        # Verify that the prompt from vim_yaml_editor.py is present
        assert f"=== Exercise {i}: {prompt_text} ===" in output

        # Verify explanation for each prompt
        assert f"Explanation: {explanation_text}" in output

    # Verify correct number of "Correct!" messages
    assert output.count("✅ Correct!") == num_questions
