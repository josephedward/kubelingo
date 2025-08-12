import uuid
from dataclasses import asdict
from typing import Dict, List, Optional

import questionary
import yaml
from kubelingo.database import add_question, get_db_connection
from kubelingo.integrations.llm import GeminiClient
from kubelingo.modules.kubernetes.vim_yaml_editor import VimYamlEditor
from kubelingo.question import Question, QuestionSubject
from kubelingo.utils.path_utils import get_project_root
from kubelingo.utils.validation import commands_equivalent, is_yaml_subset

# Filter out general topics that are covered by more specific ones
_all_topics = [member.value for member in QuestionSubject]
_topics_to_exclude = {
    "Vim",
    "Helm",
    "Kubectl",
    "Kubernetes Resources",
}
KUBERNETES_TOPICS = [
    topic for topic in _all_topics if topic not in _topics_to_exclude
]


class KubernetesStudyMode:
    def __init__(self):
        self.client = GeminiClient()
        self.conversation_history: List[Dict[str, str]] = []
        self.session_active = False
        self.vim_editor = VimYamlEditor()
        self.db_conn = get_db_connection()
        self.questions_dir = get_project_root() / "questions" / "generated_yaml"
        self.questions_dir.mkdir(parents=True, exist_ok=True)

    def generate_term_definition_pair(self, topic: str, exclude_terms: List[str] = None) -> Optional[Dict[str, str]]:
        """Generates a term-definition pair using the LLM."""
        system_prompt = self._build_term_definition_prompt(topic, exclude_terms or [])
        user_prompt = "Please generate one term-definition pair based on the system prompt instructions."

        try:
            response = self.client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                json_mode=True,
            )
            if not response:
                return None

            # The response is expected to be a JSON string with "term" and "definition"
            pair = yaml.safe_load(response)
            if isinstance(pair, dict) and "term" in pair and "definition" in pair:
                return pair
            return None
        except Exception as e:
            print(f"Error generating or parsing term-definition pair: {e}")
            return None

    def _build_term_definition_prompt(self, topic: str, exclude_terms: List[str]) -> str:
        """Builds a system prompt for the LLM to generate a term-definition pair as JSON."""
        excluded_list = "\n".join(f"- {term}" for term in exclude_terms)
        return f"""
# **Role: Kubernetes Terminology Generator**
You are an expert on Kubernetes. Your task is to generate a single, unique term-definition pair in JSON format. Your output MUST BE A VALID JSON OBJECT.

# **Request Details**
- **Topic:** {topic}
- **Task:** Provide one term and its corresponding definition.

# **Exclusion List**
Do not generate a term from the following list:
{excluded_list if excluded_list else "- (none)"}

# **Instructions**
- The `term` should be a single, specific Kubernetes concept.
- The `definition` should be a clear and concise explanation of the term.
- The output MUST be a single, valid JSON object with two keys: "term" and "definition". Do not include any other text or formatting.

# **JSON Schema**
```json
{{
  "term": "(string, required) - The Kubernetes term.",
  "definition": "(string, required) - The definition of the term."
}}
```

# **Example**
```json
{{
  "term": "ReplicaSet",
  "definition": "Ensures that a specified number of pod replicas are running at any given time."
}}
```
"""

    def start_study_session(self, user_level: str = "intermediate") -> None:
        """Guides the user to select a topic and quiz style, then starts the session."""
        while True:
            try:
                topic = questionary.select(
                    "Which Kubernetes topic would you like to study?",
                    choices=KUBERNETES_TOPICS,
                    use_indicator=True,
                ).ask()
                if not topic:
                    break

                quiz_style = questionary.select(
                    "What style of quiz would you like?",
                    choices=[
                        "Open-Ended Socratic Dialogue",
                        "Basic term/definition recall",
                        "Command-line Challenge",
                        "Manifest Authoring Exercise",
                    ],
                    use_indicator=True,
                ).ask()
                if not quiz_style:
                    continue

                if quiz_style == "Open-Ended Socratic Dialogue":
                    self._run_socratic_mode(topic, user_level)
                elif quiz_style == "Basic term/definition recall":
                    self._run_basic_quiz(topic, user_level)
                elif quiz_style == "Command-line Challenge":
                    self._run_command_quiz(topic, user_level)
                elif quiz_style == "Manifest Authoring Exercise":
                    self._run_manifest_quiz(topic, user_level)

            except (KeyboardInterrupt, TypeError):
                print("\nExiting study mode.")
                break

    def _run_socratic_mode(self, topic: str, user_level: str):
        """Runs the conversational Socratic tutoring mode."""
        initial_response = self._start_socratic_session(topic, user_level)
        if not initial_response:
            print("Sorry, I couldn't start the session. Please try again.")
            return

        print(f"\nKubeTutor: {initial_response}")

        try:
            while True:
                user_input = questionary.text("Your answer (type 'exit' to quit):").ask()
                if user_input is None or user_input.lower() in ["exit", "quit"]:
                    break
                response = self._continue_socratic_conversation(user_input)
                print(f"\nKubeTutor: {response}")
        except (KeyboardInterrupt, TypeError):
            pass
        finally:
            print("\nSocratic session ended. Returning to menu.")

    def _run_basic_quiz(self, topic: str, user_level: str):
        """Runs a quiz focused on basic terminology."""
        print(f"\nStarting a 'Basic term/definition recall' session on {topic}. Type 'exit' or 'quit' to end the session.")
        self._run_quiz_loop("basic", topic, user_level)

    def _run_command_quiz(self, topic: str, user_level: str):
        """Runs a quiz focused on kubectl commands."""
        print(f"\nStarting a 'Command-line Challenge' on {topic}. Type 'exit' to quit.")
        self._run_quiz_loop("command", topic, user_level)

    def _run_manifest_quiz(self, topic: str, user_level: str):
        """Runs a quiz focused on authoring Kubernetes manifests."""
        print(f"\nStarting a 'Manifest Authoring' exercise on {topic}. Type 'exit' to quit.")
        self._run_quiz_loop("manifest", topic, user_level)

    def _run_quiz_loop(self, quiz_type: str, topic: str, user_level: str):
        """Generic loop for generating and asking questions."""
        while True:
            try:
                question = self._generate_question(topic, quiz_type, user_level)
                if not question:
                    if not questionary.confirm("Failed to generate a question. Try again?").ask():
                        break
                    continue

                print(f"\n{question.prompt}")
                correct = self._ask_and_validate(question)

                if correct:
                    print("\nCorrect!")
                else:
                    print("\nNot quite.")

                if question.explanation:
                    print(f"Explanation: {question.explanation}")

                if not questionary.confirm("Next question?").ask():
                    break
            except (KeyboardInterrupt, TypeError):
                break
        print("\nQuiz ended. Returning to menu.")

    def _ask_and_validate(self, question: Question) -> bool:
        """Asks a question and validates the answer based on its type."""
        if question.type == "basic":
            user_answer = questionary.text("Your answer:").ask()
            if user_answer is None:
                return False
            # Simple case-insensitive check for basic terminology
            return user_answer.lower().strip() == question.answers[0].lower().strip()

        if question.type == "command":
            user_answer = questionary.text("Your command:").ask()
            if user_answer is None:
                return False
            # Allow multiple correct answers, check for functional equivalence
            for ans in question.answers:
                if commands_equivalent(user_answer, ans):
                    return True
            return False

        if question.type in ("yaml_author", "yaml_edit"):
            initial_content = question.initial_files.get("exercise.yaml", "")
            user_yaml = self.vim_editor.edit_yaml_with_vim(
                initial_content, prompt=question.prompt
            )
            if user_yaml is None:
                return False
            # Check if the user's YAML is a subset of the required solution
            return is_yaml_subset(question.correct_yaml, user_yaml)

        return False

    def _generate_question(
        self, topic: str, quiz_type: str, user_level: str
    ) -> Optional[Question]:
        """Generates a question using the LLM and saves it."""
        system_prompt = self._build_question_generation_prompt(
            topic, quiz_type, user_level
        )
        user_prompt = (
            "Please generate one question based on the system prompt instructions."
        )

        try:
            response = self.client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.8,
                json_mode=True,
            )
            if not response:
                return None

            # The response is expected to be a YAML string (parsable as JSON)
            question_data = yaml.safe_load(response)
            question_data["id"] = str(uuid.uuid4())
            question_data["source_file"] = str(
                self.questions_dir / f"{question_data['id']}.yaml"
            )

            question = Question(**question_data)
            self._save_question(question)
            return question
        except Exception as e:
            print(f"Error generating or parsing question: {e}")
            return None

    def _save_question(self, question: Question):
        """Saves a question to a YAML file and the database."""
        # Save to YAML file
        with open(question.source_file, "w") as f:
            yaml.dump(asdict(question), f, sort_keys=False)

        # Save to database
        try:
            add_question(conn=self.db_conn, **asdict(question))
        except Exception as e:
            print(f"Warning: Failed to save question {question.id} to database: {e}")

    def _build_question_generation_prompt(
        self, topic: str, quiz_type: str, level: str
    ) -> str:
        """Builds a system prompt for the LLM to generate a question as YAML."""

        type_map = {
            "basic": (
                "basic",
                "Create a 'basic terminology' question. The user should provide a single term as the answer. The `prompt` is the definition, and `answers` is a list with one item: the term.",
            ),
            "command": (
                "command",
                "Create a `kubectl` command-line question. The `answers` list can contain multiple functionally equivalent correct commands.",
            ),
            "manifest": (
                "yaml_author",
                "Create a YAML authoring question. The user must create a manifest from scratch. Provide the `correct_yaml`.",
            ),
        }
        q_type, instructions = type_map[quiz_type]

        return f"""
# **Role: Kubernetes Quiz Generator**
You are an expert curriculum developer for Kubernetes. Your task is to generate a single, high-quality quiz question in YAML format based on the user's request. Your output MUST BE A VALID YAML DOCUMENT.

# **Request Details**
- **Topic:** {topic}
- **Skill Level:** {level}
- **Quiz Type:** {quiz_type.title()}

# **Instructions**
- **{instructions}**
- The `prompt` must be a clear question or instruction for the user.
- `subject_matter` must exactly match the topic: "{topic}"
- `explanation` should briefly clarify the concept or command after the user answers.
- The output MUST be a single, valid YAML document that maps to the `Question` schema. Do not include any other text or formatting.

# **YAML Schema**
```yaml
# id: (string, will be auto-generated)
prompt: (string, required) - The question text presented to the user.
type: (string, required) - Must be '{q_type}'.
subject_matter: (string, required) - Must be '{topic}'.
answers: (list of strings, required for command/basic) - Correct answer(s).
correct_yaml: (string, required for manifest) - The full, correct YAML manifest.
initial_files: (dict, optional for manifest) - Files to start with, e.g., {{'exercise.yaml': '...'}}.
explanation: (string, optional) - Explanation of the answer.
difficulty: (string, optional) - e.g., 'easy', 'medium', 'hard'.
```

# **Example (for a 'command' question about Pods)**
```yaml
prompt: "Create a kubectl command to run a Pod named 'nginx' with the 'nginx:1.14.2' image."
type: "command"
subject_matter: "Core workloads (Pods, ReplicaSets, Deployments; rollouts/rollbacks)"
answers:
  - "kubectl run nginx --image=nginx:1.14.2"
explanation: "The `kubectl run` command is a quick way to create a single Pod imperatively."
difficulty: "easy"
```
"""

    def _start_socratic_session(
        self, topic: str, user_level: str = "intermediate"
    ) -> Optional[str]:
        """Initialize a new study session using Gemini."""
        system_prompt = self._build_kubernetes_study_prompt(topic, user_level)
        user_prompt = (
            f"I want to learn about {topic} in Kubernetes. Can you guide me through it?"
        )

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

    def _continue_socratic_conversation(self, user_input: str) -> str:
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

        self.conversation_history.append(
            {"role": "assistant", "content": assistant_response}
        )

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
