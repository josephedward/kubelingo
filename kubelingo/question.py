"""
Question schema for unified live exercise mode.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class ValidationStep:
    """
    A single validation step: run `cmd` and apply `matcher` to its output.
    matcher could specify JSONPath, regex, substring, etc.
    """
    cmd: str
    matcher: Dict[str, Any]

@dataclass
class Question:
    """
    Canonical question object for live exercises and quizzes.
    """
    id: str                           # unique identifier, e.g. 'module::index'
    prompt: str                       # text shown to the user
    runner: str                       # 'shell' or 'vim', selects interaction style
    initial_cmds: List[str] = field(default_factory=list)
    initial_yaml: Optional[str] = None
    validations: List[ValidationStep] = field(default_factory=list)
    explanation: Optional[str] = None
    categories: List[str] = field(default_factory=list)
    difficulty: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)