import pytest
import json
from unittest.mock import patch, Mock
import yaml
import os
import os

# Import the function to be tested and the path to the data file from the CLI module.
# This makes the test robust against changes in file locations.
from kubelingo.modules.kubernetes.session import NewSession, YAML_QUESTIONS_FILE

@pytest.fixture
def yaml_test_data():
    """Load YAML test data, skipping if the file doesn't exist."""
    if not os.path.exists(YAML_QUESTIONS_FILE):
        pytest.skip(f"YAML questions file not found: {YAML_QUESTIONS_FILE}")

    with open(YAML_QUESTIONS_FILE, 'r') as f:
        yaml_questions_data = json.load(f)

    # Flatten the list of questions to make them easier to iterate through in the test.
    all_prompts = []
    for section in yaml_questions_data:
        for prompt in section.get('prompts', []):
            if prompt.get('question_type') == 'yaml_edit':
                all_prompts.append(prompt)
    
    return all_prompts

# A stateful callable class to simulate the editor for `subprocess.run`.
# This allows us to provide a different "edited" file for each question.
class MockEditor:
    def __init__(self, solutions):
        self.solutions_iterator = iter(solutions)
        self.call_count = 0

    def __call__(self, cmd, check=True, timeout=None):
        """
        This method is the mock for `subprocess.run`. It simulates a user
        editing a file and saving the correct content. It normalizes the YAML
        to avoid validation failures due to formatting differences.
        """
        self.call_count += 1
        tmp_file_path = cmd[1]
        try:
            solution_str = next(self.solutions_iterator)
            # Normalize YAML by loading and dumping it. This removes formatting
            # inconsistencies that could cause the string-based diff to fail.
            normalized_solution = yaml.dump(yaml.safe_load(solution_str))
            with open(tmp_file_path, 'w', encoding='utf-8') as f:
                f.write(normalized_solution)
        except StopIteration:
            raise AssertionError("MockEditor was called more times than there are solutions.")

        # Return a mock process object to simulate a successful editor session.
        mock_proc = Mock()
        mock_proc.returncode = 0
        return mock_proc

def test_yaml_editing_e2e_flow(capsys, yaml_test_data):
    """
    Tests the end-to-end flow of the YAML editing mode.
    - Mocks the editor subprocess to simulate correct answers for all questions.
    - Mocks user input to auto-continue through all exercises.
    - Verifies that the full session flow and output are correct.
    """
    all_prompts = yaml_test_data
    correct_yaml_solutions = [p['correct_yaml'] for p in all_prompts]
    num_questions = len(correct_yaml_solutions)

    if num_questions == 0:
        pytest.skip("No YAML edit questions found to test.")

    # Instantiate our mock editor with the correct solutions.
    mock_editor_instance = MockEditor(correct_yaml_solutions)

    # Mock user input to automatically answer 'y' to "Continue?" prompts
    # and 'n' to any retry prompts. This test covers the success path, so only 'y' for 'Continue?' is needed.
    user_inputs = ['y'] * (num_questions - 1)

    # The function is now a method on the NewSession class
    session = NewSession(logger=Mock())
    # Mock CLI args, though they are not used by this specific method
    mock_args = Mock()

    # Patch subprocess in the module where it's used
    with patch('kubelingo.modules.kubernetes.session.subprocess.run', side_effect=mock_editor_instance) as mock_run, \
         patch('builtins.input', side_effect=user_inputs) as mock_input, \
         patch('kubelingo.modules.kubernetes.session.random.sample', lambda pop, k: pop):
        
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
