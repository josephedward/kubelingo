import getpass
import json
import os
import random
import sqlite3
import subprocess
import sys
import uuid
from dataclasses import asdict
from typing import Dict, List, Optional

import questionary
import yaml
from questionary import Separator

from kubelingo.database import add_question, get_db_connection, get_flagged_questions
from kubelingo.integrations.llm import LLMClient, get_llm_client
from kubelingo.modules.kubernetes.vim_yaml_editor import VimYamlEditor
from kubelingo.question import Question, QuestionSubject
from kubelingo.utils.config import (
    get_ai_provider,
    get_cluster_configs,
    get_gemini_api_key,
    get_openai_api_key,
    save_ai_provider,
    save_cluster_configs,
    save_gemini_api_key,
    save_openai_api_key,
)
from kubelingo.utils.path_utils import get_project_root
from kubelingo.utils.ui import Fore, Style
from kubelingo.utils.validation import commands_equivalent, is_yaml_subset

KUBERNETES_TOPICS = [member.value for member in QuestionSubject]


class KubernetesStudyMode:
    def __init__(self):
        self.ai_provider = get_ai_provider()
        self.client: LLMClient = get_llm_client()
        self.conversation_history: List[Dict[str, str]] = []
        self.session_active = False
        self.vim_editor = VimYamlEditor()
        self.db_conn = get_db_connection()
        self.questions_dir = get_project_root() / "questions" / "generated_yaml"
        os.makedirs(self.questions_dir, exist_ok=True)

    def main_menu(self):
        """Displays the main menu and handles user selection."""
        while True:
            try:
                choice = questionary.select(
                    "Kubernetes Main Menu",
                    choices=[
                        "Study Mode",
                        "Review Questions",
                        "Settings",
                        "Tools",
                        "Exit",
                    ],
                    use_indicator=True,
                ).ask()

                if choice is None or choice == "Exit":
                    print("Exiting application. Goodbye!")
                    break

                if choice == "Study Mode":
                    level = questionary.select(
                        "What is your current overall skill level?",
                        choices=["beginner", "intermediate", "advanced"],
                        default="intermediate",
                    ).ask()
                    if not level:
                        continue
                    self.start_study_session(user_level=level)
                elif choice == "Review Questions":
                    self.review_past_questions()
                elif choice == "Settings":
                    self.settings_menu()
                elif choice == "Tools":
                    self.run_tools_menu()
            except (KeyboardInterrupt, TypeError):
                print("\nExiting application. Goodbye!")
                break

    def _run_quiz(self, questions: List[Question]):
        """Runs a quiz with a list of questions."""
        if not questions:
            print(f"\n{Fore.YELLOW}No questions available for this topic.{Style.RESET_ALL}")
            return

        # Randomize question order for variety
        random.shuffle(questions)

        for question in questions:
            try:
                print(f"\n{question.prompt}")
                correct = self._ask_and_validate(question)

                if correct:
                    print(f"\n{Fore.GREEN}Correct!{Style.RESET_ALL}")
                else:
                    print(f"\n{Fore.RED}Not quite.{Style.RESET_ALL}")
                    if question.answers:
                        # Assuming the first answer is a good one to show
                        print(f"A correct answer is: {question.answers[0]}")

                if question.explanation:
                    print(f"Explanation: {question.explanation}")

                if not questionary.confirm("Next question?").ask():
                    break
            except (KeyboardInterrupt, TypeError):
                break
        print("\nQuiz ended. Returning to menu.")

    def _get_subjects_by_type(self, quiz_types: List[str]) -> List[str]:
        """Fetches unique subjects for given quiz types from the database."""
        placeholders = ",".join("?" for _ in quiz_types)
        query = f"SELECT DISTINCT subject FROM questions WHERE type IN ({placeholders}) AND subject IS NOT NULL ORDER BY subject"
        try:
            cursor = self.db_conn.cursor()
            cursor.execute(query, quiz_types)
            subjects = [row[0] for row in cursor.fetchall()]
            return subjects
        except Exception as e:
            print(f"{Fore.RED}Error fetching subjects from database: {e}{Style.RESET_ALL}")
            return []

    def _get_questions_by_subject_and_type(
        self, subject: str, quiz_types: List[str]
    ) -> List[Question]:
        """Fetches questions from the database for a given subject and quiz types."""
        placeholders = ",".join("?" for _ in quiz_types)
        query = f"SELECT * FROM questions WHERE subject = ? AND type IN ({placeholders})"
        try:
            self.db_conn.row_factory = sqlite3.Row
            cursor = self.db_conn.cursor()
            cursor.execute(query, [subject] + quiz_types)
            rows = cursor.fetchall()
            questions = []

            column_names = [d[0] for d in cursor.description]
            for row in rows:
                q_dict = dict(zip(column_names, row))
                # Deserialize JSON fields
                for key in [
                    "validation_steps",
                    "validator",
                    "pre_shell_cmds",
                    "initial_files",
                    "answers",
                ]:
                    if q_dict.get(key) and isinstance(q_dict[key], str):
                        try:
                            q_dict[key] = json.loads(q_dict[key])
                        except (json.JSONDecodeError, TypeError):
                            q_dict[key] = None
                questions.append(Question(**q_dict))
            return questions
        except Exception as e:
            print(
                f"{Fore.RED}Error fetching questions from database: {e}{Style.RESET_ALL}"
            )
            return []

    def start_study_session(self, user_level: str = "intermediate") -> None:
        """Guides the user to select a quiz and starts the session."""
        while True:
            try:
                quiz_style = questionary.select(
                    "What style of quiz would you like?",
                    choices=[
                        "Open-Ended Socratic Dialogue",
                        "Basic term/definition recall",
                        "Command-line Challenge",
                        "Manifest Authoring Exercise",
                        Separator(),
                        questionary.Choice("Back to Main Menu", value="back"),
                    ],
                    use_indicator=True,
                ).ask()
                if not quiz_style or quiz_style == "back":
                    break

                if quiz_style == "Open-Ended Socratic Dialogue":
                    topic = questionary.select(
                        "Which Kubernetes topic would you like to study?",
                        choices=KUBERNETES_TOPICS,
                        use_indicator=True,
                    ).ask()
                    if topic:
                        self._run_socratic_mode(topic, user_level)
                    continue

                quiz_type_map = {
                    "Basic term/definition recall": ["basic"],
                    "Command-line Challenge": ["command"],
                    "Manifest Authoring Exercise": ["yaml_author", "yaml_edit"],
                }
                quiz_types = quiz_type_map[quiz_style]

                subjects = self._get_subjects_by_type(quiz_types)
                if not subjects:
                    print(
                        f"{Fore.YELLOW}No subjects found for '{quiz_style}' quizzes.{Style.RESET_ALL}"
                    )
                    continue

                choices = subjects + [
                    Separator(),
                    questionary.Choice("Back", value="back"),
                ]
                selected_subject = questionary.select(
                    f"Choose a subject for '{quiz_style}':",
                    choices=choices,
                    use_indicator=True,
                ).ask()

                if not selected_subject or selected_subject == "back":
                    continue

                questions = self._get_questions_by_subject_and_type(
                    selected_subject, quiz_types
                )

                self._run_quiz(questions)

            except (KeyboardInterrupt, TypeError):
                print("\nExiting study mode.")
                break

    def review_past_questions(self):
        """Displays past questions for review."""
        try:
            flagged_questions = get_flagged_questions()
            if not flagged_questions:
                print(
                    f"{Fore.YELLOW}\nNo questions are currently flagged for review.{Style.RESET_ALL}"
                )
                return

            print(f"\n{Fore.CYAN}Questions flagged for review:{Style.RESET_ALL}")
            for q in flagged_questions:
                source_info = f"({q['source_file']})" if q.get("source_file") else ""
                print(f"  - [{q['id']}] {q['prompt']} {source_info}")

        except Exception as e:
            print(
                f"{Fore.RED}\nCould not retrieve flagged questions: {e}{Style.RESET_ALL}"
            )

    def settings_menu(self):
        """Displays the settings menu."""
        self._manage_config_interactive()

    def run_tools_menu(self):
        """Runs the kubelingo_tools.py script to show the maintenance menu."""
        print("\nLaunching Kubelingo Tools...")
        tools_script_path = get_project_root() / "scripts" / "kubelingo_tools.py"
        if not tools_script_path.exists():
            print(f"Error: Tools script not found at {tools_script_path}")
            return

        try:
            # Use sys.executable to ensure we're using the same Python interpreter
            subprocess.run([sys.executable, str(tools_script_path)], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error running tools script: {e}")
        except FileNotFoundError:
            print(f"Error: Could not find '{sys.executable}' to run the script.")

    def _manage_config_interactive(self):
        """Interactive prompt for managing configuration."""
        try:
            from kubelingo.utils.config import get_ai_provider

            current_provider = get_ai_provider()

            action = questionary.select(
                "What would you like to do?",
                choices=[
                    Separator("AI Provider Settings"),
                    {
                        "name": f"Select AI Provider (current: {current_provider.capitalize()})",
                        "value": "set_provider",
                    },
                    Separator("API Keys"),
                    {"name": f"View API key for {current_provider.capitalize()}", "value": "view_api_key"},
                    {"name": f"Set/Update API key for {current_provider.capitalize()}", "value": "set_api_key"},
                    Separator("Kubernetes Clusters"),
                    {"name": "List configured clusters", "value": "list_clusters"},
                    {"name": "Add a new cluster connection", "value": "add_cluster"},
                    {"name": "Remove a cluster connection", "value": "remove_cluster"},
                    Separator(),
                    {"name": "Cancel", "value": "cancel"},
                ],
                use_indicator=True,
            ).ask()

            if action is None or action == "cancel":
                return

            if action == "set_provider":
                self._select_ai_provider()
            elif action == "view_api_key":
                self._handle_config_command(["config", "view", "api_key"])
            elif action == "set_api_key":
                self._handle_config_command(["config", "set", "api_key"])
            elif action == "list_clusters":
                self._handle_config_command(["config", "list", "cluster"])
            elif action == "add_cluster":
                self._handle_config_command(["config", "add", "cluster"])
            elif action == "remove_cluster":
                self._handle_config_command(["config", "remove", "cluster"])

            print()

        except (KeyboardInterrupt, EOFError):
            print()
            return

    def _select_ai_provider(self):
        """Allows user to select the AI provider."""
        try:
            new_provider = questionary.select(
                "Select your preferred AI provider:",
                choices=["gemini", "openai"],
                default=self.ai_provider,
            ).ask()

            if new_provider and new_provider != self.ai_provider:
                if save_ai_provider(new_provider):
                    self.ai_provider = new_provider
                    self.client = get_llm_client()
                    self.question_generator.llm_client = self.client
                    print(
                        f"\n{Fore.GREEN}AI provider set to {self.ai_provider.capitalize()}. It will be used for future sessions.{Style.RESET_ALL}"
                    )
                else:
                    print(
                        f"\n{Fore.RED}Failed to save AI provider setting.{Style.RESET_ALL}"
                    )

        except (KeyboardInterrupt, EOFError):
            print(f"\n{Fore.YELLOW}AI provider selection cancelled.{Style.RESET_ALL}")

    def _handle_config_command(self, cmd):
        """Handles 'config' subcommands."""
        if len(cmd) < 3:
            print("Usage: kubelingo config <action> <target> [args...]")
            print("Example: kubelingo config set api_key")
            print("Example: kubelingo config list cluster")
            return

        action = cmd[1].lower()
        target = cmd[2].lower()

        if target == "provider":
            if action == "set":
                # This logic is handled by _select_ai_provider now.
                self._select_ai_provider()
            else:
                print(f"Unknown action '{action}' for provider. Use 'set'.")

        elif target == "api_key":
            from kubelingo.utils.config import (
                get_active_api_key,
                get_ai_provider,
                save_gemini_api_key,
                save_openai_api_key,
            )

            provider = get_ai_provider()
            key_name = f"{provider.capitalize()} API key"

            if action == "view":
                key = get_active_api_key()
                if key:
                    print(f"\n{key_name}: {key}")
                else:
                    print(f"\n{key_name} is not set.")
            elif action == "set":
                value = None
                if len(cmd) >= 4:
                    value = cmd[3]
                else:
                    try:
                        value = getpass.getpass(f"Enter {key_name}: ").strip()
                    except (EOFError, KeyboardInterrupt):
                        print(
                            f"\n{Fore.YELLOW}API key setting cancelled.{Style.RESET_ALL}"
                        )
                        return

                if value:
                    save_func = (
                        save_openai_api_key
                        if provider == "openai"
                        else save_gemini_api_key
                    )
                    if save_func(value):
                        print(f"\n{Fore.GREEN}{key_name} saved.{Style.RESET_ALL}")
                    else:
                        print(f"\n{Fore.RED}Failed to save {key_name}.{Style.RESET_ALL}")
                else:
                    print("\nNo API key provided. No changes made.")
            else:
                print(f"Unknown action '{action}' for api_key. Use 'view' or 'set'.")
        elif target == "cluster":
            configs = get_cluster_configs()
            if action == "list":
                if not configs:
                    print("No Kubernetes cluster connections configured.")
                    return
                print("Configured Kubernetes clusters:")
                for name, details in configs.items():
                    print(f"  - {name} (context: {details.get('context', 'N/A')})")

            elif action == "add":
                print("Adding a new Kubernetes cluster connection.")
                try:
                    name = questionary.text("Enter a name for this connection:").ask()
                    if not name:
                        print("Connection name cannot be empty. Aborting.")
                        return
                    if name in configs:
                        print(f"A connection named '{name}' already exists. Aborting.")
                        return

                    context = questionary.text("Enter the kubectl context to use:").ask()
                    if not context:
                        print("Context cannot be empty. Aborting.")
                        return

                    configs[name] = {"context": context}
                    if save_cluster_configs(configs):
                        print(f"Cluster connection '{name}' saved.")
                    else:
                        print("Failed to save cluster configuration.")
                except (KeyboardInterrupt, EOFError):
                    print(
                        f"\n{Fore.YELLOW}Cluster configuration cancelled.{Style.RESET_ALL}"
                    )

            elif action == "remove":
                if not configs:
                    print("No Kubernetes cluster connections configured to remove.")
                    return

                try:
                    choices = list(configs.keys())
                    name_to_remove = questionary.select(
                        "Which cluster connection do you want to remove?", choices=choices
                    ).ask()

                    if name_to_remove:
                        del configs[name_to_remove]
                        if save_cluster_configs(configs):
                            print(f"Cluster connection '{name_to_remove}' removed.")
                        else:
                            print("Failed to save cluster configuration.")
                except (KeyboardInterrupt, EOFError):
                    print(f"\n{Fore.YELLOW}Cluster removal cancelled.{Style.RESET_ALL}")

            else:
                print(f"Unknown action '{action}' for cluster. Use 'list', 'add', or 'remove'.")
        else:
            print(f"Unknown config target '{target}'. Supported: provider, api_key, cluster.")

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
        print(f"\nStarting a 'Basic term/definition' quiz on {topic}. Type 'exit' to quit.")
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
        category_map = {
            "basic": "Basic",
            "command": "Command",
            "manifest": "Manifest",
        }
        category = category_map.get(quiz_type)
        asked_items = set()

        while True:
            try:
                base_question = {
                    "subject": topic,
                    "type": quiz_type,
                    "category": category,
                    "user_level": user_level,
                }
                if quiz_type == "basic":
                    base_question['exclude_terms'] = list(asked_items)
                else:
                    base_question['exclude_prompts'] = list(asked_items)

                question_dict = self.question_generator.generate_question(base_question)

                if not question_dict:
                    if not questionary.confirm(
                        "Failed to generate a question. Try again?"
                    ).ask():
                        break
                    continue

                if 'id' not in question_dict:
                    question_dict['id'] = f"ai-gen-{uuid.uuid4()}"

                question_dict.setdefault('type', quiz_type)
                question_dict.setdefault('subject', topic)
                question_dict.setdefault('category', category)
                question_dict.setdefault('source', 'ai_generated')
                question = Question(**question_dict)

                if quiz_type == "basic":
                    asked_items.add(question.response)
                    # For compatibility with _ask_and_validate
                    if question.response and not question.answers:
                        question.answers = [question.response]
                else:
                    asked_items.add(question.prompt)
                    if question.response and not question.answers:
                        question.answers = [question.response]

                # Save the generated question to a file
                try:
                    question_path = self.questions_dir / f"{question.id}.yaml"
                    with question_path.open("w", encoding="utf-8") as f:
                        yaml.dump(asdict(question), f, sort_keys=False, indent=2)
                except Exception as e:
                    print(f"\nWarning: Could not save generated question: {e}")

                print(f"\n{question.prompt}")
                correct = self._ask_and_validate(question)

                if correct:
                    print("\nCorrect!")
                else:
                    # For basic quizzes, show the correct term
                    if quiz_type == "basic":
                        print(f"\nNot quite. The correct term is: {question.response}")
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
            user_answer = questionary.text("What is the term?").ask()
            if user_answer is None:
                return False
            # Simple case-insensitive check for basic terminology
            if not question.answers:
                return False
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
