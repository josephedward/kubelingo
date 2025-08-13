import sys
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

# Add repo root to sys.path to allow importing kubelingo_tools from the scripts directory
repo_root = Path(__file__).resolve().parent.parent.parent
scripts_path = repo_root / 'scripts'
sys.path.insert(0, str(scripts_path))
sys.path.insert(0, str(repo_root))

# Now we can import the script as a module
import kubelingo_tools


@pytest.fixture
def mock_run_script():
    """Fixture to mock the _run_script helper function."""
    with patch('kubelingo_tools._run_script') as mock:
        yield mock


@pytest.fixture
def mock_subprocess_run():
    """Fixture to mock subprocess.run."""
    with patch('subprocess.run') as mock:
        yield mock


@pytest.fixture
def mock_questionary():
    """Fixture to mock the questionary library for interactive tests."""
    # Mock the entire questionary module before it's imported inside functions.
    mock_q_module = MagicMock()
    # Mock the Separator class which is imported separately.
    # The class itself is not used, just its existence for the import.
    mock_q_module.Separator = MagicMock()

    # When the code under test does `import questionary`, it will get our mock.
    with patch.dict('sys.modules', {'questionary': mock_q_module}):
        yield mock_q_module


def run_tools_main(*args):
    """Helper to run the main function of the tool with a list of arguments."""
    # We call main directly with args, avoiding patching sys.argv
    kubelingo_tools.main(list(args))


# --- Tests for individual task functions ---

def test_task_functions_call_run_script(mock_run_script):
    """Test that individual task functions call _run_script correctly."""
    kubelingo_tools.task_run_bug_ticket()
    mock_run_script.assert_called_with("bug_ticket.py")

    kubelingo_tools.task_run_generator()
    mock_run_script.assert_called_with("generator.py")

    kubelingo_tools.task_run_question_manager()
    mock_run_script.assert_called_with("question_manager.py")

    kubelingo_tools.task_run_sqlite_manager()
    mock_run_script.assert_called_with("sqlite_manager.py")

    kubelingo_tools.task_run_yaml_manager()
    mock_run_script.assert_called_with("yaml_manager.py")


# --- Tests for Interactive Menu ---

@patch('kubelingo_tools.task_tool_scripts')
def test_main_no_args_runs_menu(mock_task_tool_scripts):
    """Test that running the script with no arguments launches the tool scripts menu."""
    kubelingo_tools.main([])
    mock_task_tool_scripts.assert_called_once()

def test_task_tool_scripts_select_and_run(mock_questionary, mock_run_script):
    """Test that selecting a script from the menu runs it."""
    # Simulate user selecting "generator.py"
    mock_questionary.select.return_value.ask.return_value = "generator.py"
    kubelingo_tools.task_tool_scripts()
    # The task function should call _run_script
    mock_run_script.assert_called_with("generator.py")

def test_task_tool_scripts_back(mock_questionary, mock_run_script):
    """Test that selecting 'Back' from the menu does nothing."""
    mock_questionary.select.return_value.ask.return_value = "Back"
    kubelingo_tools.task_tool_scripts()
    mock_run_script.assert_not_called()


# --- Tests for main() and argument parsing ---

@patch('kubelingo_tools.run_quiz')
def test_main_quiz_command(mock_run_quiz):
    """Test the 'quiz' subcommand forwards arguments correctly."""
    run_tools_main('quiz', '--subject', 'pods', '-n', '5')
    mock_run_quiz.assert_called_once()
    args, _ = mock_run_quiz.call_args
    assert args[0].quiz_args == ['--subject', 'pods', '-n', '5']


@patch('kubelingo_tools.manage_organize')
def test_main_manage_organize_command(mock_manage_organize):
    """Test the 'manage organize' subcommand."""
    run_tools_main('manage', 'organize', '--dry-run')
    mock_manage_organize.assert_called_once()
    args, _ = mock_manage_organize.call_args
    assert args[0].dry_run is True


@patch('kubelingo_tools.generate_manifests')
def test_main_generate_manifests_command(mock_generate_manifests):
    """Test the 'generate manifests' subcommand."""
    run_tools_main('generate', 'manifests')
    mock_generate_manifests.assert_called_once()


@patch('kubelingo_tools.ckad_export')
def test_main_ckad_export_command(mock_ckad_export):
    """Test the 'ckad export' subcommand."""
    run_tools_main('ckad', 'export', '--csv', 'file.csv')
    mock_ckad_export.assert_called_once()


@patch('kubelingo_tools.run_dynamic_script')
def test_main_run_dynamic_script_command(mock_run_dynamic_script):
    """Test the 'run' subcommand for dynamic script execution."""
    with patch('kubelingo_tools.scripts_dir') as mock_scripts_dir:
        mock_script_path = MagicMock(spec=Path)
        mock_script_path.is_file.return_value = True
        mock_script_path.name = 'my_dynamic_script.py'
        mock_script_path.stem = 'my_dynamic_script'
        mock_scripts_dir.iterdir.return_value = [mock_script_path]

        run_tools_main('run', 'my-dynamic-script', '--arg1', 'val1')

    mock_run_dynamic_script.assert_called_once()
    args, _ = mock_run_dynamic_script.call_args
    assert args[0].script_name == 'my-dynamic-script'
    assert args[0].script_args == ['--arg1', 'val1']
    assert args[0].script_path == mock_script_path


# --- Tests for file system operations ---

@pytest.fixture
def question_data_dir(tmp_path):
    """Create a temporary directory structure mimicking the real 'question-data' folder."""
    q_data = tmp_path / 'question-data'
    json_dir = q_data / 'json'
    yaml_dir = q_data / 'yaml'
    csv_dir = q_data / 'csv'
    md_dir = q_data / 'md'

    for d in [json_dir, yaml_dir, csv_dir, md_dir]:
        d.mkdir(parents=True)

    # Create files to be archived
    (json_dir / 'ckad_questions.json').touch()
    (yaml_dir / 'ckad_questions.yml').touch()
    (csv_dir / 'legacy.csv').touch()
    # Create files to be renamed
    (json_dir / 'ckad_quiz_data.json').touch()
    (json_dir / 'vim_quiz_data.json').touch()
    # Create markdown files for prefix stripping test
    (md_dir / 'a.some-doc.md').touch()
    (md_dir / 'killercoda_cheatsheet.md').touch()

    return tmp_path


def test_manage_organize_dry_run(question_data_dir, capsys):
    """Test the 'manage organize' command in --dry-run mode."""
    args = MagicMock(dry_run=True)

    with patch('kubelingo_tools.repo_root', question_data_dir):
        kubelingo_tools.manage_organize(args)

    archive_dir = question_data_dir / 'question-data' / '_archive'
    
    # Assert that no files were actually moved
    assert (question_data_dir / 'question-data' / 'json' / 'ckad_questions.json').exists()
    assert not (archive_dir / 'json' / 'ckad_questions.json').exists()

    # Check that output contains dry-run messages
    captured = capsys.readouterr()
    assert "[DRY-RUN] Move:" in captured.out


def test_manage_organize_execution(question_data_dir):
    """Test that 'manage organize' correctly moves and renames files."""
    args = MagicMock(dry_run=False)

    with patch('kubelingo_tools.repo_root', question_data_dir):
        kubelingo_tools.manage_organize(args)

    q_root = question_data_dir / 'question-data'
    archive_dir = q_root / '_archive'
    json_dir = q_root / 'json'
    md_dir = q_root / 'md'

    # Check archived files
    assert (archive_dir / 'json' / 'ckad_questions.json').exists()
    assert (archive_dir / 'md' / 'killercoda_cheatsheet.md').exists()

    # Check renamed files
    assert (json_dir / 'kubernetes.json').exists()
    assert not (json_dir / 'ckad_quiz_data.json').exists()

    # Check markdown prefix stripping
    assert (md_dir / 'some-doc.md').exists()
    assert not (md_dir / 'a.some-doc.md').exists()

    # Check that empty 'csv' dir was removed
    assert not (q_root / 'csv').exists()
