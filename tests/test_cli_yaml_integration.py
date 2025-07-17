import json
import os
import pytest

from kubelingo.cli import run_yaml_editing_mode, YAML_QUESTIONS_FILE


def test_run_yaml_editing_mode_integration(capsys, monkeypatch):
    # Load YAML exercise definitions
    with open(YAML_QUESTIONS_FILE, 'r', encoding='utf-8') as f:
        sections = json.load(f)
    # Flatten prompts of type 'yaml_edit'
    prompts = []
    for section in sections:
        for item in section.get('prompts', []):
            if item.get('question_type') == 'yaml_edit':
                prompts.append(item)
    assert prompts, "No YAML edit prompts found in data file."
    # Prepare correct YAMLs for each prompt
    correct_yamls = [item.get('correct_yaml', '') for item in prompts]

    # Counter for subprocess calls
    call_state = {'idx': 0}

    # Simulate vim editing by writing the correct YAML to the temp file
    def simulate_vim_edit(cmd, check=True):  # cmd: [editor, tmp_filename]
        tmp_file = cmd[1]
        yaml_text = correct_yamls[call_state['idx']]
        with open(tmp_file, 'w', encoding='utf-8') as out_f:
            out_f.write(yaml_text)
        call_state['idx'] += 1

    # Patch subprocess.run in the YAML editor module
    monkeypatch.setattr(
        'kubelingo.modules.vim_yaml_editor.subprocess.run',
        simulate_vim_edit
    )
    # Simulate user input: continue through all exercises except last
    # run_yaml_editing_mode prompts to continue for each exercise idx < total
    cont_inputs = ['y'] * (len(prompts) - 1)
    def fake_input(prompt=None):
        return cont_inputs.pop(0) if cont_inputs else 'n'
    monkeypatch.setattr('builtins.input', fake_input)

    # Run the YAML editing mode
    run_yaml_editing_mode(YAML_QUESTIONS_FILE)
    captured = capsys.readouterr()
    out = captured.out

    # Verify header and summary
    total = len(prompts)
    assert f"Found {total} YAML editing exercises." in out
    assert "Editor:" in out

    # Verify each exercise prompt, correctness, and explanation
    for idx, item in enumerate(prompts, start=1):
        prompt_line = f"Exercise {idx}/{total}: {item.get('prompt')}"
        assert prompt_line in out
        assert "Correct!" in out, f"Missing correct confirmation for exercise {idx}."
        explanation = item.get('explanation')
        if explanation:
            assert explanation in out, f"Missing explanation for exercise {idx}."

    # Verify session completion message
    assert "YAML Editing Session Complete" in outimport pytest
import json
from unittest.mock import patch

# Import the function to be tested and the path to the data file from the CLI module.
# This makes the test robust against changes in file locations.
from kubelingo.cli import run_yaml_editing_mode, YAML_QUESTIONS_FILE

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

    with patch('subprocess.run', side_effect=mock_editor_instance) as mock_run, \
         patch('builtins.input', side_effect=user_inputs) as mock_input:
        
        run_yaml_editing_mode(YAML_QUESTIONS_FILE)

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

    # Split the output by "Exercise" to verify each one individually.
    output_parts = output.split("Exercise ")[1:] # Skip the initial banner part.
    assert len(output_parts) == num_questions, "The number of exercises in the output should match the number of questions."

    # Check that each question's prompt, success message, and explanation were printed.
    for i, prompt_data in enumerate(all_prompts):
        part = output_parts[i]
        prompt_text = prompt_data['prompt']
        explanation_text = prompt_data['explanation']

        # Verify exercise number and prompt are present in the output for this part.
        assert f"{i+1}/{num_questions}: {prompt_text}" in part
        
        # Verify success message and explanation.
        assert "✅ Correct!" in part
        assert f"Explanation: {explanation_text}" in part

        # Ensure "Correct!" appears before the explanation.
        correct_index = part.find("✅ Correct!")
        explanation_index = part.find(f"Explanation: {explanation_text}")
        assert correct_index != -1 and explanation_index > correct_index
