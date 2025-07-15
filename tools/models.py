from dataclasses import dataclass
from typing import Optional


@dataclass
class Question:
    """Represents a single quiz question."""
    question: str
    answer: str
    explanation: Optional[str] = None
