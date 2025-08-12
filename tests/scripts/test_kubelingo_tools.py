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
    # Since questionary is imported dynamically inside functions, we use
    # create=True to allow patching an attribute that doesn't exist at import time.
    with patch('kubelingo_tools.questionary', create=True) as mock:
        with patch('kubelingo_tools.Separator', create=True):
            yield mock


def run_tools_main(*args):
    """Helper to run the main function of the tool with a list of arguments."""
    # We call main directly with args, avoiding patching sys.argv
    kubelingo_tools.main(list(args))


# --- Tests for individual task functions ---

def test_task_functions_call_run_script(mock_run_script):
    """Test that various task functions call _run_script with correct arguments."""
    kubelingo_tools.task_index_yaml()
    mock_run_script.assert_called_with("index_yaml_files.py")

    kubelingo_tools.task_create_sqlite_backup()
    mock_run_script.assert_called_with("consolidate_dbs.py")

    kubelingo_tools.task_deduplicate_questions()
    mock_run_script.assert_called_with("question_manager.py", "deduplicate")


def test_task_full_migrate_and_cleanup(mock_run_script, mock_subprocess_run):
    """Test the full migration pipeline function."""
    # Mock filesystem and utility functions to isolate the logic
    with patch('kubelingo_tools.Path.exists', return_value=False), \
         patch('kubelingo_tools.shutil.copy2'), \
         patch('pathlib.Path.mkdir'), \
         patch('kubelingo_tools.repo_root', Path('/fake/repo')):
        kubelingo_tools.task_full_migrate_and_cleanup()

    expected_script_calls = [
        call('generator.py', 'manifests'),
        call('consolidate_manifests.py'),
        call('merge_solutions.py')
    ]
    mock_run_script.assert_has_calls(expected_script_calls)

    expected_subprocess_calls = [
        call(['kubelingo', 'migrate-yaml'], check=False),
        call(['kubelingo', 'import-json'], check=False)
    ]
    mock_subprocess_run.assert_has_calls(expected_subprocess_calls)


# --- Tests for Interactive Menu ---

def test_run_interactive_menu_select_task(mock_questionary):
    """Test that selecting a task from the menu calls the correct function."""
    # Simulate user selecting "Deduplicate Questions" then "Cancel"
    mock_questionary.select.return_value.ask.side_effect = ["Deduplicate Questions", "Cancel"]

    with patch('kubelingo_tools.task_deduplicate_questions') as mock_task:
        kubelingo_tools.run_interactive_menu()

    mock_task.assert_called_once()


def test_run_interactive_menu_cancel_immediately(mock_questionary):
    """Test that the menu exits gracefully when user selects Cancel."""
    mock_questionary.select.return_value.ask.return_value = "Cancel"
    # The function should exit the loop and finish without calling any task
    kubelingo_tools.run_interactive_menu()


# --- Tests for main() and argument parsing ---

@patch('kubelingo_tools.run_interactive_menu')
def test_main_no_args_runs_menu(mock_run_interactive_menu):
    """Test that running the script with no arguments launches the interactive menu."""
    kubelingo_tools.main([])
    mock_run_interactive_menu.assert_called_once()


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


@patch('kubelingo_tools.task_full_migrate_and_cleanup')
def test_main_full_migrate_command(mock_task_full_migrate):
    """Test the 'full-migrate' subcommand."""
    run_tools_main('full-migrate')
    mock_task_full_migrate.assert_called_once()


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
