import pytest
from unittest.mock import patch, MagicMock

from kubelingo.modules.kubernetes.study_mode import KubernetesStudyMode


@pytest.fixture
def mock_gemini_client():
    """Fixture to mock the GeminiClient used in KubernetesStudyMode."""
    with patch("kubelingo.modules.kubernetes.study_mode.GeminiClient") as mock:
        instance = mock.return_value
        instance.chat_completion = MagicMock()
        yield instance


def test_start_study_session_success(mock_gemini_client):
    """
    Tests that a study session starts successfully when the LLM call succeeds.
    """
    # Arrange
    mock_gemini_client.chat_completion.return_value = "Hello! Let's talk about Pods."
    study_mode = KubernetesStudyMode()

    # Act
    response = study_mode.start_study_session("Pods", "beginner")

    # Assert
    assert response == "Hello! Let's talk about Pods."
    assert study_mode.session_active is True
    assert len(study_mode.conversation_history) == 3  # system, user, assistant
    assert study_mode.conversation_history[0]["role"] == "system"
    assert study_mode.conversation_history[2]["content"] == "Hello! Let's talk about Pods."
    mock_gemini_client.chat_completion.assert_called_once()


def test_start_study_session_failure_on_llm_none(mock_gemini_client):
    """
    Tests that a study session fails gracefully if the LLM returns None.
    """
    # Arrange
    mock_gemini_client.chat_completion.return_value = None
    study_mode = KubernetesStudyMode()

    # Act
    response = study_mode.start_study_session("Pods", "beginner")

    # Assert
    assert response is None
    assert study_mode.session_active is False
    assert len(study_mode.conversation_history) == 0


def test_start_study_session_failure_on_llm_exception(mock_gemini_client):
    """
    Tests that a study session fails gracefully if the LLM call raises an exception.
    """
    # Arrange
    mock_gemini_client.chat_completion.side_effect = Exception("API Error")
    study_mode = KubernetesStudyMode()

    # Act
    response = study_mode.start_study_session("Pods", "beginner")

    # Assert
    assert response is None
    assert study_mode.session_active is False
    assert len(study_mode.conversation_history) == 0


def test_continue_conversation_success(mock_gemini_client):
    """
    Tests continuing a conversation successfully.
    """
    # Arrange
    study_mode = KubernetesStudyMode()
    study_mode.session_active = True
    study_mode.conversation_history = [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "Initial prompt"},
        {"role": "assistant", "content": "Initial response"},
    ]
    mock_gemini_client.chat_completion.return_value = "That is a great question!"

    # Act
    response = study_mode.continue_conversation("What about containers?")

    # Assert
    assert response == "That is a great question!"
    assert len(study_mode.conversation_history) == 5  # system, user, assistant, user, assistant
    assert study_mode.conversation_history[3]["role"] == "user"
    assert study_mode.conversation_history[3]["content"] == "What about containers?"
    mock_gemini_client.chat_completion.assert_called_once()


def test_continue_conversation_inactive_session(mock_gemini_client):
    """
    Tests that continue_conversation returns an error if the session is not active.
    """
    # Arrange
    study_mode = KubernetesStudyMode()
    study_mode.session_active = False

    # Act
    response = study_mode.continue_conversation("This should not be sent.")

    # Assert
    assert response == "The study session has not been started. Please start a session first."
    mock_gemini_client.chat_completion.assert_not_called()


def test_continue_conversation_llm_failure(mock_gemini_client):
    """
    Tests that continue_conversation handles an LLM failure gracefully.
    """
    # Arrange
    study_mode = KubernetesStudyMode()
    study_mode.session_active = True
    study_mode.conversation_history = [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "Initial prompt"},
        {"role": "assistant", "content": "Initial response"},
    ]
    mock_gemini_client.chat_completion.return_value = None

    # Act
    response = study_mode.continue_conversation("Another question")

    # Assert
    assert response == "I'm sorry, I seem to be having connection issues. Could you please repeat your question?"
    # History should contain the user's question, but not the failed assistant response
    assert len(study_mode.conversation_history) == 4
