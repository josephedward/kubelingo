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
    Canonical question object for unified shell exercises and quizzes.
    Supports legacy aliases: category, response, validation.
    """
    # Core fields
    id: str
    prompt: str
    # Legacy compatibility aliases
    category: Optional[str] = None
    response: Optional[str] = None
    validation: List[Any] = field(default_factory=list)
    # Question type, e.g. 'command', 'live_k8s', etc.
    type: str = ''
    # Shell preparation commands
    pre_shell_cmds: List[str] = field(default_factory=list)
    # Files to seed workspace
    initial_files: Dict[str, str] = field(default_factory=dict)
    # Steps to run after shell exit
    validation_steps: List[ValidationStep] = field(default_factory=list)
    # For AI-based validation
    validator: Optional[Dict[str, Any]] = None
    # Metadata
    explanation: Optional[str] = None
    categories: List[str] = field(default_factory=list)
    difficulty: Optional[str] = None
    review: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Map legacy 'category' to categories list
        if self.category:
            # Override categories if category alias provided
            self.categories = [self.category]
        # Map legacy 'response' to validation_steps if none provided
        if self.response is not None and not self.validation_steps and not self.validation:
            try:
                step = ValidationStep(cmd=self.response, matcher={'contains': self.response})
                self.validation_steps = [step]
            except Exception:
                pass
        # Map legacy 'validation' list to validation_steps if provided
        if self.validation and not self.validation_steps:
            steps = []
            for v in self.validation:
                if isinstance(v, ValidationStep):
                    steps.append(v)
                elif isinstance(v, dict):
                    cmd = v.get('cmd') or v.get('command') or ''
                    matcher = v.get('matcher', {})
                    steps.append(ValidationStep(cmd=cmd, matcher=matcher))
            if steps:
                self.validation_steps = steps

