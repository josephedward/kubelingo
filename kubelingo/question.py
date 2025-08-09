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
    Canonical question object for all exercises.

    This schema supports three core question modalities, identified by the `type` field:
      1. socratic        - Open-ended conceptual/resource questions (AI-driven Socratic tutor).
      2. command         - Single-line command quizzes (kubectl, helm, vim) with syntax + AI validation.
      3. yaml_author     - Create manifests from scratch in Vim.
      4. yaml_edit       - Edit templates in Vim to meet requirements.
      5. live_k8s_edit   - Apply manifests to a cluster with post-apply checks.
    """
    # Core identity
    id: str
    prompt: str
    # Question modality
    type: str = 'command'

    # --- Modality-specific fields ---
    # For `command` questions
    answers: List[str] = field(default_factory=list)

    # For manifest-based exercises (`yaml_author`, `yaml_edit`)
    correct_yaml: Optional[str] = None
    initial_files: Dict[str, str] = field(default_factory=dict)

    # For live cluster or shell-based exercises
    pre_shell_cmds: List[str] = field(default_factory=list)
    validation_steps: List[ValidationStep] = field(default_factory=list)

    # --- Common metadata ---
    explanation: Optional[str] = None
    categories: List[str] = field(default_factory=list)
    difficulty: Optional[str] = None
    source: Optional[str] = None
    review: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    validator: Optional[Dict[str, Any]] = None

    # --- Legacy compatibility ---
    category: Optional[str] = None
    response: Optional[str] = None
    validation: List[Any] = field(default_factory=list)

    def __post_init__(self):
        # Map legacy category → categories
        if self.category and not self.categories:
            self.categories = [self.category]
        # Legacy response → answers
        if self.response is not None and not self.answers:
            self.answers = [self.response]
        # Legacy response → validation_steps for command questions
        if self.type == 'command' and self.response and not self.validation_steps and not self.validation:
            try:
                step = ValidationStep(cmd=self.response, matcher={'exit_code': 0})
                self.validation_steps = [step]
            except Exception:
                pass
        # Legacy validation list → validation_steps
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

