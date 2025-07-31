import subprocess
import sys
import re

ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')

def run_cli_help():
    """Run the CLI with --help and capture output."""
    return subprocess.run(
        [sys.executable, '-m', 'kubelingo', '--help'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

def test_help_exit_code_and_no_null_bytes():
    """The help output should exit cleanly and contain no null bytes."""
    result = run_cli_help()
    assert result.returncode == 0
    assert '\x00' not in result.stdout

def test_help_line_lengths():
    """Each line of help output should be at most 80 characters (ignoring ANSI codes)."""
    result = run_cli_help()
    for line in result.stdout.splitlines():
        clean = ANSI_RE.sub('', line)
        assert len(clean) <= 80, f"Line too long ({len(clean)}): {clean!r}"

def test_help_contains_core_options():
    """Help output should list core CLI options."""
    result = run_cli_help()
    text = ANSI_RE.sub('', result.stdout)
    for opt in ['--file', '--num', '--category', '--history', '--list-modules']:
        assert opt in text, f"Expected option '{opt}' in help output"

def test_menu_options_match_shared_context():
    """Verify that the interactive menu options align with shared_context.md spec."""
    # Extract documented menu options
    doc = open('shared_context.md', encoding='utf-8').read()
    match = re.search(r'Options are now: (.+)', doc)
    assert match, "Could not find 'Options are now:' in shared_context.md"
    # Split options by comma and normalize
    opts = [opt.strip().strip('“”') for opt in match.group(1).split(',')]
    # Load code and check presence of each option text
    code = open('kubelingo/modules/kubernetes/session.py', encoding='utf-8').read()
    missing = []
    for opt in opts:
        # Check case-insensitive presence
        if opt not in code and opt.lower() not in code.lower():
            missing.append(opt)
    assert not missing, f"Missing menu options in code: {missing}"