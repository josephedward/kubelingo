#!/usr/bin/env python3
"""
CLI entry point for Kubelingo application.
Displays the main menu as per requirements.md specifications.
"""
import sys
import os
import subprocess
import json
import glob
import yaml
import tempfile
import builtins
from kubelingo.importer import import_from_file
from kubelingo.question_generator import QuestionGenerator
from kubelingo.k8s_manifest_generator import ManifestGenerator
from rich.console import Console
from rich.text import Text
from rich.align import Align
import requests
import shutil
import kubelingo.llm_utils as _llm_utils
from kubelingo.llm_utils import ai_chat
# Keep track of the original LLM ai_chat for conditional overrides in quiz flows
_original_llm_ai_chat = _llm_utils.ai_chat
from kubelingo.constants import SUBJECT_MATTERS
try:
    from prompt_toolkit import prompt
except ImportError:
    prompt = input
# Replace built-in input with prompt (prompt_toolkit or fallback) to enable line editing and history
builtins.input = prompt
try:
    from InquirerPy import inquirer
    from InquirerPy.utils import get_style
except ImportError:
    import types
    inquirer = types.SimpleNamespace(
        select=lambda *args, **kwargs: None,
        text=lambda *args, **kwargs: None
    )
    def get_style(style_dict, style_override=False):
        return None

# LLM providers and question types for testing and flows
LLM_PROVIDERS = ["gemini", "openai", "openrouter", "perplexity"]
QUESTION_TYPES = ["tf", "mcq", "vocab", "imperative", "declarative", "command", "manifest", "stored"]

# ASCII art banner for Kubelingo (disabled for now)
ASCII_ART = r"""
 /$$   /$$           /$$                 /$$       /$$                              
| $$  /$$/          | $$                | $$      |__/                              
| $$ /$$/  /$$   /$$| $$$$$$$   /$$$$$$ | $$       /$$ /$$$$$$$   /$$$$$$   /$$$$$$ 
| $$$$$/  | $$  | $$| $$__  $$ /$$__  $$| $$      | $$| $$__  $$ /$$__  $$ /$$__  $$
| $$  $$  | $$  | $$| $$  \ $$| $$$$$$$$| $$      | $$| $$  \ $$| $$  \ $$| $$  \ $$
| $$\  $$ | $$  | $$| $$  | $$| $$_____/| $$      | $$| $$  | $$| $$  | $$| $$  | $$
| $$ \  $$|  $$$$$$/| $$$$$$$/|  $$$$$$$| $$$$$$$$| $$| $$  | $$|  $$$$$$$|  $$$$$$/
|__/  \__/ \______/ |_______/  \_______/|________/|__/|__/  |__/ \____  $$ \______/ 
                                                                 /$$  \ $$          
                                                                |  $$$$$$/          
                                                                 \______/           
"""
# End of ASCII_ART; constants imported earlier


# Generate a Rich Text representation of the ASCII art with a blue/purple spiral coloring
def get_spiral_colored_art(art: str) -> Text:
    # Split into lines for full banner
    lines = art.strip('\n').splitlines()
    # Trim trailing spaces and pad to uniform width
    height = len(lines)
    width = max(len(line.rstrip()) for line in lines)
    grid = [list(line.rstrip().ljust(width)) for line in lines]
    order = []
    top, bottom = 0, height - 1
    left, right = 0, width - 1
    while left <= right and top <= bottom:
        for c in range(left, right + 1):
            order.append((top, c))
        for r in range(top + 1, bottom + 1):
            order.append((r, right))
        if top < bottom:
            for c in range(right - 1, left - 1, -1):
                order.append((bottom, c))
        if left < right:
            for r in range(bottom - 1, top, -1):
                order.append((r, left))
        top += 1; bottom -= 1; left += 1; right -= 1
    pos_to_idx = {pos: idx for idx, pos in enumerate(order)}
    txt = Text()
    for r in range(height):
        for c in range(width):
            ch = grid[r][c]
            idx = pos_to_idx.get((r, c), 0)
            color = 'blue' if idx % 2 == 0 else 'magenta'
            txt.append(ch, style=color)
        if r < height - 1:
            txt.append('\n')
    return txt

# Define a custom style for InquirerPy prompts
STYLE = get_style({
    "questionmark": "#e5c07b",
    "question": "#c678dd",
    "answer": "#61afef",
    "pointer": "#98c379",
    "instruction": "#abb2bf",
}, style_override=False)
last_generated_q = None  # track the last answered question for testing






def quiz_loop(questions: list) -> None:
    """The main quiz loop with a consistent menu flow for all question types."""
    global last_generated_q
    console = Console()
    if not questions:
        print("No questions to run a quiz session.")
        return

    current_question_index = 0
    while current_question_index < len(questions):
        question = questions[current_question_index]
        question_type = question.get("question_type")
        choices = question.get('choices') or question.get('options')

        # Clear screen for non-manifest questions
        if question_type != 'manifest':
            os.system('cls' if os.name == 'nt' else 'clear')
        console.print(Align(get_spiral_colored_art(ASCII_ART), align="center"))
        print(f"\nQuestion: {question['question']}")
        if choices:
            for idx, opt in enumerate(choices, start=1):
                print(f"  {idx}. {opt}")
        # For manifest questions, automatically launch editor and grade without showing menu
        if question_type == 'manifest':
            # Prepare editor template: vim modeline + commented prompt
            lines = question['question'].splitlines()
            commented = "\n".join(f"# {line}" for line in lines)
            modeline = "# vim: set ft=yaml ts=2 sw=2 sts=2 et\n"
            template = f"{modeline}{commented}\n\n"
            # Launch editor
            user_answer = _open_manifest_editor(template=template)
            # Show answer and grade
            print("Your answer:")
            print(user_answer)
            suggested_answer = question.get('suggested_answer') or question.get('answer', '')
            if user_answer.strip() == suggested_answer.strip():
                print("Correct!")
            else:
                print("Suggested Answer:")
                print(suggested_answer)
            current_question_index += 1
            continue

        # --- Question Menu ---
        action_taken = False
        while not action_taken:
            console.print(Text("\nv)im, c)lear, n)ext, p)revious, a)nswer, s)ource, q)uit", style="green"))
            user_input = input().strip().lower()
            
            if user_input.startswith('q'):
                print("\nQuiz session finished.")
                return
            elif user_input.startswith('p'):
                current_question_index = (current_question_index - 1 + len(questions)) % len(questions)
                break # Breaks inner loop to show previous question
            elif user_input.startswith('n'):
                current_question_index = (current_question_index + 1) % len(questions)
                break # Breaks inner loop to show next question
            elif user_input.startswith('c'):
                continue # Redraws the screen
            elif user_input.startswith('s'):
                source = question.get('source', 'N/A')
                print(f"Source: {source}")
                continue

            # --- Answering ---
            user_answer = ""
            if user_input.startswith('v'):
                qtext = question.get('question', '')
                lines = qtext.splitlines()
                commented = "\n".join(f"# {line}" for line in lines)
                template = f"{commented}\n\n"
                user_answer = _open_manifest_editor(template=template)
                action_taken = True
            elif user_input.startswith('a'):
                # Use InquirerPy text prompt for answer input when available
                try:
                    user_answer = inquirer.text(message="Your answer:").execute().strip()
                except Exception:
                    user_answer = input().strip()
                action_taken = True
            else: # Treat any other input as the answer
                user_answer = user_input
                action_taken = True

            if action_taken:
                # --- Grading and Feedback ---
                suggested_answer = question.get('suggested_answer') or question.get('answer', '')
                is_correct = user_answer.strip().lower() == suggested_answer.strip().lower()

                print("\nYour answer:")
                print(user_answer)
                if is_correct:
                    print("Correct!")
                else:
                    print("\nSuggested Answer:")
                    print(suggested_answer)
                    try:
                        sys_prompt = (
                            "You are a helpful Kubernetes instructor. "
                            "Provide constructive feedback on the user's answer compared to the suggested answer."
                        )
                        user_prompt = (
                            f"Question: {question['question']}\n"
                            f"Suggested Answer:\n{suggested_answer}\n"
                            f"User Answer:\n{user_answer}"
                        )
                        feedback = ai_chat(sys_prompt, user_prompt)
                        if feedback:
                            console.print("\nAI Feedback:", style="bold cyan")
                            console.print(feedback)
                            question['ai_feedback'] = feedback
                    except Exception as e:
                        print(f"[AI feedback error: {e}]")
                last_generated_q = question

                # --- Post-Answer Menu ---
                post_action_taken = False
                while not post_action_taken:
                    console.print(Text("\nr)etry, c)orrect, m)issed, s)ource, d)elete question", style="yellow"))
                    post_choice = input().strip().lower()
                    if post_choice.startswith('r'):
                        post_action_taken = True  # Will re-run the current question
                    elif post_choice.startswith('c'):
                        save_question(question, os.path.join(os.getcwd(), 'questions', 'correct'))
                        print("Question saved as correct.")
                        questions.pop(current_question_index)
                        post_action_taken = True
                    elif post_choice.startswith('m'):
                        save_question(question, os.path.join(os.getcwd(), 'questions', 'missed'))
                        print("Question saved as missed.")
                        questions.pop(current_question_index)
                        post_action_taken = True
                    elif post_choice.startswith('d'):
                        src = question.get('source')
                        if src and src != 'generated':
                            try:
                                os.remove(src)
                                print(f"Deleted question from {src}")
                            except OSError as e:
                                print(f"Error deleting question file: {e}")
                        else:
                            print("Discarding question.")
                        questions.pop(current_question_index)
                        post_action_taken = True
                    elif post_choice.startswith('s'):
                        source = question.get('source', 'N/A')
                        print(f"Source: {source}")
                    else:
                        print("Invalid choice.")
                # After post-answer action, adjust index
                if not post_choice.startswith('r'):
                    if not questions:
                        current_question_index = -1  # End loop
                    elif current_question_index >= len(questions):
                        current_question_index = 0
                    # Otherwise, index remains the same for the next question
                else:
                    # if retry, we need to decrement the index so that it gets incremented to the same question
                    current_question_index -= 1

        current_question_index += 1

    if not questions:
        print("\nNo more questions.")

# Alias for backward compatibility
quiz_session = quiz_loop
# Post-answer menu input helper (for consistency)
def post_answer_menu() -> str:
    """Read the user's choice from the post-answer menu."""
    try:
        return input().strip().lower()
    except EOFError:
        return 'q'

def import_menu() -> None:

    """Display the import menu for questions via file or URL."""
    questions_dir = os.path.join(os.getcwd(), 'questions')
    if not os.path.isdir(questions_dir):
        print("No questions directory found.")
        return
    choice = inquirer.select(
        message="Import Menu:",
        choices=["File/Folder Path", "URL", "Back"]
    ).execute()
    if choice == "Back":
        return
    if choice == "File/Folder Path":
        path = inquirer.text(message="Enter the file or directory path:").execute()
        try:
            questions = import_from_file(path)
            if questions:
                print(f"Successfully imported {len(questions)} questions from {path}.")
                for q in questions:
                    print(f"  - {q['question']}")
            else:
                print("No questions imported. The file might be empty or in an unsupported format.")
        except FileNotFoundError:
            print("File not found. Please enter a valid path.")
    elif choice == "URL":
        url = inquirer.text(message="Enter the URL to import from:").execute()
        try:
            questions = import_from_file(url)
            if questions:
                print(f"Successfully imported {len(questions)} questions from URL.")
                for q in questions:
                    print(f"  - {q['question']}")
            else:
                print("No questions imported from URL.")
        except Exception as e:
            print(f"Error importing from URL: {e}")

def select_topic() -> str:
    """Prompt the user to select a subject matter topic."""
    choices = SUBJECT_MATTERS + ["Back"]
    return inquirer.select(
        message="- Subject Matters",
        choices=choices,
        style=STYLE
    ).execute()

def settings_menu() -> None:
    """Display the Settings submenu for API keys and provider."""
    # Load current configuration
    from dotenv import dotenv_values
    config = dotenv_values(".env")
    gemini = config.get("GEMINI_API_KEY", "")
    openai = config.get("OPENAI_API_KEY", "")
    openrouter = config.get("OPENROUTER_API_KEY", "")
    perplexity = config.get("PERPLEXITY_API_KEY", "")
    
    console = Console()

    # Helpers
    def mask(key):
        return f"****{key[-4:]}" if key else "()"
    def status(key, prefix=""):
        if not key:
            return ""
        if prefix == "openai":
            return "Valid" if key.startswith("sk-") else "Invalid"
        return "Valid"
    # Models
    models = {
        "gemini": "gemini-1.5-flash-latest",
        "openai": "gpt-3.5-turbo",
        "openrouter": "deepseek/deepseek-r1-0528:free",
        "perplexity": "sonar-medium-online"
    }
    # Print menu
    console.print("- Config Menu:", style="bold magenta")
    console.print("    --- API Key Configuration ---", style="bold cyan")
    
    text = Text("      1. Set Gemini API Key (current: ", style="green")
    text.append(mask(gemini), style="yellow")
    text.append(f" {('('+status(gemini)+')') if gemini else ''}", style="green")
    text.append(f" (Model: {models['gemini']})")
    console.print(text)

    text = Text("      2. Set OpenAI API Key (current: ", style="green")
    text.append(mask(openai), style="yellow")
    text.append(f" {('('+status(openai,'openai')+')') if openai else ''}", style="green")
    text.append(f" (Model: {models['openai']})")
    console.print(text)

    text = Text("      3. Set OpenRouter API Key (current: ", style="green")
    text.append(mask(openrouter), style="yellow")
    text.append(f" {('('+status(openrouter)+')') if openrouter else ''}", style="green")
    text.append(f" (Model: {models['openrouter']})")
    console.print(text)

    text = Text("      4. Set Perplexity API Key (current: ", style="green")
    text.append(mask(perplexity), style="yellow")
    text.append(f" {('('+status(perplexity)+')') if perplexity else ''}", style="green")
    text.append(f" (Model: {models['perplexity']})")
    console.print(text)

    console.print()
    console.print("    --- AI Provider Selection ---", style="bold cyan")
    provider = config.get("KUBELINGO_LLM_PROVIDER", "")
    provider_disp = provider or "none"
    
    text = Text("      5. Choose AI Provider (current: ", style="green")
    text.append(provider_disp, style="yellow")
    text.append(")")
    console.print(text)

    console.print("      6. Back", style="green")
    choice = input("? Enter your choice: ").strip()
    # TODO: implement choice actions
    if choice == "1":
        key = inquirer.text(message="Enter Gemini API Key:", password=True).execute()
        _update_env_file("GEMINI_API_KEY", key)
    elif choice == "2":
        key = inquirer.text(message="Enter OpenAI API Key:", password=True).execute()
        _update_env_file("OPENAI_API_KEY", key)
    elif choice == "3":
        key = inquirer.text(message="Enter OpenRouter API Key:", password=True).execute()
        _update_env_file("OPENROUTER_API_KEY", key)
    elif choice == "4":
        key = inquirer.text(message="Enter Perplexity API Key:", password=True).execute()
        _update_env_file("PERPLEXITY_API_KEY", key)
    elif choice == "5":
        provider_choice = inquirer.select(
            message="Choose AI Provider:",
            choices=LLM_PROVIDERS,
            default=provider if provider else None,
            style=STYLE
        ).execute()
        _update_env_file("KUBELINGO_LLM_PROVIDER", provider_choice)
    return

def _update_env_file(key: str, value: str):
    """Updates or adds a key-value pair in the .env file."""
    env_path = os.path.join(os.getcwd(), ".env")
    lines = []
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            lines = f.readlines()

    found = False
    with open(env_path, 'w') as f:
        for line in lines:
            if line.startswith(f"{key}="):
                f.write(f"{key}={value}\n")
                found = True
            else:
                f.write(line)
        if not found:
            f.write(f"{key}={value}\n")
    print(f"Updated {key} in .env file.")

def save_question(question: dict, directory: str):
    """Save a question to a file."""
    if not os.path.isdir(directory):
        os.makedirs(directory)
    file_path = os.path.join(directory, f"{question['id']}.json")
    with open(file_path, 'w') as f:
        json.dump(question, f, indent=4)

def static_quiz():
    """Run a quiz on on-disk questions under questions/<category> directories, moving files based on user action."""
    base_dir = os.path.join(os.getcwd(), 'questions')
    if not os.path.isdir(base_dir):
        print("No questions directory found.")
        return
    # Iterate through each category (e.g., uncategorized)
    for category in sorted(os.listdir(base_dir)):
        category_path = os.path.join(base_dir, category)
        if not os.path.isdir(category_path):
            continue
        # Find all JSON question files
        for qfile in sorted(glob.glob(os.path.join(category_path, '*.json'))):
            try:
                with open(qfile, 'r', encoding='utf-8') as f:
                    qdata = json.load(f)
            except Exception:
                continue
            # Prompt the user for action
            print(f"\nQuestion: {qdata.get('question', '')}")
            action = inquirer.select(
                message="- Post Answer Menu",
                choices=[
                    {"name": "Correct", "value": "Correct"},
                    {"name": "Missed", "value": "Missed"},
                    {"name": "Remove Question", "value": "Remove Question"},
                    {"name": "Quit", "value": "Quit"},
                ],
                style=STYLE
            ).execute()
            # Handle quit
            if action.lower() in ("q", "quit"):  # Quit static quiz
                return
            # Determine destination directory name
            dest_map = {"Correct": "correct", "Missed": "missed", "Remove Question": "triage"}
            dest_key = dest_map.get(action)
            if dest_key:
                dest_path = os.path.join(base_dir, dest_key, category)
                os.makedirs(dest_path, exist_ok=True)
                # Move the file
                try:
                    shutil.move(qfile, dest_path)
                except Exception as e:
                    print(f"Error moving file: {e}")


def _open_manifest_editor(template: str = "") -> str:
    """
    Open a manifest editor for Kubernetes YAML content.
    Writes the provided template to a temp file, opens the EDITOR, and returns edited content.
    """
    import tempfile, os
    # Ensure test manifests are written under the 'tests' directory
    tests_dir = os.path.join(os.getcwd(), 'tests')
    try:
        os.makedirs(tests_dir, exist_ok=True)
    except Exception:
        pass
    # Create temp file in tests directory so test manifest files appear there
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.yaml', dir=tests_dir) as tmpfile:
        tmpfile.write(template or "")
        tmpfile.flush()
        tmp_path = tmpfile.name
    editor = os.environ.get('EDITOR', 'vim') or 'vim'
    
    # For vim, add commands to ensure settings are applied
    if 'vim' in editor:
        # The modeline should be respected, but we can add extra commands if needed
        # Forcing syntax on is a good practice
        os.system(f'{editor} -c "syntax on" {tmp_path}')
    else:
        os.system(f'{editor} {tmp_path}')

    try:
        with open(tmp_path, 'r') as tmpfile:
            content = tmpfile.read()
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
    # Remove the modeline before returning; if no modeline present, return full content
    lines = content.split('\n')
    if lines and lines[0].startswith('# vim:'):
        return '\n'.join(lines[1:])
    else:
        return content

def quiz_menu() -> None:
    """Display the quiz menu and start a quiz session."""
    while True: # Loop to allow returning from subject matter selection
        # Question Type Menu (user-friendly)
        question_type_choices = [
            "True/False",
            "Vocab",
            "Multiple Choice",
            "Imperative (Commands)",
            "Declarative (Manifests)",
            "Stored",
            "Back",
        ]

        question_type = inquirer.select(
            message="- Type Menu",
            choices=question_type_choices,
            style=STYLE
        ).execute()
        
        # Map user choice to internal QG type
        type_map = {
            "True/False": "true/false",
            "Vocab": "vocabulary",
            "Multiple Choice": "multiple choice",
            "Imperative (Commands)": "command",
            "Declarative (Manifests)": "manifest",
        }
        internal_qtype = type_map.get(question_type, question_type.lower())

        if question_type == "Back":
            return
        
        if question_type == "Static":
            static_quiz()
            return

        subject_matter = select_topic()
        if subject_matter == "Back":
            continue
        
        try:
            count_str = inquirer.text(message="How many questions would you like? ").execute()
            count = int(count_str)
            if count <= 0:
                raise ValueError
        except Exception:
            print("Invalid number. Returning to quiz menu.")
            continue

        questions = []
        if internal_qtype == "stored":
            base_dir = os.path.join(os.getcwd(), 'questions', 'stored')
            files = glob.glob(os.path.join(base_dir, '*.json'))
            if not files:
                print("No stored questions available.")
                continue
            all_qs = []
            for fp in files:
                try:
                    with open(fp, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        all_qs.append(data)
                except Exception:
                    continue
            questions = [q for q in all_qs if q.get('topic') == subject_matter]
            if not questions:
                print(f"No stored questions found for subject '{subject_matter}'.")
                continue
            if count < len(questions):
                questions = questions[:count]
            elif count > len(questions):
                print(f"Only {len(questions)} stored questions available; showing all.")
            for q in questions:
                if 'question_type' not in q:
                    q['question_type'] = q.get('type', 'stored')
        else:
            gen = QuestionGenerator()
            if internal_qtype == 'manifest':
                mg = ManifestGenerator()
                gen.manifest_generator = mg

            if _llm_utils.ai_chat is _original_llm_ai_chat:
                _llm_utils.ai_chat = ai_chat
            
            questions = gen.generate_question_set(
                count=count,
                question_type=internal_qtype,
                subject_matter=subject_matter
            )
            if any(isinstance(q.get('question'), str) and q['question'].startswith("Failed to generate AI question") for q in questions):
                print("AI generation failed. Please try the stored quiz mode via 'Stored' option.")
                return
            if not questions:
                print(f"No questions generated for topic '{subject_matter}'.")
                continue

        quiz_loop(questions)
        return


def main():
    """Main entry point for the Kubelingo CLI application."""
    console = Console()
    while True:
        console.print(Align(get_spiral_colored_art(ASCII_ART), align="center"))
        choice = inquirer.select(
            message="Main Menu:",
            choices=[
                "Quiz",
                "Import",
                "Settings",
                "Exit"
            ],
            style=STYLE
        ).execute()

        if choice == "Quiz":
            quiz_menu()
        elif choice == "Import":
            import_menu()
        elif choice == "Settings":
            settings_menu()
        elif choice == "Exit":
            console.print("Exiting Kubelingo. Goodbye!", style="bold red")
            sys.exit(0)

if __name__ == "__main__":
    main()