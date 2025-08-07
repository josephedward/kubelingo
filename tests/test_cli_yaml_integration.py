import pytest
# YAML editing feature is now enabled
import json
from unittest.mock import patch, Mock
import yaml
import os
import os


# Import the function to be tested and the path to the data file from the CLI module.
# This makes the test robust against changes in file locations.
from kubelingo.modules.kubernetes.session import NewSession
from kubelingo.utils.config import YAML_QUESTIONS_FILE


@pytest.fixture
def yaml_test_data():
    """Load YAML test data."""
    # The file existence is already checked by pytestmark, so we can assume it exists.
    with open(YAML_QUESTIONS_FILE, 'r', encoding='utf-8') as f:
        # Load YAML quiz data directly
        yaml_questions_data = yaml.safe_load(f)

    # Flatten the list of questions to make them easier to iterate through in the test.
    all_prompts = []
    for section in yaml_questions_data:
        # Nested prompts
        if isinstance(section, dict) and section.get('prompts'):
            for prompt in section.get('prompts', []):
                if prompt.get('question_type') == 'yaml_edit':
                    all_prompts.append(prompt)
        # Simple standalone questions
        elif isinstance(section, dict) and section.get('prompt') and 'answer' in section:
            all_prompts.append({
                'prompt': section['prompt'],
                'starting_yaml': section.get('starting_yaml', ''),
                'correct_yaml': section.get('correct_yaml', section['answer']),
                'explanation': section.get('explanation', '')
            })
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

    # Mock user input for editor launches and continue prompts: alternate '' then 'y', ending with ''
    user_inputs = []
    for idx in range(num_questions):
        # Press Enter to open editor
        user_inputs.append('')
        # Respond 'y' to continue prompts except after last question
        if idx < num_questions - 1:
            user_inputs.append('y')

    # The function is now a method on the NewSession class
    session = NewSession(logger=Mock())
    # Mock CLI args, though they are not used by this specific method
    mock_args = Mock()

    # Patch subprocess in the vim_yaml_editor module to simulate editor
    with patch('kubelingo.modules.kubernetes.vim_yaml_editor.subprocess.run', side_effect=mock_editor_instance) as mock_run, \
         patch('builtins.input', side_effect=user_inputs) as mock_input, \
         patch('kubelingo.modules.kubernetes.session.random.sample', lambda pop, k: pop):
        
        session._run_yaml_editing_mode(mock_args)

    # --- Assertions ---
    # Assert that the editor was called once for each question.
    assert mock_editor_instance.call_count == num_questions

    # Assert that input was called for each editor launch and continue prompt
    expected_input_calls = 2 * num_questions - 1
    assert mock_input.call_count == expected_input_calls

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
