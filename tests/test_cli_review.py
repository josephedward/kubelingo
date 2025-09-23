import pytest
import os
import sys
import json
from unittest.mock import patch, MagicMock

# Adjust the path to import cli.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import cli
from cli import TRIVIA_DESCRIPTIONS, TRIVIA_TERMS
from InquirerPy import inquirer
from enum import Enum

class DifficultyLevel(Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

class FakeAnswer:
    """Fake answer to mimic InquirerPy answer object."""
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value

def setup_fake_inquirer(monkeypatch, text_responses, select_responses, checkbox_responses=None):
    """
    Monkeypatch InquirerPy functions to provide fake text and select responses.
    text_responses: list of strings to return for text prompts in order.
    select_responses: list of strings to return for select prompts in order.
    checkbox_responses: list of lists of strings to return for checkbox prompts in order.
    """
    texts = list(text_responses)
    selects = list(select_responses)
    checkboxes = list(checkbox_responses) if checkbox_responses is not None else []

    def fake_text(message):
        if not texts:
            pytest.fail(f"No more text responses left for prompt: {message}")
        return FakeAnswer(texts.pop(0))

    def fake_select(message, choices=None, default=None):
        if not selects:
            pytest.fail(f"No more select responses left for prompt: {message}")
        return FakeAnswer(selects.pop(0))

    def fake_checkbox(message, choices=None):
        if not checkboxes:
            pytest.fail(f"No more checkbox responses left for prompt: {message}")
        val = checkboxes.pop(0)
        if isinstance(val, list):
            return FakeAnswer(val)
        return FakeAnswer([val])

    monkeypatch.setattr(inquirer, 'text', fake_text)
    monkeypatch.setattr(inquirer, 'select', fake_select)
    monkeypatch.setattr(inquirer, 'checkbox', fake_checkbox)

@pytest.fixture
def mock_ai_chat(monkeypatch):
    with patch('cli.ai_chat') as mock_chat:
        yield mock_chat

@pytest.fixture
def mock_console_print(monkeypatch):
    with patch('cli.console.print') as mock_print:
        yield mock_print

def test_review_correct_no_files(monkeypatch, mock_console_print):
    setup_fake_inquirer(monkeypatch, text_responses=[""], select_responses=[], checkbox_responses=[[]])
    monkeypatch.setattr(os, 'listdir', lambda x: [])
    cli.review_correct()
    mock_console_print.assert_called_with("[bold yellow]No YAML files found to review.[/bold yellow]")

def test_review_incorrect_no_files(monkeypatch, mock_console_print):
    setup_fake_inquirer(monkeypatch, text_responses=[""], select_responses=[], checkbox_responses=[[]])
    monkeypatch.setattr(os, 'listdir', lambda x: [])
    cli.review_incorrect()
    mock_console_print.assert_called_with("[bold yellow]No YAML files found to review.[/bold yellow]")

def test_review_correct_with_files(monkeypatch, mock_ai_chat, mock_console_print):
    # Mock os.listdir to return dummy YAML files
    monkeypatch.setattr(os, 'listdir', lambda x: ["test1.yaml", "test2.yaml"])
    # Mock open to return dummy YAML content
    mock_open = MagicMock()
    mock_open.side_effect = [
        MagicMock(read_data='question: q1\nsuggested_answer: s1\nuser_answer: u1'),
        MagicMock(read_data='question: q2\nsuggested_answer: s2\nuser_answer: u2')
    ]
    with patch('builtins.open', mock_open):
        # Mock inquirer responses
        setup_fake_inquirer(
            monkeypatch,
            text_responses=["", ""], # For directory path and follow-up
            select_responses=[],
            checkbox_responses=[["test1.yaml", "test2.yaml"]] # Select all files
        )
        # Mock ai_chat response
        mock_ai_chat.return_value = "AI feedback for correct answers."

        cli.review_correct()

        # Assertions
        mock_ai_chat.assert_called_once()
        assert "AI Feedback:" in mock_console_print.call_args_list[0].args[0]

def test_review_incorrect_with_files(monkeypatch, mock_ai_chat, mock_console_print):
    # Mock os.listdir to return dummy YAML files
    monkeypatch.setattr(os, 'listdir', lambda x: ["test1.yaml", "test2.yaml"])
    # Mock open to return dummy YAML content
    mock_open = MagicMock()
    mock_open.side_effect = [
        MagicMock(read_data='question: q1\nsuggested_answer: s1\nuser_answer: u1'),
        MagicMock(read_data='question: q2\nsuggested_answer: s2\nuser_answer: u2')
    ]
    with patch('builtins.open', mock_open):
        # Mock inquirer responses
        setup_fake_inquirer(
            monkeypatch,
            text_responses=["", ""], # For directory path and follow-up
            select_responses=[],
            checkbox_responses=[["test1.yaml", "test2.yaml"]] # Select all files
        )
        # Mock ai_chat response
        mock_ai_chat.return_value = "AI feedback for incorrect answers."

        cli.review_incorrect()

        # Assertions
        mock_ai_chat.assert_called_once()
        assert "AI Feedback:" in mock_console_print.call_args_list[0].args[0]
