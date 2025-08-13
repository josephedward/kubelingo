import sys
from unittest.mock import patch, MagicMock, ANY

import pytest

from kubelingo.cli import main, run_interactive_main_menu
from kubelingo.question import QuestionCategory


pytestmark = pytest.mark.filterwarnings("ignore:Can not control echo on the terminal")


@patch('kubelingo.cli.show_history')
def test_cli_history_argument(mock_show_history):
    """Test that `kubelingo --history` calls show_history()."""
    with patch.object(sys, 'argv', ['kubelingo', '--history']):
        # main() contains a loop, so we expect it to break after this command.
        try:
            main()
        except SystemExit:
            pass
        mock_show_history.assert_called_once()


@patch('kubelingo.cli.show_modules')
def test_cli_list_modules_argument(mock_show_modules):
    """Test that `kubelingo --list-modules` calls show_modules()."""
    with patch.object(sys, 'argv', ['kubelingo', '--list-modules']):
        main()
        # It should call show_modules and then exit the loop
        mock_show_modules.assert_called_once()


@patch('questionary.select', autospec=True)
@patch('kubelingo.cli.load_session')
def test_cli_k8s_module_argument(mock_load_session, mock_select):
    """Test that `kubelingo --k8s` loads the kubernetes module."""
    mock_session = MagicMock()
    mock_session.initialize.return_value = True
    mock_load_session.return_value = mock_session

    with patch.object(sys, 'argv', ['kubelingo', '--k8s']):
        main()

    # Check that 'kubernetes' was passed to load_session
    mock_load_session.assert_called_with('kubernetes', ANY)


@patch('kubelingo.sandbox.spawn_pty_shell')
def test_cli_sandbox_pty(mock_spawn_pty_shell):
    """Test that `kubelingo sandbox pty` calls spawn_pty_shell()."""
    with patch.object(sys, 'argv', ['kubelingo', 'sandbox', 'pty']):
        main()
    mock_spawn_pty_shell.assert_called_once()


@patch('kubelingo.sandbox.launch_container_sandbox')
def test_cli_sandbox_docker(mock_launch_container_sandbox):
    """Test that `kubelingo sandbox docker` calls launch_container_sandbox()."""
    with patch.object(sys, 'argv', ['kubelingo', 'sandbox', 'docker']):
        main()
    mock_launch_container_sandbox.assert_called_once()


@patch('kubelingo.sandbox.spawn_pty_shell')
def test_cli_sandbox_default_is_pty(mock_spawn_pty_shell):
    """Test that `kubelingo sandbox` defaults to pty."""
    with patch.object(sys, 'argv', ['kubelingo', 'sandbox']):
        main()
    mock_spawn_pty_shell.assert_called_once()


@patch('kubelingo.sandbox.spawn_pty_shell')
def test_cli_legacy_pty_flag(mock_spawn_pty_shell, capsys):
    """Test that `kubelingo --pty` calls spawn_pty_shell() and warns."""
    with patch.object(sys, 'argv', ['kubelingo', '--pty']):
        main()
    mock_spawn_pty_shell.assert_called_once()
    captured = capsys.readouterr()
    assert "deprecated" in captured.err.lower()


@patch('kubelingo.sandbox.launch_container_sandbox')
def test_cli_legacy_docker_flag(mock_launch_container_sandbox, capsys):
    """Test that `kubelingo --docker` calls launch_container_sandbox() and warns."""
    with patch.object(sys, 'argv', ['kubelingo', '--docker']):
        main()
    mock_launch_container_sandbox.assert_called_once()
    captured = capsys.readouterr()
    assert "deprecated" in captured.err.lower()


@pytest.fixture
def mock_dependencies():
    """Mocks all external dependencies for run_interactive_main_menu."""
    with patch('kubelingo.cli.questionary') as mock_q, \
         patch('kubelingo.cli.KubernetesStudyMode') as mock_ksm_class, \
         patch('kubelingo.cli.get_llm_client'), \
         patch('kubelingo.cli.get_flagged_questions') as mock_gfq, \
         patch('kubelingo.cli._setup_ai_provider_interactive') as mock_setup, \
         patch('kubelingo.cli._run_tools_script') as mock_run_tools, \
         patch('kubelingo.cli.show_session_type_help') as mock_help:

        # Configure KubernetesStudyMode mock
        mock_study_instance = MagicMock()
        mock_study_instance._get_question_count_by_category.return_value = 10
        mock_study_instance.client = True  # Pretend AI client is available
        mock_ksm_class.return_value = mock_study_instance

        # Configure get_flagged_questions mock
        mock_gfq.return_value = [{'id': 'q1'}, {'id': 'q2'}]  # 2 missed questions

        yield {
            "questionary": mock_q,
            "study_mode": mock_study_instance,
            "setup_ai": mock_setup,
            "run_tools": mock_run_tools,
            "show_help": mock_help,
        }


def test_main_menu_learn_socratic_tutor(mock_dependencies):
    """Test selecting 'Study Mode (Socratic Tutor)' calls the correct method."""
    mock_dependencies["questionary"].select.side_effect = [
        MagicMock(ask=MagicMock(return_value=("learn", "socratic"))),
        MagicMock(ask=MagicMock(return_value="exit")),
    ]
    run_interactive_main_menu()
    mock_dependencies["study_mode"]._run_socratic_mode_entry.assert_called_once()


def test_main_menu_learn_missed_questions(mock_dependencies):
    """Test selecting 'Missed Questions' calls the correct method."""
    mock_dependencies["questionary"].select.side_effect = [
        MagicMock(ask=MagicMock(return_value=("learn", "review"))),
        MagicMock(ask=MagicMock(return_value="exit")),
    ]
    run_interactive_main_menu()
    mock_dependencies["study_mode"].review_past_questions.assert_called_once()


def test_main_menu_drill_selection(mock_dependencies):
    """Test selecting a drill option calls the correct method."""
    mock_dependencies["questionary"].select.side_effect = [
        MagicMock(ask=MagicMock(return_value=("drill", QuestionCategory.COMMAND_SYNTAX))),
        MagicMock(ask=MagicMock(return_value="exit")),
    ]
    run_interactive_main_menu()
    mock_dependencies["study_mode"]._run_drill_menu.assert_called_once_with(QuestionCategory.COMMAND_SYNTAX)


def test_main_menu_settings_api_keys(mock_dependencies):
    """Test selecting 'API Keys' calls the interactive setup function."""
    mock_dependencies["questionary"].select.side_effect = [
        MagicMock(ask=MagicMock(return_value=("settings", "api"))),
        MagicMock(ask=MagicMock(return_value="exit")),
    ]
    run_interactive_main_menu()
    mock_dependencies["setup_ai"].assert_called_once_with(force_setup=True)


def test_main_menu_settings_cluster_config(mock_dependencies):
    """Test selecting 'Cluster Configuration' calls the correct method."""
    mock_dependencies["questionary"].select.side_effect = [
        MagicMock(ask=MagicMock(return_value=("settings", "cluster"))),
        MagicMock(ask=MagicMock(return_value="exit")),
    ]
    run_interactive_main_menu()
    mock_dependencies["study_mode"]._cluster_config_menu.assert_called_once()


def test_main_menu_settings_tool_scripts(mock_dependencies):
    """Test selecting 'Tool Scripts' calls the function to run the tools script."""
    mock_dependencies["questionary"].select.side_effect = [
        MagicMock(ask=MagicMock(return_value=("settings", "tools"))),
        MagicMock(ask=MagicMock(return_value="exit")),
    ]
    run_interactive_main_menu()
    mock_dependencies["run_tools"].assert_called_once()


def test_main_menu_settings_triage(mock_dependencies):
    """Test selecting 'Triaged Questions' calls the correct method."""
    mock_dependencies["questionary"].select.side_effect = [
        MagicMock(ask=MagicMock(return_value=("settings", "triage"))),
        MagicMock(ask=MagicMock(return_value="exit")),
    ]
    run_interactive_main_menu()
    mock_dependencies["study_mode"]._view_triaged_questions.assert_called_once()


def test_main_menu_settings_help(mock_dependencies):
    """Test selecting 'Help' calls the correct method."""
    mock_dependencies["questionary"].select.side_effect = [
        MagicMock(ask=MagicMock(return_value=("settings", "help"))),
        MagicMock(ask=MagicMock(return_value="exit")),
    ]
    run_interactive_main_menu()
    mock_dependencies["show_help"].assert_called_once()


def test_main_menu_exit_on_none(mock_dependencies):
    """Test that the menu exits cleanly if questionary returns None (e.g., Ctrl+C)."""
    mock_dependencies["questionary"].select.return_value.ask.return_value = None
    run_interactive_main_menu()
    # Check that no action methods were called
    mock_dependencies["study_mode"]._run_socratic_mode_entry.assert_not_called()
    mock_dependencies["study_mode"].review_past_questions.assert_not_called()
    mock_dependencies["run_tools"].assert_not_called()


