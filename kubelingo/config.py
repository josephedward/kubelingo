"""
Backward-compatibility module to expose top-level configurations.
"""
# Backward-compatibility module to expose top-level configurations.
from kubelingo.utils.config import DEFAULT_DATA_FILE, ENABLED_QUIZZES

# Export default public API
__all__ = ['DEFAULT_DATA_FILE', 'ENABLED_QUIZZES']
