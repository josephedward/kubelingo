import os
import uuid
from dataclasses import asdict
from typing import Dict, List, Optional

import questionary
import yaml

from kubelingo.database import add_question, get_db_connection  # Fixed import
from kubelingo.integrations.llm import GeminiClient
from kubelingo.modules.kubernetes.vim_yaml_editor import VimYamlEditor
from kubelingo.modules.question_generator import AIQuestionGenerator
from kubelingo.question import Question, QuestionSubject
from kubelingo.utils.path_utils import get_project_root
from kubelingo.utils.validation import commands_equivalent, is_yaml_subset

KUBERNETES_TOPICS = [member.value for member in QuestionSubject]


class KubernetesStudyMode:
    def __init__(self):
        self.client = GeminiClient()
        self.conversation_history: List[Dict[str, str]] = []
        self.session_active = False
        self.vim_editor = VimYamlEditor()
        self.question_generator = AIQuestionGenerator()
        self.db_conn = get_db_connection()
        self.questions_dir = get_project_root() / "questions" / "ai_generated"
        os.makedirs(self.questions_dir, exist_ok=True)

    def main_menu(self):
        """Displays the main menu and handles user selection."""
        while True:
            try:
                choice = questionary.select(
                    "Kubernetes Main Menu",
                    choices=[
                        "Start Study Session",
                        "Review Past Questions",
                        "Settings",
                        "Exit",
                    ],
                    use_indicator=True,
                ).ask()

                if choice is None or choice == "Exit":
                    print("Exiting application. Goodbye!")
                    break

                if choice == "Start Study Session":
                    level = questionary.select(
                        "What is your current overall skill level?",
                        choices=["beginner", "intermediate", "advanced"],
                        default="intermediate",
                    ).ask()
                    if not level:
                        continue
                    self.start_study_session(user_level=level)
                elif choice == "Review Past Questions":
                    self.review_past_questions()
                elif choice == "Settings":
                    self.settings_menu()
            except (KeyboardInterrupt, TypeError):
                print("\nExiting application. Goodbye!")
                break

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
                    break

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

    def review_past_questions(self):
        """Displays past questions for review."""
        print("\nReviewing past questions is not yet implemented.")
        # Placeholder for future implementation

    def settings_menu(self):
        """Displays the settings menu."""
        print("\nSettings menu is not yet implemented.")
        # Placeholder for future implementation

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
        print("\nStarting basic term/definition recall session...")
        print("Type 'exit' or 'quit' to end the session.")
        while True:
            try:
                pair = self.generate_term_definition_pair(
                    topic, user_level
                )
                if not pair:
                    print("Failed to generate a term/definition pair. Please try again.")
                    if not questionary.confirm("Try again?").ask():
                        break
                    continue

                term = pair.get("term")
                definition = pair.get("definition")

                print(f"\nDefinition: {definition}")
                user_answer = questionary.text("What is the term?").ask()
                if user_answer is None or user_answer.lower() in ["exit", "quit"]:
                    break

                if user_answer.strip().lower() == term.strip().lower():
                    print("\nCorrect!")
                else:
                    print(f"\nNot quite. The correct term is: {term}")

                if not questionary.confirm("Next question?").ask():
                    break
            except (KeyboardInterrupt, TypeError):
                break
        print("\nQuiz ended. Returning to menu.")

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
        category_map = {
            "basic": "Basic",
            "command": "Command",
            "manifest": "Manifest",
        }
        category = category_map.get(quiz_type)

        while True:
            try:
                questions = self.question_generator.generate_questions(
                    subject=topic,
                    num_questions=1,
                    category=category
                )

                if not questions:
                    if not questionary.confirm("Failed to generate a question. Try again?").ask():
                        break
                    continue

                question = questions[0]

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

    def generate_term_definition_pair(
        self,
        topic: str,
        user_level: str = "intermediate",
    ) -> Optional[Dict[str, str]]:
        """Generates a term and definition pair for the given topic."""
        try:
            questions = self.question_generator.generate_questions(
                subject=topic,
                num_questions=1,
                category="Basic",
            )
            if questions and questions[0] and questions[0].answers:
                question = questions[0]
                return {"term": question.answers[0], "definition": question.prompt}
        except Exception as e:
            print(f"Error generating question: {e}")
        return None

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
