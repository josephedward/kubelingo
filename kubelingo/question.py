"""
Question schema for unified live exercise mode.
"""
import os
from dataclasses import dataclass, field, KW_ONLY
from enum import Enum
from typing import Any, Dict, List, Optional


class QuestionCategory(str, Enum):
    """High-level category for a question, determining its evaluation method."""
    OPEN_ENDED = "Open-Ended"
    BASIC_TERMINOLOGY = "Basic Terminology"
    COMMAND_SYNTAX = "Command Syntax"
    YAML_MANIFEST = "YAML Manifest"


class QuestionSubject(str, Enum):
    """Subject matter areas for Kubernetes questions."""
    LINUX_SYNTAX = "Linux Syntax"
    CORE_WORKLOADS = "Core workloads"
    POD_DESIGN = "Pod design patterns"
    COMMAND_ARGS_ENV = "Commands, args, and env"
    APP_CONFIGURATION = "App configuration"
    PROBES_HEALTH = "Probes & health"
    RESOURCE_MANAGEMENT = "Resource management"
    JOBS_CRONJOBS = "Jobs & CronJobs"
    SERVICES = "Services"
    INGRESS_ROUTING = "Ingress/Egress & HTTP routing"
    NETWORKING_UTILITIES = "Networking utilities"
    PERSISTENCE = "Persistence"
    OBSERVABILITY_TROUBLESHOOTING = "Observability & troubleshooting"
    LABELS_SELECTORS = "Metadata Labels, annotations & selectors"
    IMPERATIVE_DECLARATIVE = "Imperative vs declarative"
    IMAGE_REGISTRY = "Container Image & registry use"
    SECURITY_BASICS = "Security basics"
    SERVICE_ACCOUNTS = "ServiceAccounts in apps"
    SCHEDULING = "Scheduling hints"
    NAMESPACES_CONTEXTS = "Namespaces & contexts"
    API_DISCOVERY_DOCS = "API discovery & docs"
    HELM = "Helm"
    HELM_BASICS = "Helm Basics"
    VIM_BASICS = "Vim Basics"


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
    _: KW_ONLY
    """
    Canonical question object for all exercises.

    This schema supports several core question modalities, identified by the `type` field.
    The `type` dictates which fields are required for the question to be solvable.

    Supported types:
    - 'socratic': Open-ended conceptual questions for AI-driven tutoring.
        - Required: `prompt`.
    - 'command': Single-line command quizzes (e.g., kubectl, helm, vim).
        - Required: `prompt`.
        - Solvable with: `answers` (list of valid commands) OR `validation_steps`.
    - 'basic_terminology': Questions about definitions and concepts.
        - Required: `prompt`.
        - Solvable with: `answers` (list of correct terms/phrases).
    - 'yaml_author': Create a YAML manifest from scratch.
        - Required: `prompt`.
        - Solvable with: `correct_yaml`.
    - 'yaml_edit': Edit a template YAML to meet requirements.
        - Required: `prompt`, `initial_files`.
        - Solvable with: `correct_yaml`.
    - 'live_k8s_edit': Apply/edit manifests on a live cluster and run checks.
        - Required: `prompt`.
        - Solvable with: `validation_steps`.
    """
    # Core identity
    id: str
    prompt: str
    # Question modality
    type_: str = 'command'
    # The schema category this question belongs to.
    category: Optional[str] = None
    # Subject matter area for the question.
    subject: Optional[str] = None

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
    source: Optional[str] = None
    difficulty: Optional[str] = None
    review: bool = False  # Automatically managed based on answer correctness
    triage: bool = False  # Manually flagged by user for being problematic
    metadata: Dict[str, Any] = field(default_factory=dict)
    validator: Optional[Dict[str, Any]] = None
    source_file: Optional[str] = None
    triaged: bool = False

    # --- Tracking metadata ---
    created_at: Optional[str] = field(default=None)
    updated_at: Optional[str] = field(default=None)
    content_hash: Optional[str] = field(default=None)

    # --- Legacy compatibility ---
    category: Optional[str] = None
    response: Optional[str] = None

    def __post_init__(self):
        # Ensure category_id is an enum member if provided as a string
        if isinstance(self.category_id, str):
            try:
                self.category_id = QuestionCategory(self.category_id)
            except ValueError:
                # If it's not a valid category, we'll let it be derived from type.
                self.category_id = None
        
        # Handle legacy 'category' field if category_id is not yet set
        if self.category and not self.category_id:
            try:
                # Find enum member by value (case-insensitive for robustness)
                for member in QuestionCategory:
                    if member.value.lower() == self.category.lower():
                        self.category_id = member
                        break
            except ValueError:
                pass  # Ignore if not a valid category string

        # Ensure subject_id is an enum member if provided as a string
        if isinstance(self.subject_id, str):
            try:
                self.subject_id = QuestionSubject(self.subject_id)
            except ValueError:
                self.subject_id = None

        # Handle legacy `subject` field and convert to subject_id
        if self.subject and not self.subject_id:
            try:
                self.subject_id = QuestionSubject(self.subject)
            except ValueError:
                pass  # Ignore invalid legacy subjects

        # Derive category_id from question type for schema enforcement if not provided
        if self.category_id is None:
            if self.type_ == 'socratic':
                self.category_id = QuestionCategory.OPEN_ENDED
            elif self.type_ in ('basic_terminology', 'basic'):
                self.category_id = QuestionCategory.BASIC_TERMINOLOGY
            elif self.type_ == 'command':
                self.category_id = QuestionCategory.COMMAND_SYNTAX
            elif self.type_ in ('yaml_author', 'yaml_edit', 'live_k8s_edit'):
                self.category_id = QuestionCategory.YAML_MANIFEST
            else:
                # Default for unknown or legacy types.
                self.category_id = QuestionCategory.COMMAND_SYNTAX

        # Legacy compatibility mapping
        if self.category and not self.categories:
            self.categories = [self.category]
        if self.response is not None and not self.answers:
            self.answers = [self.response]

    def is_solvable(self) -> bool:
        """
        Determines if a question has enough information to be answered and validated.
        """
        if self.type_ in ('yaml_author', 'yaml_edit'):
            # These need a definitive correct YAML to compare against.
            return bool(self.correct_yaml)

        if self.type_ == 'command':
            # Command questions can be validated against a list of acceptable commands
            # or through specific validation steps. `answers` holds the commands.
            return bool(self.answers or self.validation_steps)

        if self.type_ in ('live_k8s', 'live_k8s_edit'):
            # Live exercises require explicit steps to validate the state of the cluster.
            return bool(self.validation_steps)

        if self.type_ == 'socratic':
            # Socratic questions are conversational and don't have a simple solvable state.
            return True

        # Default to unsolvable for unknown or unspecified types.
        # This includes cases where `type` is None or an empty string.
        return False

