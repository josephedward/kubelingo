import pytest
from pathlib import Path
import sys
from unittest.mock import patch

def test_dynamic_script_commands_are_correctly_generated(monkeypatch, tmp_path, capsys):
    """
    Tests that the 'run' subcommand correctly generates subcommands for scripts
    in the scripts directory, respecting exclusions.
    """
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()

    # Create a set of test scripts that should be discovered
    (scripts_dir / "my-script.py").touch()
    (scripts_dir / "another_script.sh").touch()
    (scripts_dir / "script_with_underscores.py").touch()

    # Create scripts that should be excluded by the logic in kubelingo_tools.py
    (scripts_dir / ".hidden.py").touch()
    (scripts_dir / "__init__.py").touch()
    (scripts_dir / "kubelingo_tools.py").touch()
    (scripts_dir / "maintenance_menu.py").touch()
    (scripts_dir / "full_migrate_and_cleanup.py").touch()
    (scripts_dir / "toolbox.py").touch()
    (scripts_dir / "ckad.py").touch()
    (scripts_dir / "generator.py").touch()

    from scripts import kubelingo_tools
    monkeypatch.setattr(kubelingo_tools, 'scripts_dir', scripts_dir)
    # The script loads a shared context file, which won't exist in test context.
    # The script handles this gracefully, but we can also patch repo_root to be safe.
    monkeypatch.setattr(kubelingo_tools, 'repo_root', tmp_path)

    try:
        kubelingo_tools.main(['run', '--help'])
    except SystemExit as e:
        # --help should exit with 0
        assert e.code == 0

    captured = capsys.readouterr()
    stdout = captured.out

    # Check for scripts that should be present as subcommands
    assert "my-script" in stdout
    assert "another-script" in stdout
    assert "script-with-underscores" in stdout

    # Check for scripts that should be excluded
    assert ".hidden" not in stdout
    assert "__init__" not in stdout
    assert "kubelingo-tools" not in stdout
    assert "maintenance-menu" not in stdout
    assert "full-migrate-and-cleanup" not in stdout
    assert "toolbox" not in stdout
    assert "ckad" not in stdout
    assert "generator" not in stdout


@pytest.fixture
def setup_question_data(tmp_path):
    """Creates a mock question-data directory structure for testing 'manage organize'."""
    question_data = tmp_path / "question-data"

    # Create directories
    json_dir = question_data / "json"
    yaml_dir = question_data / "yaml"
    csv_dir = question_data / "csv"
    md_dir = question_data / "md"

    for d in [json_dir, yaml_dir, csv_dir, md_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Create files to be archived
    (json_dir / "ckad_questions.json").touch()
    (json_dir / "killercoda_ckad.json").touch()
    (yaml_dir / "ckad_questions.yaml").touch()
    (csv_dir / "some_data.csv").touch()
    (md_dir / "a.some-doc.md").touch()
    (md_dir / "killercoda_cheatsheet.md").touch()

    # Create files to be renamed
    (json_dir / "ckad_quiz_data.json").touch()
    (json_dir / "ckad_quiz_data_with_explanations.json").touch()
    (json_dir / "yaml_edit_questions.json").touch()
    (json_dir / "vim_quiz_data.json").touch()

    # A file that should not be touched
    (json_dir / "untouched.json").touch()

    return tmp_path


def test_manage_organize_dry_run(setup_question_data, monkeypatch, capsys):
    """Tests 'manage organize --dry-run' command."""
    from scripts import kubelingo_tools
    monkeypatch.setattr(kubelingo_tools, 'repo_root', setup_question_data)

    kubelingo_tools.main(['manage', 'organize', '--dry-run'])

    captured = capsys.readouterr()
    stdout = captured.out

    # Check for dry-run output
    assert "[DRY-RUN] Move:" in stdout
    assert "ckad_questions.json" in stdout
    assert "killercoda_ckad.json" in stdout
    assert "ckad_questions.yaml" in stdout
    assert "some_data.csv" in stdout
    assert "a.some-doc.md" in stdout
    assert "killercoda_cheatsheet.md" in stdout
    assert "ckad_quiz_data.json" in stdout
    assert "kubernetes.json" in stdout

    # Check that files were NOT moved
    question_data = setup_question_data / "question-data"
    assert (question_data / "json/ckad_questions.json").exists()
    assert not (question_data / "_archive/json/ckad_questions.json").exists()
    assert (question_data / "json/ckad_quiz_data.json").exists()
    assert not (question_data / "json/kubernetes.json").exists()


def test_manage_organize_execution(setup_question_data, monkeypatch, capsys):
    """Tests 'manage organize' command execution."""
    from scripts import kubelingo_tools
    monkeypatch.setattr(kubelingo_tools, 'repo_root', setup_question_data)

    kubelingo_tools.main(['manage', 'organize'])

    captured = capsys.readouterr()
    stdout = captured.out
    
    assert "Moved:" in stdout
    assert "Removed empty dir:" in stdout

    question_data = setup_question_data / "question-data"
    archive_dir = question_data / "_archive"

    # Check archived files
    assert not (question_data / "json/ckad_questions.json").exists()
    assert (archive_dir / "json/ckad_questions.json").exists()

    assert not (question_data / "csv/some_data.csv").exists()
    assert (archive_dir / "csv/some_data.csv").exists()

    assert not (question_data / "md/killercoda_cheatsheet.md").exists()
    assert (archive_dir / "md/killercoda_cheatsheet.md").exists()

    # Check renamed files
    assert not (question_data / "json/ckad_quiz_data.json").exists()
    assert (question_data / "json/kubernetes.json").exists()

    assert not (question_data / "md/a.some-doc.md").exists()
    assert (question_data / "md/some-doc.md").exists()

    # Check untouched file
    assert (question_data / "json/untouched.json").exists()

    # Check empty dir removal
    assert not (question_data / "csv").exists()
    assert not (question_data / "yaml").exists()
    assert (question_data / "json").exists()
    assert (question_data / "md").exists()


@patch('scripts.kubelingo_tools._run_script')
def test_generate_commands(mock_run_script, monkeypatch, tmp_path):
    """Tests that 'generate' subcommands call the correct script."""
    from scripts import kubelingo_tools
    monkeypatch.setattr(kubelingo_tools, 'repo_root', tmp_path)

    # Test each generate subcommand
    kubelingo_tools.main(['generate', 'kubectl-operations'])
    mock_run_script.assert_called_with('generator.py', 'kubectl-operations')

    kubelingo_tools.main(['generate', 'resource-reference'])
    mock_run_script.assert_called_with('generator.py', 'resource-reference')

    kubelingo_tools.main(['generate', 'manifests'])
    mock_run_script.assert_called_with('generator.py', 'manifests')


@patch('subprocess.run')
def test_ckad_commands(mock_subprocess_run, monkeypatch, tmp_path):
    """Tests that 'ckad' subcommands call the correct script with correct args."""
    from scripts import kubelingo_tools

    # The script constructs absolute paths, so we need to know what they are
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    script_path = str(scripts_dir / 'ckad.py')

    monkeypatch.setattr(kubelingo_tools, 'scripts_dir', scripts_dir)
    monkeypatch.setattr(kubelingo_tools, 'repo_root', tmp_path)

    # Test ckad export
    kubelingo_tools.main(['ckad', 'export', '--csv', 'in.csv', '--json', 'out.json', '--yaml', 'out.yaml'])
    expected_cmd = [sys.executable, script_path, 'export', '--csv', 'in.csv', '--json', 'out.json', '--yaml', 'out.yaml']
    mock_subprocess_run.assert_called_with(expected_cmd, check=True)

    # Test ckad import
    kubelingo_tools.main(['ckad', 'import', '--json', 'in.json', '--yaml', 'in.yaml', '--csv', 'out.csv'])
    expected_cmd = [sys.executable, script_path, 'import', '--json', 'in.json', '--yaml', 'in.yaml', '--csv', 'out.csv']
    mock_subprocess_run.assert_called_with(expected_cmd, check=True)

    # Test ckad normalize
    kubelingo_tools.main(['ckad', 'normalize', '--input', 'in.csv', '--output', 'out.csv'])
    expected_cmd = [sys.executable, script_path, 'normalize', '--input', 'in.csv', '--output', 'out.csv']
    mock_subprocess_run.assert_called_with(expected_cmd, check=True)


@patch('subprocess.run')
def test_run_dynamic_script_execution(mock_subprocess_run, monkeypatch, tmp_path):
    """Tests that 'run' executes a script with passthrough arguments."""
    from scripts import kubelingo_tools
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()

    # Create a python script
    py_script = scripts_dir / "my_python_script.py"
    py_script.touch()

    # Create a shell script
    sh_script = scripts_dir / "my_shell_script.sh"
    sh_script.touch()

    monkeypatch.setattr(kubelingo_tools, 'scripts_dir', scripts_dir)
    monkeypatch.setattr(kubelingo_tools, 'repo_root', tmp_path)
    # mock subprocess result
    mock_subprocess_run.return_value.returncode = 0

    # Mock SystemExit to prevent test from stopping
    with patch('sys.exit') as mock_exit:
        # Test python script, with hyphens in name
        kubelingo_tools.main(['run', 'my-python-script', '--arg1', 'val1'])
        expected_py_cmd = [sys.executable, str(py_script), '--arg1', 'val1']
        mock_subprocess_run.assert_called_with(expected_py_cmd)
        mock_exit.assert_called_with(0)

        # Test shell script
        kubelingo_tools.main(['run', 'my-shell-script', 'pos-arg'])
        expected_sh_cmd = ['bash', str(sh_script), 'pos-arg']
        mock_subprocess_run.assert_called_with(expected_sh_cmd)
        mock_exit.assert_called_with(0)
