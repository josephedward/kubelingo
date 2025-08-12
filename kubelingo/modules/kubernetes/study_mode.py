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
    def __init__(self):
        self.client = get_llm_client()
        self.conversation_history: List[Dict[str, str]] = []

    def start_study_session(self, topic: str, user_level: str = "intermediate") -> str:
        """Initialize a new study session"""
        system_prompt = self._build_kubernetes_study_prompt(topic, user_level)
        user_prompt = f"I want to learn about {topic} in Kubernetes. Can you guide me through it?"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        assistant_response = self.client.chat_completion(
            messages=messages, temperature=0.7
        )

        if not assistant_response:
            assistant_response = "I'm sorry, I'm having trouble connecting to my knowledge base. Please try again later."

        self.conversation_history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": assistant_response},
        ]

        return assistant_response

    def continue_conversation(self, user_input: str) -> str:
        """Continue the study conversation"""
        self.conversation_history.append({"role": "user", "content": user_input})

        assistant_response = self.client.chat_completion(
            messages=self.conversation_history, temperature=0.7
        )

        if not assistant_response:
            assistant_response = "I'm sorry, I seem to be having connection issues. Could you please repeat your question?"

        self.conversation_history.append({"role": "assistant", "content": assistant_response})

        return assistant_response

    def _build_kubernetes_study_prompt(self, topic: str, level: str) -> str:
        """Build topic-specific system prompt"""
        base_prompt = """You are a Kubernetes expert tutor specializing in {topic}.

STRICT RULES

Be an approachable-yet-dynamic teacher who guides users through Kubernetes concepts using the Socratic method.

Get to know the user's current level with {topic} before diving deep. If they don't specify, assume {level} level knowledge.

Build on existing knowledge. Connect new concepts to fundamental Kubernetes building blocks they already understand.

Guide users, don't give direct answers. Use probing questions like:
- "What do you think would happen if...?"
- "How might this relate to what you know about pods/services/deployments?"
- "Can you think of a scenario where this would be useful?"

For {topic}, focus on:
- Practical applications and real-world scenarios  
- Connection to kubectl commands and YAML manifests
- Troubleshooting common issues
- Best practices and security considerations

Never provide complete YAML files or kubectl commands. Instead, guide them to construct these step by step.

Check understanding frequently with questions like "Can you explain back to me how X works?" or "What would you expect to see if you ran kubectl get Y?"

TONE: Be warm, patient, conversational. Keep responses under 150 words. Always end with a guiding question or next step.

Remember: Your goal is deep understanding, not quick answers."""

        return base_prompt.format(topic=topic, level=level)
