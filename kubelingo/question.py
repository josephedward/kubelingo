"""
Question schema for unified live exercise mode.
"""
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class QuestionCategory(str, Enum):
    """The four core categories for all questions."""
    OPEN_ENDED = "Open-Ended"
    BASIC = "Basic Terminology"
    COMMAND = "Command Syntax"
    MANIFEST = "YAML Manifest"


class QuestionSubject(str, Enum):
    """Subject matter areas for Kubernetes questions."""
    LINUX_SYNTAX = "Linux Syntax(Commands from Bash, Vim, Kubectl, Docker, Helm)"
    CORE_WORKLOADS = "Core workloads (Pods, ReplicaSets, Deployments; rollouts/rollbacks)"
    POD_DESIGN = "Pod design patterns (initContainers, sidecars, lifecycle hooks)"
    COMMAND_ARGS_ENV = "Commands, args, and env (ENTRYPOINT/CMD overrides, env/envFrom)"
    APP_CONFIGURATION = "App configuration (ConfigMaps, Secrets, projected & downwardAPI volumes)"
    PROBES_HEALTH = "Probes & health (liveness, readiness, startup; graceful shutdown)"
    RESOURCE_MANAGEMENT = "Resource management (requests/limits, QoS classes, HPA basics)"
    JOBS_CRONJOBS = "Jobs & CronJobs (completions, parallelism, backoff, schedules)"
    SERVICES = "Services (ClusterIP/NodePort/LoadBalancer, selectors, headless)"
    INGRESS_ROUTING = "Ingress & HTTP routing (basic rules, paths, service backends)"
    NETWORKING_UTILITIES = "Networking utilities (DNS in-cluster, port-forward, exec, curl)"
    PERSISTENCE = "Persistence (PVCs, using existing StorageClasses, common volume types)"
    OBSERVABILITY_TROUBLESHOOTING = "Observability & troubleshooting (logs, describe/events, kubectl debug/ephemeral containers)"
    METADATA_LABELS_SELECTORS = "Metadata Labels, annotations & selectors (label ops, field selectors, jsonpath)"
    IMPERATIVE_DECLARATIVE = "Imperative vs declarative (—dry-run, create/apply/edit/replace/patch)"
    CONTAINER_IMAGE_REGISTRY = "Container Image & registry use (imagePullPolicy, imagePullSecrets, private registries)"
    SECURITY_BASICS = "Security basics (securityContext, runAsUser/fsGroup, capabilities, readOnlyRootFilesystem)"
    SERVICE_ACCOUNTS = "ServiceAccounts in apps (mounting SA, minimal RBAC needed for app access)"
    SCHEDULING = "Scheduling hints (nodeSelector, affinity/anti-affinity, tolerations)"
    NAMESPACES_CONTEXTS = "Namespaces & contexts (scoping resources, default namespace, context switching)"
    API_DISCOVERY_DOCS = "API discovery & docs (kubectl explain, api-resources, api-versions)"


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
    # The schema category this question belongs to.
    schema_category: Optional["QuestionCategory"] = None
    # Subject matter area for the question.
    subject_matter: Optional["QuestionSubject"] = None

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
    source_file: Optional[str] = None
    triaged: bool = False

    # --- Tracking metadata ---
    created_at: Optional[str] = field(default=None)
    updated_at: Optional[str] = field(default=None)
    content_hash: Optional[str] = field(default=None)

    # --- Legacy compatibility ---
    category: Optional[str] = None
    response: Optional[str] = None
    validation: List[Any] = field(default_factory=list)

    def __post_init__(self):
        # Derive schema_category from question type for schema enforcement if not provided
        if self.schema_category is None:
            # Special override for specific quizzes to be categorized as 'basic'
            source_filename = os.path.basename(self.source_file) if self.source_file else ''
            if source_filename in ('general_operations.yaml', 'resource_types_reference.yaml'):
                self.schema_category = QuestionCategory.BASIC
            elif self.type in ('yaml_author', 'yaml_edit', 'live_k8s_edit'):
                self.schema_category = QuestionCategory.MANIFEST
            elif self.type in ('command', 'live_k8s'):
                self.schema_category = QuestionCategory.COMMAND
            elif self.type == 'socratic':
                self.schema_category = QuestionCategory.OPEN_ENDED
            else:
                # Default for unknown or legacy types.
                self.schema_category = QuestionCategory.COMMAND

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

    def is_solvable(self) -> bool:
        """
        Determines if a question has enough information to be answered and validated.
        """
        if self.type in ('yaml_author', 'yaml_edit'):
            # These need a definitive correct YAML to compare against.
            return bool(self.correct_yaml)

        if self.type == 'command':
            # Command questions can be validated against a list of acceptable commands
            # or through specific validation steps. `answers` holds the commands.
            return bool(self.answers or self.validation_steps)

        if self.type in ('live_k8s', 'live_k8s_edit'):
            # Live exercises require explicit steps to validate the state of the cluster.
            return bool(self.validation_steps)

        if self.type == 'socratic':
            # Socratic questions are conversational and don't have a simple solvable state.
            return True

        # Default to unsolvable for unknown or unspecified types.
        # This includes cases where `type` is None or an empty string.
        return False

