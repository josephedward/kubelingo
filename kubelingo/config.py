"""
Backward-compatibility module to expose top-level configurations.
"""
# Backward-compatibility module to expose top-level configurations.
from kubelingo.utils.config import (
    BASIC_QUIZZES,
    COMMAND_QUIZZES,
    ENABLED_QUIZZES,
    MANIFEST_QUIZZES,
)

# Export default public API
__all__ = [
    'BASIC_QUIZZES',
    'COMMAND_QUIZZES',
    'ENABLED_QUIZZES',
    'MANIFEST_QUIZZES',
]
