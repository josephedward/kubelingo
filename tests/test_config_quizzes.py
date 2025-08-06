"""
Tests for quiz configuration to ensure enabled quiz files exist and no duplicate entries.
"""
import os
import pytest

from kubelingo.utils.config import ENABLED_QUIZZES

def test_enabled_quiz_paths_exist():
    """Ensure each enabled quiz path in config points to an existing file."""
    missing = []
    for name, path in ENABLED_QUIZZES.items():
        if not os.path.exists(path):
            missing.append(f"{name}: {path}")
    assert not missing, f"Enabled quizzes with missing files: {missing}"