import os
from typing import Dict, List

try:
    import openai
except ImportError:
    openai = None
# If this module-level openai is our local stub (openai.py), try loading the real package
import os, sys, importlib
if openai is not None and hasattr(openai, '__file__'):
    # Detect stub by filename
    if os.path.basename(openai.__file__) == 'openai.py':
        cwd = os.getcwd()
        backup_path = list(sys.path)
        # Remove current dir entries to avoid importing local stub
        sys.path = [p for p in sys.path if p not in ('', cwd)]
        try:
            real_openai = importlib.import_module('openai')
        except ImportError:
            real_openai = openai
        finally:
            sys.path = backup_path
        openai = real_openai


KUBERNETES_TOPICS = {
    "pods": [
        "multi-container pods", "init containers", "pod lifecycle",
        "pod networking", "resource limits", "pod security contexts"
    ],
    "services": [
        "ClusterIP vs NodePort vs LoadBalancer", "service discovery",
        "endpoints", "ingress controllers", "network policies"
    ],
    "deployments": [
        "rolling updates", "rollback strategies", "replica sets",
        "deployment strategies", "blue-green deployments"
    ],
    "storage": [
        "persistent volumes", "storage classes", "volume mounts",
        "stateful sets", "dynamic provisioning"
    ]
}


class KubernetesStudyMode:
    def __init__(self, api_key: str):
        if openai is None:
            raise ImportError("openai package not found. Please install it with 'pip install openai'")
        # Configure API key on the OpenAI module
        try:
            openai.api_key = api_key
        except Exception as e:
            raise ImportError(f"Failed to set OpenAI API key: {e}")
        # Use OpenAI module directly for chat completions
        self.openai = openai
        self.conversation_history = []

    def start_study_session(self, topic: str, user_level: str = "intermediate") -> str:
        """Initialize a new study session"""
        system_prompt = self._build_kubernetes_study_prompt(topic, user_level)

        initial_message = f"I want to learn about {topic} in Kubernetes. Can you guide me through it?"

        response = self.openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": initial_message}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        assistant_response = response.choices[0].message.content
        self.conversation_history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": initial_message},
            {"role": "assistant", "content": assistant_response}
        ]

        return assistant_response

    def continue_conversation(self, user_input: str) -> str:
        """Continue the study conversation"""
        self.conversation_history.append({"role": "user", "content": user_input})

        response = self.openai.ChatCompletion.create(
            model="gpt-4",
            messages=self.conversation_history,
            temperature=0.7,
            max_tokens=500
        )

        assistant_response = response.choices[0].message.content
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

    def generate_practice_question(self, topic: str, difficulty: str = "medium") -> str:
        """Generate practice questions for specific topics"""
        question_prompt = f"""Generate a {difficulty} difficulty practice question about {topic} in Kubernetes. 

The question should:
- Present a realistic scenario
- Require understanding of concepts, not just memorization  
- Be answerable through guided discovery
- Include enough context for troubleshooting

Format: Present the scenario, then ask "What questions would you ask first to troubleshoot this?" rather than asking for the direct solution."""

        response = self.openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert Kubernetes instructor creating quiz questions."},
                {"role": "user",   "content": question_prompt}
            ],
            temperature=0.8,
            max_tokens=300
        )

        return response.choices[0].message.content

    def generate_topic_questions(self, main_topic: str, count: int = 5) -> List[str]:
        """Generate multiple questions for a topic"""
        subtopics = KUBERNETES_TOPICS.get(main_topic, [main_topic])
        questions = []

        for i in range(count):
            subtopic = subtopics[i % len(subtopics)]
            question = self.generate_practice_question(f"{main_topic} - {subtopic}")
            questions.append(question)

        return questions
