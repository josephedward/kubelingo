import pytest
import cli


def test_print_question_menu(capsys):
    # Capture the output of printing the question menu
    cli.print_question_menu()
    out = capsys.readouterr().out
    # Header should not be printed; only entries are shown
    assert '# Post Question Menu' not in out
    assert 'v) vim      - opens vim for manifest-based questions' in out
    assert 'b) backward - previous question' in out
    assert 'f) forward  - next question' in out
    assert 'a) answer   - shows solution' in out
    assert 's) visit    - source (opens browser at source)' in out
    assert 'q) quit     - back to main menu' in out

def test_print_post_answer_menu(capsys):
    # Capture the output of printing the post-answer menu
    cli.print_post_answer_menu()
    out = capsys.readouterr().out
    # Header should not be printed; only entries are shown
    assert 'Post Answer Menu' not in out
    # Ensure entries match MENU_DEFINITIONS for post-answer menu
    for key, label, desc in cli.MENU_DEFINITIONS['post_answer']['entries']:
        expected_line = f"{key}) {label:<9}- {desc}"
        assert expected_line in out

def test_print_post_answer_menu_only_shows_post_answer_entries(capsys):
    # Ensure only post-answer menu entries are displayed (exactly the first four)
    cli.print_post_answer_menu()
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line.strip()]
    expected = [f"{k}) {label:<9}- {desc}" for k, label, desc in cli.MENU_DEFINITIONS['post_answer']['entries']]
    assert lines == expected, f"Expected only post-answer entries, got:\n{out}"
    # Also ensure no extra entries beyond defined ones
    assert len(lines) == len(cli.MENU_DEFINITIONS['post_answer']['entries'])

def test_print_question_menu_only_shows_post_question_entries(capsys):
    # Ensure only post-question menu entries are displayed
    cli.print_question_menu()
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line.strip()]
    expected = [f"{k}) {label:<9}- {desc}" for k, label, desc in cli.MENU_DEFINITIONS['post_question']['entries']]
    assert lines == expected, f"Expected only post-question entries, got:\n{out}"
    assert len(lines) == len(cli.MENU_DEFINITIONS['post_question']['entries'])

def test_print_menu_generic_and_aliases(capsys):
    # Generic print_menu for post_question should match specific aliases
    funcs = [cli.print_menu, cli.print_menu_entries]
    names = ['post_question']
    # Also include specific wrappers
    wrappers = [cli.print_question_menu, cli.print_post_question_menu]
    # Generate expected output once
    cli.print_menu('post_question')
    expected_out = capsys.readouterr().out
    # Compare generic and entries printers
    for fn in funcs:
        cli.print_menu('post_question') if fn is cli.print_menu else cli.print_menu_entries('post_question')
        out = capsys.readouterr().out
        assert out == expected_out, f"{fn.__name__} output differs from print_menu:\n{out}"
    # Compare wrappers
    for fn in wrappers:
        fn()
        out = capsys.readouterr().out
        assert out == expected_out, f"{fn.__name__} output differs from print_menu:\n{out}"

def test_print_menu_invalid_name(capsys):
    # Unknown menu name should produce no output
    cli.print_menu('nonexistent_menu')
    out = capsys.readouterr().out
    assert out == ''