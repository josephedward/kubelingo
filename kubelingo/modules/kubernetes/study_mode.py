from typing import Dict, List

from kubelingo.integrations.llm import get_llm_client


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
    """
    A Socratic tutor for Kubernetes concepts, powered by a configured LLM.
    This class manages the conversation flow, system prompt, and interaction
    with the LLM client.
    """
    def __init__(self):
        """Initializes the study mode, getting a compatible LLM client."""
        self.client = get_llm_client()
        self.conversation_history: List[Dict[str, str]] = []

    def start_study_session(self, topic: str, user_level: str = "intermediate") -> str:
        """
        Starts a new study session on a given topic.

        It builds the initial system and user prompts, gets the first response
        from the LLM, and initializes the conversation history.
        """
        system_prompt = self._build_kubernetes_study_prompt(topic, user_level)
        user_prompt = f"I'm ready to learn about {topic}. Let's start with the basics, assuming I'm at a {user_level} level."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        assistant_response = self.client.chat_completion(messages=messages, temperature=0.7)

        if not assistant_response:
            return "I'm sorry, I'm having trouble connecting to my knowledge base. Please try again later."

        # Initialize history after the first successful exchange
        self.conversation_history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": assistant_response},
        ]

        return assistant_response

    def continue_conversation(self, user_input: str) -> str:
        """
        Continues an existing conversation with new user input.
        """
        if not self.conversation_history:
            return "No active session. Please start a new session."
            
        self.conversation_history.append({"role": "user", "content": user_input})

        assistant_response = self.client.chat_completion(
            messages=self.conversation_history, temperature=0.7
        )

        if not assistant_response:
            return "I'm sorry, I seem to be having connection issues. Could you please repeat your question?"

        self.conversation_history.append({"role": "assistant", "content": assistant_response})
        return assistant_response

    def _build_kubernetes_study_prompt(self, topic: str, level: str) -> str:
        """
        Builds a structured, detailed system prompt optimized for Gemini models.
        """
        return f"""
# **Persona**
You are KubeTutor, an expert on Kubernetes and a friendly, patient Socratic guide. Your goal is to help users achieve a deep, practical understanding of Kubernetes concepts. You are tutoring a user whose skill level is `{level}`.

# **Topic**
The user wants to learn about: **{topic}**.

# **Core Methodology: Socratic Guiding**
- **NEVER give direct answers.** Instead, guide the user with probing questions.
- **Assess understanding** before introducing new concepts. Ask them what they already know about `{topic}`.
- **Use analogies** to connect complex ideas to simpler ones (e.g., "Think of a ReplicaSet as a manager for Pods...").
- **Pose scenarios.** Ask "What if..." or "How would you..." questions to encourage critical thinking. For example: "What do you think would happen if you deleted a Pod managed by a Deployment?"
- **Encourage hands-on thinking.** Prompt them to think about `kubectl` commands or YAML structure. For example: "What `kubectl` command would you use to see the logs of a Pod?" or "What are the essential keys you'd expect in a Pod's YAML manifest?"
- **Keep it concise.** Responses should be short and focused, typically under 150 words, and always end with a question to guide the conversation forward.

# **Strict Rules**
1.  **No Code Snippets:** Do not provide complete YAML files or multi-line `kubectl` commands. Guide the user to build them piece by piece.
2.  **Stay on Topic:** Gently steer the conversation back to `{topic}` if the user strays.
3.  **Positive Reinforcement:** Encourage the user's progress. "Great question!" or "That's exactly right."
4.  **Always End with a Question:** Your primary goal is to prompt the user to think. Every response must end with a question.
"""
