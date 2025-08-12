import llm
from typing import Dict, List


KUBERNETES_TOPICS = [
    "Core workloads (Pods, ReplicaSets, Deployments; rollouts/rollbacks)",
    "Pod design patterns (initContainers, sidecars, lifecycle hooks)",
    "Commands, args, and env (ENTRYPOINT/CMD overrides, env/envFrom)",
    "App configuration (ConfigMaps, Secrets, projected & downwardAPI volumes)",
    "Probes & health (liveness, readiness, startup; graceful shutdown)",
    "Resource management (requests/limits, QoS classes, HPA basics)",
    "Jobs & CronJobs (completions, parallelism, backoff, schedules)",
    "Services (ClusterIP/NodePort/LoadBalancer, selectors, headless)",
    "Ingress & HTTP routing (basic rules, paths, service backends)",
    "Networking utilities (DNS in-cluster, port-forward, exec, curl)",
    "Persistence (PVCs, using existing StorageClasses, common volume types)",
    "Observability & troubleshooting (logs, describe/events, kubectl debug/ephemeral containers)",
    "Labels, annotations & selectors (label ops, field selectors, jsonpath)",
    "Imperative vs declarative (—dry-run, create/apply/edit/replace/patch)",
    "Image & registry use (imagePullPolicy, imagePullSecrets, private registries)",
    "Security basics (securityContext, runAsUser/fsGroup, capabilities, readOnlyRootFilesystem)",
    "ServiceAccounts in apps (mounting SA, minimal RBAC needed for app access)",
    "Scheduling hints (nodeSelector, affinity/anti-affinity, tolerations)",
    "Namespaces & contexts (scoping resources, default namespace, context switching)",
    "API discovery & docs (kubectl explain, api-resources, api-versions)"
]


class KubernetesStudyMode:
    """A Socratic tutor for Kubernetes topics, powered by Gemini."""

    def __init__(self, model_id: str = "gemini-1.5-pro-latest"):
        """
        Initializes the study mode with a specific Gemini model.

        Args:
            model_id: The `llm` model ID for the Gemini model to use.

        Raises:
            Exception: If the llm-gemini plugin is not installed or the API key is missing.
        """
        try:
            self.model = llm.get_model(model_id)
            if not self.model.key:
                # The model object may exist but the key might be missing.
                # This will trigger the exception handler in session.py
                raise ValueError("Gemini API key not found.")
        except llm.UnknownModelError:
            raise ImportError("Model not found. Is llm-gemini installed? `pip install llm-gemini`")
        except Exception as e:
            # Re-raise to be caught by the session runner
            raise e

        self.conversation = None

    def start_study_session(self, topic: str, user_level: str = "intermediate") -> str:
        """Initialize a new study session."""
        system_prompt = self._build_kubernetes_study_prompt(topic, user_level)
        user_prompt = f"I want to learn about {topic} in Kubernetes. Can you guide me through it?"

        # Create a new conversation with the system prompt
        self.conversation = self.model.conversation()
        response = self.conversation.prompt(user_prompt, system=system_prompt)

        if not response or not response.text:
            return "I'm sorry, I'm having trouble connecting to my knowledge base. Please try again later."
        
        return response.text

    def continue_conversation(self, user_input: str) -> str:
        """Continue the study conversation."""
        if not self.conversation:
            return "The study session has not been started. Please start a session first."

        response = self.conversation.prompt(user_input)

        if not response or not response.text:
            return "I'm sorry, I seem to be having connection issues. Could you please repeat your question?"

        return response.text

    def _build_kubernetes_study_prompt(self, topic: str, level: str) -> str:
        """Builds a new Socratic-style prompt tailored for Gemini."""
        return f"""
You are an expert Kubernetes tutor. Your name is KubeLingo.
Your student wants to learn about "{topic}".
Their self-assessed skill level is "{level}".

Your teaching style is strictly Socratic. You must guide the student to discover answers themselves.
- NEVER give direct answers, commands, or YAML examples.
- ALWAYS respond with a guiding question.
- Start by assessing their current knowledge of "{topic}". Ask them to explain it in their own words.
- Connect new topics to core concepts like Pods, Services, and Deployments.
- Keep your responses concise, friendly, and encouraging.
- End every response with a question to prompt the student.

Example Interaction:
Student: I want to learn about ConfigMaps.
You: Great! To start, what's your understanding of what a ConfigMap is and what problem it solves in Kubernetes?
Student: I think it's for configuration data.
You: Exactly! And why is it better to use a ConfigMap instead of putting configuration directly inside a container image? What advantage does that give you?
"""
