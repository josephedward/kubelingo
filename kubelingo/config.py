"""
Backward-compatibility module to expose top-level configurations.
"""
from kubelingo.utils.config import ENABLED_QUIZZES

# Export default public API
__all__ = ['ENABLED_QUIZZES']
