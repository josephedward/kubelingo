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
    assert "YAML Editing Session Complete" in out