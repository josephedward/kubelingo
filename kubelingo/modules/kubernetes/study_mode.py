import json
import logging
from typing import Dict, List, Optional

from kubelingo.integrations.llm import GeminiClient

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
    "API discovery & docs (kubectl explain, api-resources, api-versions)",
    "Vim for YAML editing (modes, navigation, editing commands)",
    "Helm for Package Management (charts, releases, repositories)",
    "Advanced Kubectl Usage (jsonpath, patch, custom columns)",
    "Kubernetes API Resources (exploring objects with explain and api-resources)"
]


class KubernetesStudyMode:
    def __init__(self):
        self.client = GeminiClient()
        self.conversation_history: List[Dict[str, str]] = []
        self.session_active = False

    def generate_term_definition_pair(self, topic: str) -> Optional[Dict[str, str]]:
        """Generates a term and definition pair for the given topic."""
        system_prompt = self._build_term_recall_prompt(topic)
        user_prompt = f"Give me a term and definition about {topic}."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response_text = self.client.chat_completion(
                messages=messages, temperature=0.5
            )
            if response_text:
                # The prompt asks for JSON, so we parse it.
                return json.loads(response_text)
        except json.JSONDecodeError as e:
            logging.error(f"Failed to decode JSON from LLM response: {e}")
        except Exception:
            # The client logs the error, we just need to fail gracefully.
            pass

        return None

    def start_study_session(self, topic: str, user_level: str = "intermediate") -> Optional[str]:
        """Initialize a new study session using Gemini."""
        system_prompt = self._build_kubernetes_study_prompt(topic, user_level)
        user_prompt = f"I want to learn about {topic} in Kubernetes. Can you guide me through it?"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            assistant_response = self.client.chat_completion(
                messages=messages, temperature=0.7
            )
        except Exception:
            assistant_response = None

        if not assistant_response:
            self.session_active = False
            return None

        self.session_active = True
        self.conversation_history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": assistant_response},
        ]

        return assistant_response

    def continue_conversation(self, user_input: str) -> str:
        """Continue the study conversation using Gemini."""
        if not self.session_active:
            return "The study session has not been started. Please start a session first."

        self.conversation_history.append({"role": "user", "content": user_input})

        try:
            assistant_response = self.client.chat_completion(
                messages=self.conversation_history, temperature=0.7
            )
        except Exception:
            assistant_response = None

        if not assistant_response:
            return "I'm sorry, I seem to be having connection issues. Could you please repeat your question?"

        self.conversation_history.append({"role": "assistant", "content": assistant_response})

        return assistant_response

    def _build_kubernetes_study_prompt(self, topic: str, level: str) -> str:
        """Builds a structured, detailed system prompt optimized for Gemini models."""
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

    def _build_term_recall_prompt(self, topic: str) -> str:
        """Builds a system prompt for generating term/definition pairs."""
        return f"""
# **Persona**
You are a concise Kubernetes terminology expert. Your task is to generate a single term and its definition based on a given topic.

# **Topic**
The user wants a term/definition pair related to: **{topic}**.

# **Task**
1.  Identify a single, specific, and important term from the topic `{topic}`.
2.  Write a clear, one-sentence definition for that term.
3.  Format your response **exclusively** as a JSON object with two keys: "term" and "definition".

# **Example**
If the topic is "Core workloads", a valid response would be:
{{
  "term": "Pod",
  "definition": "The smallest and simplest unit in the Kubernetes object model that you create or deploy."
}}

# **Strict Rules**
- Your output MUST be a valid JSON object.
- Do not include any text, explanations, or formatting outside of the JSON structure.
- The definition should be concise and easy to understand for someone learning Kubernetes.
"""
