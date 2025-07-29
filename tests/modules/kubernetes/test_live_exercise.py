import logging
import subprocess
from unittest.mock import patch, MagicMock, call
import pytest

from kubelingo.modules.kubernetes.session import NewSession, PromptSession

# Mock logger for the session
@pytest.fixture
def mock_logger():
    return MagicMock(spec=logging.Logger)

# Mock successful subprocess result
@pytest.fixture
def mock_success_proc():
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.returncode = 0
    proc.stdout = "Success"
    proc.stderr = ""
    return proc

# Mock failed subprocess result
@pytest.fixture
def mock_fail_proc():
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.returncode = 1
    proc.stdout = ""
    proc.stderr = "Validation failed"
    return proc

@patch('kubelingo.modules.kubernetes.session.os.chmod')
@patch('kubelingo.modules.kubernetes.session.os.remove')
@patch('kubelingo.modules.kubernetes.session.tempfile.NamedTemporaryFile')
def test_live_exercise_success(mock_tempfile, mock_remove, mock_chmod, mock_logger, mock_success_proc):
    """
    Tests a successful run of a live exercise where the user enters a valid command
    and the validation script passes.
    """
    # Arrange
    # Mock the temporary file for the assertion script
    mock_file = MagicMock()
    mock_file.__enter__.return_value.name = '/tmp/assert.sh'
    mock_tempfile.return_value = mock_file

    session = NewSession(mock_logger)
    question = {
        'type': 'live_k8s',
        'prompt': 'Create a pod.',
        'assert_script': '#!/bin/bash\nexit 0'
    }

    # Simulate user input: a kubectl command, then 'done'
    user_commands = ['kubectl create pod my-pod --image=nginx', 'done']

    with patch('kubelingo.modules.kubernetes.session.PromptSession.prompt', side_effect=user_commands) as mock_prompt, \
         patch('kubelingo.modules.kubernetes.session.subprocess.run') as mock_run:
        
        # The first call is the user's command, the second is the validation script
        mock_run.side_effect = [mock_success_proc, mock_success_proc]

        # Act
        session._run_one_exercise(question)

        # Assert
        # Check that the shell prompt was called for each simulated user command
        assert mock_prompt.call_count == len(user_commands)

        # Check that subprocess.run was called for the user command and the validation script
        expected_calls = [
            call(['kubectl', 'create', 'pod', 'my-pod', '--image=nginx'], capture_output=True, text=True, check=False),
            call(['bash', '/tmp/assert.sh'], capture_output=True, text=True)
        ]
        mock_run.assert_has_calls(expected_calls)

        # Check that the logger recorded a correct result
        mock_logger.info.assert_called_with(f"Live exercise: prompt=\"{question['prompt']}\" result=\"correct\"")

@patch('kubelingo.modules.kubernetes.session.os.chmod')
@patch('kubelingo.modules.kubernetes.session.os.remove')
@patch('kubelingo.modules.kubernetes.session.tempfile.NamedTemporaryFile')
def test_live_exercise_failure(mock_tempfile, mock_remove, mock_chmod, mock_logger, mock_fail_proc):
    """
    Tests a failed run where the user finishes but the validation script fails.
    """
    # Arrange
    mock_file = MagicMock()
    mock_file.__enter__.return_value.name = '/tmp/assert.sh'
    mock_tempfile.return_value = mock_file

    session = NewSession(mock_logger)
    question = {
        'type': 'live_k8s',
        'prompt': 'Create a pod.',
        'assert_script': '#!/bin/bash\nexit 1'
    }
    user_commands = ['done'] # User does nothing, fails validation

    with patch('kubelingo.modules.kubernetes.session.PromptSession.prompt', side_effect=user_commands) as mock_prompt, \
         patch('kubelingo.modules.kubernetes.session.subprocess.run', return_value=mock_fail_proc) as mock_run:

        # Act
        session._run_one_exercise(question)

        # Assert
        assert mock_prompt.call_count == len(user_commands)
        mock_run.assert_called_once_with(['bash', '/tmp/assert.sh'], capture_output=True, text=True)
        mock_logger.info.assert_called_with(f"Live exercise: prompt=\"{question['prompt']}\" result=\"incorrect\"")
