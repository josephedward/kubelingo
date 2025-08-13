import getpass
import json
import logging
import os
import random
import re
import sqlite3
import subprocess
import sys
import uuid
from dataclasses import asdict
from typing import Dict, List, Optional

import questionary
import yaml
from questionary import Separator

from kubelingo.database import (
    get_db_connection,
    get_flagged_questions,
    get_question_counts_by_subject,
    index_yaml_files,
)
from kubelingo.integrations.llm import (
    GeminiClient,
    LLMClient,
    OpenAIClient,
    get_llm_client,
)
from kubelingo.modules.base.session import SessionManager
from kubelingo.modules.kubernetes.vim_yaml_editor import VimYamlEditor
from kubelingo.question import Question, QuestionCategory, QuestionSubject
from kubelingo.utils.config import (
    get_ai_provider,
    get_cluster_configs,
    save_cluster_configs,
)
from kubelingo.utils.path_utils import get_all_yaml_files, get_project_root
from kubelingo.modules.ai_evaluator import AIEvaluator
from kubelingo.modules.question_generator import AIQuestionGenerator
from kubelingo.utils.ui import Fore, Style
from kubelingo.utils.validation import commands_equivalent, is_yaml_subset

try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    import openai
except ImportError:
    openai = None


KUBERNETES_TOPICS = [member.value for member in QuestionSubject]


SOCRATIC_TUTOR_TOPICS = [
    "Linux Syntax(Commands from Vim, Kubectl, Docker ,Helm )",
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
]


class SocraticMode:
    def __init__(self):
        self.ai_provider = get_ai_provider()
        try:
            self.client: LLMClient = get_llm_client()
            self.ai_evaluator = AIEvaluator(llm_client=self.client)
            self.question_generator = AIQuestionGenerator(llm_client=self.client)
        except (ValueError, ImportError):
            self.client = None  # Handle case where no key is set yet
            self.ai_evaluator = None
            self.question_generator = None
        self.conversation_history: List[Dict[str, str]] = []
        self.session_active = False
        self.vim_editor = VimYamlEditor()
        self.db_conn = get_db_connection()
        self.session_manager = SessionManager(logging.getLogger(__name__))
        # Per user request, save generated questions to the top-level 'yaml' directory.
        self.questions_dir = get_project_root() / "yaml"
        os.makedirs(self.questions_dir, exist_ok=True)
        self._index_all_yaml_files()


    def run_drill_menu(self):
        """Shows a menu of exercise types, then subjects for drilling."""
        choices = [
            questionary.Choice(cat.value, value=cat) for cat in QuestionCategory
        ]
        choices.append(Separator())
        choices.append(questionary.Choice("Generate New Questions (AI)", value="generate_ai"))
        choices.append(questionary.Choice("Back", value="back"))

        choice = questionary.select(
            "--- Exercise Type ---",
            choices=choices,
            use_indicator=True
        ).ask()

        if choice and choice != "back":
            if choice == "generate_ai":
                self._run_ai_question_generation_menu()
            elif choice == QuestionCategory.OPEN_ENDED:
                self._run_socratic_mode_entry()
            else:
                self._run_subject_drill_menu(choice)

    def _run_subject_drill_menu(self, category: QuestionCategory):
        """Shows a sub-menu of subjects for a given category for study."""
        counts = get_question_counts_by_subject(category.value, self.db_conn)
        subject_choices = [
            questionary.Choice(f"{subject.value} ({count})", value=subject)
            for subject in QuestionSubject
            if (count := counts.get(subject.value, 0)) > 0
        ]
        subject_choices.sort(key=lambda c: c.title)

        if not subject_choices:
            # If no subjects are found, run a quiz with all questions for the category.
            # This handles cases where questions have a category but no subject.
            all_category_questions = self._get_questions_by_category_and_subject(
                category, None
            )
            if all_category_questions:
                print(
                    f"{Fore.YELLOW}No specific subjects found. Running quiz for all {len(all_category_questions)} questions in '{category.value}'.{Style.RESET_ALL}"
                )
                questionary.confirm("Press Enter to continue...").ask()
                self.run_exercises(all_category_questions)
            else:
                print(
                    f"\n{Fore.YELLOW}No questions found for '{category.value}'.{Style.RESET_ALL}"
                )
                questionary.confirm("Press Enter to continue...").ask()
            return

        subject_choices.append(Separator())
        subject_choices.append(questionary.Choice("Back", value="back"))

        subject_choice = questionary.select(
            f"Select a subject to study for '{category.value}':",
            choices=subject_choices,
        ).ask()

        if subject_choice and subject_choice != "back":
            self.run_drill_quiz(category, subject_choice)

    def _run_ai_question_generation_menu(self):
        """Runs a command-line interface to generate questions using AI."""
        if not self.question_generator:
            print(
                f"\n{Fore.YELLOW}AI Question Generator not available. Please check your AI provider configuration.{Style.RESET_ALL}"
            )
            questionary.confirm("Press Enter to continue...").ask()
            return

        category_choice = questionary.select(
            "Select a category for the new questions:",
            choices=[cat.value for cat in QuestionCategory if cat != QuestionCategory.OPEN_ENDED],
        ).ask()
        if not category_choice:
            return

        subject_choice = questionary.select(
            "Select a subject for the new questions:",
            choices=KUBERNETES_TOPICS,
        ).ask()
        if not subject_choice:
            return

        num_questions_str = questionary.text(
            "How many questions to generate?",
            default="3",
            validate=lambda text: text.isdigit() and int(text) > 0,
        ).ask()
        if not num_questions_str:
            return
        num_questions = int(num_questions_str)

        print(f"\nGenerating {num_questions} questions for '{subject_choice}' in '{category_choice}'...")

        try:
            context_questions = self._get_random_questions_for_context()
            # The generator returns Question objects, which we'll save as YAML
            generated_questions = self.question_generator.generate_questions(
                subject=subject_choice,
                num_questions=num_questions,
                category=category_choice,
                base_questions=context_questions,
            )

            if not generated_questions:
                print(f"{Fore.YELLOW}AI did not return any questions.{Style.RESET_ALL}")
                questionary.confirm("Press Enter to continue...").ask()
                return

            saved_count = 0
            for question in generated_questions:
                try:
                    # This logic is adapted from _run_quiz_loop to save and index consistently
                    category_dir_name = self._slugify_prompt(category_choice)
                    subject_dir_name = self._slugify_prompt(subject_choice)
                    target_dir = (
                        self.questions_dir / category_dir_name / subject_dir_name
                    )
                    os.makedirs(target_dir, exist_ok=True)

                    slug = self._slugify_prompt(question.prompt)
                    filename = f"{slug}.yaml"
                    question_path = target_dir / filename
                    if question_path.exists():
                        short_id = str(uuid.uuid4())[:8]
                        filename = f"{slug}-{short_id}.yaml"
                        question_path = target_dir / filename

                    with question_path.open("w", encoding="utf-8") as f:
                        yaml.dump(asdict(question), f, sort_keys=False, indent=2)

                    self._index_new_question(question_path)
                    saved_count += 1

                except Exception as e:
                    print(
                        f"\n{Fore.RED}Could not save and index question '{question.prompt[:50]}...': {e}{Style.RESET_ALL}"
                    )

            print(f"\n{Fore.GREEN}Successfully saved and indexed {saved_count} of {len(generated_questions)} new questions.{Style.RESET_ALL}")

        except Exception as e:
            print(f"\n{Fore.RED}An error occurred during AI question generation: {e}{Style.RESET_ALL}")

        questionary.confirm("Press Enter to continue...").ask()

    def run_exercises(self, questions: List[Question]):
        """
        Runs an interactive quiz session with a given list of questions.
        Includes a menu for each question for navigation and actions.
        """
        if not questions:
            print(f"\n{Fore.YELLOW}No questions available for this topic.{Style.RESET_ALL}")
            return

        random.shuffle(questions)
        current_index = 0

        while 0 <= current_index < len(questions):
            question = questions[current_index]
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"Question {current_index + 1}/{len(questions)}")
            print(f"{Style.BRIGHT}{question.prompt}{Style.RESET_ALL}\n")

            action = questionary.select(
                "Choose an action:",
                choices=[
                    "Answer Question",
                    "Visit Source",
                    "Next Question",
                    "Previous Question",
                    "Triage",
                    Separator(),
                    "Back",
                ],
                use_indicator=True
            ).ask()

            if action is None or action == "Back":
                break
            elif action == "Answer Question":
                correct = self._ask_and_validate(question)
                if correct:
                    print(f"\n{Fore.GREEN}Correct!{Style.RESET_ALL}")
                    self.session_manager.unmark_question_for_review(question.id)
                else:
                    print(f"\n{Fore.RED}Not quite.{Style.RESET_ALL}")
                    if question.answers:
                        print(f"A correct answer is: {question.answers[0]}")
                    self.session_manager.mark_question_for_review(question.id)
                
                if question.explanation:
                    print(f"\n{Fore.CYAN}Explanation: {question.explanation}{Style.RESET_ALL}")

                questionary.confirm("Press Enter to continue...").ask()
                current_index += 1
            elif action == "Visit Source":
                if question.source and question.source.startswith("http"):
                    print(f"Opening source: {question.source}")
                    subprocess.run(['open', question.source], check=False)
                else:
                    print("No valid source URL available for this question.")
                questionary.confirm("Press Enter to continue...").ask()
            elif action == "Next Question":
                current_index += 1
            elif action == "Previous Question":
                current_index -= 1
            elif action == "Triage":
                self.session_manager.triage_question(question.id)
                print(f"{Fore.YELLOW}Question '{question.id}' has been marked for triage.{Style.RESET_ALL}")
                questionary.confirm("Press Enter to continue...").ask()

        print("\nQuiz ended. Returning to menu.")

    def _run_socratic_mode_entry(self):
        """Gets user input before starting socratic mode."""
        if not self.client:
            print(
                f"\n{Fore.YELLOW}AI client not configured. Please set up your AI provider in 'Settings > AI'.{Style.RESET_ALL}"
            )
            questionary.confirm("Press Enter to continue...").ask()
            return

        topic = questionary.select(
            "Which Kubernetes topic would you like to study?",
            choices=SOCRATIC_TUTOR_TOPICS,
            use_indicator=True,
        ).ask()

        if topic:
            self._run_socratic_mode(topic)

    def run_drill_quiz(self, category: QuestionCategory, subject: QuestionSubject):
        """Runs a quiz with existing questions for a specific category and subject."""
        questions = self._get_questions_by_category_and_subject(
            category, subject.value
        )
        if questions:
            self.run_exercises(questions)
        else:
            print(
                f"\n{Fore.YELLOW}No questions found for '{subject.value}' in '{category.value}'.{Style.RESET_ALL}"
            )
            questionary.confirm("Press Enter to continue...").ask()

    def _get_questions_by_category_and_subject(
        self, category: QuestionCategory, subject: Optional[str]
    ) -> List[Question]:
        """
        Finds question files from the database and loads them from YAML.
        If subject is None, fetches all questions for the category.
        """
        params = [category.value]
        if subject:
            query = "SELECT id, source_file FROM questions WHERE category_id = ? AND subject_id = ?"
            params.append(subject)
        else:
            query = "SELECT id, source_file FROM questions WHERE category_id = ?"

        try:
            self.db_conn.row_factory = sqlite3.Row
            cursor = self.db_conn.cursor()
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            questions = []

            for row in rows:
                qid = row["id"]
                source_file = row["source_file"]
                if source_file:
                    question = self._load_question_from_yaml(source_file)
                    if question:
                        # The ID from the DB is the canonical ID.
                        question.id = qid
                        questions.append(question)
            return questions
        except Exception as e:
            print(
                f"{Fore.RED}Error fetching questions from database: {e}{Style.RESET_ALL}"
            )
            return []

    def _get_question_counts_by_subject(
        self, category: QuestionCategory
    ) -> Dict[str, int]:
        """Fetches question counts for all subjects within a given category."""
        query = """
            SELECT subject_id, COUNT(*)
            FROM questions
            WHERE category_id = ?
            GROUP BY subject_id
        """
        counts = {}
        try:
            cursor = self.db_conn.cursor()
            cursor.execute(query, (category.value,))
            rows = cursor.fetchall()
            for subject_val, count in rows:
                counts[subject_val] = count
        except Exception as e:
            print(f"{Fore.RED}Error fetching question counts: {e}{Style.RESET_ALL}")
        return counts

    def _index_all_yaml_files(self):
        """Finds and indexes all YAML question files into the database."""
        try:
            print("Checking for new or updated questions...")
            yaml_files = get_all_yaml_files()
            if yaml_files:
                index_yaml_files(yaml_files, self.db_conn, verbose=True)
        except Exception as e:
            print(f"{Fore.RED}Error during YAML file indexing: {e}{Style.RESET_ALL}")

    def _slugify_prompt(self, prompt: str) -> str:
        """Creates a filesystem-friendly slug from a question prompt."""
        s = prompt.lower().strip()
        s = re.sub(r"[\s\W-]+", "-", s)  # Replace whitespace/non-word chars with a hyphen
        return s[:75].strip("-")

    def _index_new_question(self, question_path):
        """Indexes a newly created YAML question file into the database."""
        try:
            # Use verbose=False to prevent printing success message for every file
            index_yaml_files([question_path], self.db_conn, verbose=False)
        except Exception as e:
            print(
                f"{Fore.RED}Failed to index new question {question_path.name}: {e}{Style.RESET_ALL}"
            )

    def _load_question_from_yaml(self, file_path: str) -> Optional[Question]:
        """Loads a single Question object from a YAML file."""
        try:
            if not os.path.isabs(file_path):
                file_path = os.path.join(str(get_project_root()), file_path)

            if not os.path.exists(file_path):
                print(f"{Fore.YELLOW}Warning: Question file not found: {file_path}{Style.RESET_ALL}")
                return None

            with open(file_path, "r", encoding="utf-8") as f:
                # Use safe_load_all to handle files that may contain lists or multiple documents.
                # We are interested in the first valid question data.
                documents = list(yaml.safe_load_all(f))

            if not documents or not documents[0]:
                return None  # File is empty or contains only null documents

            q_data = documents[0]
            q_dict = None

            if isinstance(q_data, list):
                if q_data:
                    q_dict = q_data[0]  # Take first item if it's a list of questions
            elif isinstance(q_data, dict):
                q_dict = q_data

            if not q_dict or not isinstance(q_dict, dict):
                # This will handle cases where the YAML is just a string (e.g., "COMMAND")
                raise TypeError("YAML content is not a dictionary.")

            return Question(**q_dict)
        except (yaml.YAMLError, TypeError) as e:
            print(
                f"{Fore.YELLOW}Warning: Could not load or parse {os.path.basename(file_path)}: {e}{Style.RESET_ALL}"
            )
            return None

    def review_past_questions(self):
        """Runs a quiz with questions that have been flagged for review."""
        try:
            flagged_question_dicts = get_flagged_questions()
            if not flagged_question_dicts:
                print(
                    f"{Fore.YELLOW}\nNo questions are currently flagged for review.{Style.RESET_ALL}"
                )
                return

            questions = []
            for q_meta in flagged_question_dicts:
                source_file = q_meta.get("source_file")
                qid = q_meta.get("id")
                if source_file and qid:
                    question = self._load_question_from_yaml(source_file)
                    if question:
                        question.id = qid
                        questions.append(question)

            if not questions:
                print(f"{Fore.YELLOW}\nCould not load any flagged questions.{Style.RESET_ALL}")
                return

            print(f"\nStarting review session with {len(questions)} flagged question(s).")
            self.run_exercises(questions)

        except Exception as e:
            print(
                f"{Fore.RED}\nCould not retrieve or run flagged questions: {e}{Style.RESET_ALL}"
            )


    def _cluster_config_menu(self):
        """Interactive prompt for managing cluster configurations."""
        self._handle_config_command("cluster")

    def run_tools_menu(self):
        """Runs the kubelingo_tools.py script to show the maintenance menu."""
        print("\nLaunching Kubelingo Tools...")
        tools_script_path = get_project_root() / "scripts" / "kubelingo_tools.py"
        if not tools_script_path.exists():
            print(f"Error: Tools script not found at {tools_script_path}")
            return

        try:
            # Use sys.executable to ensure we're using the same Python interpreter
            subprocess.run([sys.executable, str(tools_script_path)], check=False)
        except subprocess.CalledProcessError as e:
            print(f"Error running tools script: {e}")
        except FileNotFoundError:
            print(f"Error: Could not find '{sys.executable}' to run the script.")

    def _view_triaged_questions(self):
        """Lists all questions currently marked for triage."""
        query = "SELECT id, prompt, source_file FROM questions WHERE triage = 1"
        try:
            cursor = self.db_conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            if not rows:
                print(f"{Fore.YELLOW}No questions are currently marked for triage.{Style.RESET_ALL}")
                return
            print("The following questions are marked for triage:")
            for qid, prompt, source_file in rows:
                print(f" - [{qid}] {prompt} (from: {source_file})")
        except Exception as e:
            print(f"{Fore.RED}Error fetching triaged questions: {e}{Style.RESET_ALL}")

    def _get_random_questions_for_context(self, limit: int = 5) -> List[Question]:
        """
        Fetches metadata for random questions from DB and loads them from YAML for context.
        """
        query = "SELECT id, source_file FROM questions ORDER BY RANDOM() LIMIT ?"
        try:
            self.db_conn.row_factory = sqlite3.Row
            cursor = self.db_conn.cursor()
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            questions = []

            for row in rows:
                qid = row["id"]
                source_file = row["source_file"]
                if source_file:
                    question = self._load_question_from_yaml(source_file)
                    if question:
                        question.id = qid
                        questions.append(question)
            return questions
        except Exception:
            # Silently fail, context is optional.
            return []

    def _handle_config_command(self, target: str):
        """Handles interactive configuration for a specific target (e.g., 'cluster')."""
        configs = get_cluster_configs()
        if target == "cluster":
            action = questionary.select(
                "Cluster Configuration:",
                choices=["List configured clusters", "Add a new cluster", "Remove a cluster", "Back"]
            ).ask()

            if action is None or action == "Back":
                return

            if action == "List configured clusters":
                if not configs:
                    print("No Kubernetes cluster connections configured.")
                    return
                print("Configured Kubernetes clusters:")
                for name, details in configs.items():
                    print(f"  - {name} (context: {details.get('context', 'N/A')})")

            elif action == "Add a new cluster":
                print("Adding a new Kubernetes cluster connection.")
                try:
                    name = questionary.text("Enter a name for this connection:").ask()
                    if not name: return
                    if name in configs:
                        print(f"A connection named '{name}' already exists. Aborting.")
                        return
                    context = questionary.text("Enter the kubectl context to use:").ask()
                    if not context: return

                    configs[name] = {"context": context}
                    if save_cluster_configs(configs): print(f"Cluster connection '{name}' saved.")
                    else: print("Failed to save cluster configuration.")
                except (KeyboardInterrupt, EOFError):
                    print(f"\n{Fore.YELLOW}Cluster configuration cancelled.{Style.RESET_ALL}")

            elif action == "Remove a cluster":
                if not configs:
                    print("No clusters to remove.")
                    return
                try:
                    name_to_remove = questionary.select("Which cluster to remove?", choices=list(configs.keys())).ask()
                    if name_to_remove:
                        del configs[name_to_remove]
                        if save_cluster_configs(configs): print(f"Cluster '{name_to_remove}' removed.")
                        else: print("Failed to save configuration.")
                except (KeyboardInterrupt, EOFError):
                    print(f"\n{Fore.YELLOW}Cluster removal cancelled.{Style.RESET_ALL}")

    def _run_socratic_mode(self, topic: str):
        """Runs the conversational Socratic tutoring mode."""
        initial_response = self._start_socratic_session(topic)
        if not initial_response:
            print(
                f"{Fore.RED}\nSorry, I couldn't start the session. Please check your AI configuration and network connection.{Style.RESET_ALL}"
            )
            questionary.confirm("Press Enter to continue...").ask()
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

    def _run_basic_quiz(self, topic: str):
        """Runs a quiz focused on basic terminology."""
        print(f"\nStarting a 'Basic term/definition' quiz on {topic}. Type 'exit' to quit.")
        self._run_quiz_loop("basic", topic, QuestionCategory.BASIC_TERMINOLOGY)

    def _run_command_quiz(self, topic: str):
        """Runs a quiz focused on kubectl commands."""
        print(f"\nStarting a 'Command-line Challenge' on {topic}. Type 'exit' to quit.")
        self._run_quiz_loop("command", topic, QuestionCategory.COMMAND_SYNTAX)

    def _run_manifest_quiz(self, topic: str):
        """Runs a quiz focused on authoring Kubernetes manifests."""
        print(f"\nStarting a 'Manifest Authoring' exercise on {topic}. Type 'exit' to quit.")
        self._run_quiz_loop("manifest", topic, QuestionCategory.YAML_MANIFEST)

    def _run_quiz_loop(
        self, quiz_type: str, topic: str, category_enum: QuestionCategory
    ):
        """Generic loop for generating and asking questions."""
        if not self.client:
            print(
                f"\n{Fore.YELLOW}AI client not configured. Please set up your AI provider in 'Settings > AI'.{Style.RESET_ALL}"
            )
            questionary.confirm("Press Enter to continue...").ask()
            return

        category = category_enum.value
        asked_items = set()

        while True:
            try:
                context_questions = self._get_random_questions_for_context()
                base_question = {
                    "subject": topic,
                    "type": quiz_type,
                    "schema_category": category,
                    "base_questions": [asdict(q) for q in context_questions],
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
                question_dict.setdefault('schema_category', category)
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

                # Save the generated question to a file and index it.
                try:
                    # Organize generated questions into subdirectories based on category and subject.
                    # Structure: /yaml/{category}/{subject}/{slug}.yaml
                    category_dir_name = quiz_type  # 'basic', 'command', 'manifest'
                    subject_dir_name = self._slugify_prompt(topic)

                    target_dir = (
                        self.questions_dir / category_dir_name / subject_dir_name
                    )
                    os.makedirs(target_dir, exist_ok=True)

                    slug = self._slugify_prompt(question.prompt)
                    filename = f"{slug}.yaml"
                    question_path = target_dir / filename
                    # Avoid overwriting by adding a short UUID if a file with the same slug exists.
                    if question_path.exists():
                        short_id = str(uuid.uuid4())[:8]
                        filename = f"{slug}-{short_id}.yaml"
                        question_path = target_dir / filename

                    with question_path.open("w", encoding="utf-8") as f:
                        yaml.dump(asdict(question), f, sort_keys=False, indent=2)

                    # Index the new question into the database so it's immediately available.
                    self._index_new_question(question_path)

                except Exception as e:
                    print(f"\nWarning: Could not save and index generated question: {e}")

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

            if not self.ai_evaluator:
                print(f"{Fore.YELLOW}AI evaluator not available. Falling back to exact match.{Style.RESET_ALL}")
                # Fallback to simple check if AI is not configured
                for ans in question.answers:
                    if commands_equivalent(user_answer, ans):
                        return True
                return False

            # Use AI for more flexible evaluation
            q_dict = asdict(question)
            eval_result = self.ai_evaluator.evaluate_command(q_dict, user_answer)

            if eval_result:
                print(f"\n{Fore.CYAN}Feedback: {eval_result.get('reasoning', 'No reasoning provided.')}{Style.RESET_ALL}")
                return eval_result.get('correct', False)
            else:
                print(f"{Fore.RED}AI evaluation failed. Please check your connection or API key.{Style.RESET_ALL}")
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

        if question.type == "socratic":
            # For Socratic questions, just prompt for input and treat as 'correct'
            # to show explanation. There's no single right answer.
            questionary.text("Your thoughts? (Press Enter to continue)").ask()
            return True

        return False

    def _start_socratic_session(
        self, topic: str
    ) -> Optional[str]:
        """Initialize a new study session using Gemini."""
        system_prompt = self._build_kubernetes_study_prompt(topic)
        user_prompt = (
            f"I want to learn about {topic} in Kubernetes. Can you guide me through it?"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            assistant_response_obj = self.client.chat_completion(
                messages=messages, temperature=0.7
            )
            assistant_response = assistant_response_obj.text if assistant_response_obj else None
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
            assistant_response_obj = self.client.chat_completion(
                messages=self.conversation_history, temperature=0.7
            )
            assistant_response = assistant_response_obj.text if assistant_response_obj else None
        except Exception:
            assistant_response = None

        if not assistant_response:
            return "I'm sorry, I seem to be having connection issues. Could you please repeat your question?"

        self.conversation_history.append(
            {"role": "assistant", "content": assistant_response}
        )

        return assistant_response

    def _build_kubernetes_study_prompt(self, topic: str) -> str:
        """Builds a structured, detailed system prompt optimized for Gemini models."""
        return f"""
# **Persona**
You are KubeTutor, an expert on Kubernetes and a friendly, patient Socratic guide. Your goal is to help users achieve a deep, practical understanding of Kubernetes concepts.

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
