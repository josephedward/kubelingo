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
from InquirerPy import inquirer
from InquirerPy.utils import get_style
from kubelingo.importer import import_from_file
from kubelingo.question_generator import QuestionGenerator
from rich.console import Console
from rich.text import Text
import requests
import shutil
import kubelingo.llm_utils as _llm_utils
from kubelingo.llm_utils import ai_chat
# Keep track of the original LLM ai_chat for conditional overrides in quiz flows
_original_llm_ai_chat = _llm_utils.ai_chat
from kubelingo.constants import SUBJECT_MATTERS


# LLM providers and question types for testing and flows
LLM_PROVIDERS = ["gemini", "openai", "openrouter", "perplexity"]
QUESTION_TYPES = ["tf", "mcq", "vocab", "imperative", "declarative", "command", "manifest", "stored"]

# ASCII art banner for Kubelingo (disabled for now)
ASCII_ART = r"""
                                        bbbbbbb
KKKKKKKKK    KKKKKKK                    b:::::b                                  lllllll   iiii
K:::::::K    K:::::K                    b:::::b                                  l:::::l  i::::i
K:::::::K    K:::::K                    b:::::b                                  l:::::l   iiii
K:::::::K   K::::::K                    b:::::b                                  l:::::l 
KK::::::K  K:::::KKK uuuuuu    uuuuuu   b:::::bbbbbbbbb         eeeeeeeeeeee     l:::::l  iiiiii  nnnn  nnnnnnnn      ggggggggg   gggg   ooooooooooo
  K:::::K K:::::K    u::::u    u::::u   b::::::::::::::bb     ee::::::::::::ee   l:::::l  i::::i  n::nn::::::::nn    g:::::::::ggg:::g oo:::::::::::oo
  K::::::K:::::K     u::::u    u::::u   b::::::::::::::::b   e::::::eeeee:::::ee l:::::l  i:::::i  n:::::::::::::nn  g::::::::::::::::g o:::::::::::::::o
  K:::::::::::K      u::::u    u::::u   b:::::bbbbb:::::::b e::::::e     e:::::e l:::::l  i:::::i  n:::::nnnn:::::n g::::::ggggg::::::g go:::::ooooo::::o
  K::::::K:::::K     u::::u    u::::u   b:::::b    b::::::b e:::::::eeeee::::::e l:::::l  i:::::i  n::::n    n::::n g:::::g     g:::::g o::::o     o::::o
  K:::::K K:::::K    u::::u    u::::u   b:::::b     b:::::b e:::::::::::::::::e  l:::::l  i:::::i  n::::n    n::::n g:::::g     g:::::g o::::o     o:::::o
  K:::::uuuu:::::u   b:::::b     b:::::b e::::::eeeeeeeeeee   l:::::l  i:::::i  n::::n    n::::n g:::::g     g:::::g o::::o     o:::::o
KK::::::K  K:::::KKK u:::::uuuu:::::u   b:::::b     b:::::b e:::::::e            l:::::l i:::::i  n::::n    n::::n g::::::g    g:::::g o:::::ooooo:::::o
K:::::::K   K::::::K u:::::::::::::::uu b:::::bbbbbb::::::b e::::::::e           l:::::l i:::::i  n::::n    n::::n g:::::::ggggg:::::g o:::::ooooo:::::o
K:::::::K    K:::::K  u:::::::::::::::u b:::::::::::::::b     ee:::::::::::::e   l:::::l i:::::i  n::::n    n:::::n   gg::::::::::::::g  oo:::::::::::oo
K:::::::K    K:::::K   uu::::::::uu:::u b:::::::::::::::b     ee:::::::::::::e   l:::::l i:::::i  n::::n    n:::::n     gggggggg::::::g    ooooooooooo
KKKKKKKKK    KKKKKKK   uuu uuuuu  uuuu bbbbbbbbbbbbbbbb        eeeeeeeeeeeeee   lllllll iiiiiii  nnnnnn    nnnnnn     gggggggg::::::g    ooooooooooo
                                                                                                                               g:::::g
                                                                                                                   gggggg      g:::::g
                                                                                                                   g:::::gg   gg:::::g
                                                                                                                    g::::::ggg:::::::g
                                                                                                                     gg:::::::::::::g
                                                                                                                       ggg::::::ggg
                                                                                                                          gggggg
"""
# End of ASCII_ART; constants imported earlier


# Define a custom style for InquirerPy prompts
STYLE = get_style({
    "questionmark": "#e5c07b",
    "question": "#c678dd",
    "answer": "#61afef",
    "pointer": "#98c379",
    "instruction": "#abb2bf",
}, style_override=False)
last_generated_q = None  # track the last answered question for testing

def handle_post_answer(question: dict, questions: list, current_question_index: int, choice: str) -> int:
    # normalize full choice string to first letter command
    # normalize full choice string to first letter command
    key = choice[0].lower() if choice else ''
    if key == 'r':
        # retry same question
        return current_question_index
    elif key == 'c':
        # save as correct and remove from question list
        save_question(question, os.path.join(os.getcwd(), 'questions', 'correct'))
        print("Question saved as correct.")
        questions.pop(current_question_index)
        if not questions:
            return None
        return current_question_index % len(questions)
    elif key == 'm':
        # save as missed and remove from question list
        save_question(question, os.path.join(os.getcwd(), 'questions', 'missed'))
        print("Question saved as missed.")
        questions.pop(current_question_index)
        if not questions:
            return None
        return current_question_index % len(questions)
    elif key == 'd':
        # delete or discard question
        src = question.get('source')
        if src and src != 'generated':
            try:
                os.remove(src)
                print(f"Deleted question from {src}")
            except OSError as e:
                print(f"Error deleting question file: {e}")
        else:
            # no file to delete, just discard
            print("Discarding question.")
        questions.pop(current_question_index)
        if not questions:
            return None
        return current_question_index % len(questions)
    elif key == 's': # Handle 's)ource' option
        source = question.get('source', 'N/A')
        print(f"Source: {source}")
        return current_question_index # Stay on the same question
    elif key == 'q':
        # Show next question before quitting the session
        if questions:
            next_index = (current_question_index + 1) % len(questions)
            next_question = questions[next_index]
            print(f"\nQuestion: {next_question['question']}")
        return None
    # any other key (including empty) moves to next question by default
    # move to next question by default
    if not questions: # If no questions left, return None
        return None
    return (current_question_index + 1) % len(questions)

def quiz_session(questions: list) -> None:
    """Run a simple quiz session on a given list of questions."""
    global last_generated_q
    console = Console()
    if not questions:
        print("No questions to run a quiz session.")
        return

    current_question_index = 0

    while questions: # Loop as long as there are questions
        if not questions: # If all questions are removed (e.g., by 'd'), exit
            break

        question = questions[current_question_index]
        suggested = question.get('suggested_answer', '') # Define suggested here
        # Support both 'choices' and 'options' keys for multiple choice questions
        choices = question.get('choices') or question.get('options')
        # Determine the suggested answer for grading and feedback
        suggested = question.get('suggested_answer') or question.get('answer', '')
        print(f"\nQuestion: {question['question']}")
        if choices:
            for idx_opt, opt in enumerate(choices, start=1):
                print(f"  {idx_opt}. {opt}")

        # Question menu (consistent across all types)
        console.print(Text("v) vim, c) clear, n) next, p) previous, a) answer, s) source, q) quit", style="green"))
        user_input = input().strip().lower()
        # Help: reprint menu options
        if user_input == '?':
            console.print(Text("v) vim, c) clear, n) next, p) previous, a) answer, s) source, q) quit", style="green"))
            continue

        if user_input == 'q':
            break
        elif user_input == 'p':
            current_question_index = (current_question_index - 1) % len(questions)
            continue
        elif user_input == 'n':
            current_question_index = (current_question_index + 1) % len(questions)
            continue
        elif user_input == 'a':
            # Grade using suggested answer or show it for non-MCQ
            if choices:
                # Multiple-choice: auto-grade correctness
                correct = False
                # Normalize comparison
                if suggested and question.get('answer'):
                    if suggested.strip().lower() == question['answer'].strip().lower():
                        correct = True
                if correct:
                    print("Correct!")
                else:
                    print("Incorrect!")
                question['user_answer'] = suggested
            else:
                # Free-form answer: show suggested answer
                print(f"Suggested Answer:\n{suggested}")
                question['user_answer'] = suggested
                if suggested and question['user_answer'].strip().lower() == suggested.strip().lower():
                    print("Correct!")
            last_generated_q = question
            print('r)etry, c)orrect, m)issed, s)ource, d)elete question')
            post_answer_choice = post_answer_menu()
            idx = handle_post_answer(question, questions, current_question_index, post_answer_choice)
            if idx is None:
                break
            current_question_index = idx
        elif user_input == 's':
            source = question.get('source', 'N/A')
            print(f"Source: {source}")
            continue
        elif user_input == 'v':
            suggested_answer = question.get('suggested_answer', '')
            print(f"\n--- Opening editor for manifest. Save and close the file to continue. ---")
            user_answer = _open_manifest_editor(suggested_answer) # Use the actual editor

            question['user_answer'] = user_answer # Update question with the user's answer
            
            # Grading logic (copied from else block)
            if suggested and user_answer.strip().lower() == suggested.strip().lower():
                print("Correct!") # Added for consistency
            else:
                # Only provide AI feedback if the answer differs
                console.print(Text("(Your answer differs from the suggested answer.)", style="bold yellow"))
                try:
                    sys_prompt = (
                        "You are a helpful Kubernetes instructor. "
                        "Provide constructive feedback on the user's answer compared to the suggested answer."
                    )
                    user_prompt = (
                        f"Question: {question['question']}\n"
                        f"Suggested Answer:\n{suggested}\n"
                        f"User Answer:\n{user_answer}"
                    )
                    feedback = ai_chat(sys_prompt, user_prompt)
                except Exception as e:
                    feedback = f"[AI feedback error: {e}]"
                if feedback:
                    console.print(Text("\nAI Feedback:\n", style="bold cyan"))
                    console.print(feedback)
                question['ai_feedback'] = feedback
            
            last_generated_q = question
            print('r)etry, c)orrect, m)issed, s)ource, d)elete question')
            post_answer_choice = post_answer_menu()
            idx = handle_post_answer(question, questions, current_question_index, post_answer_choice)
            if idx is None: # Only break if handle_post_answer explicitly returns None
                break
            current_question_index = idx
        elif user_input == 'c':
            os.system('cls' if os.name == 'nt' else 'clear')
            continue # Stay on the same question after clearing
        else:
            # Treat input as an answer; record, show suggested answer, and grade it
            user_answer = user_input
            # Map numeric choice to actual option if applicable
            if choices and user_input.isdigit():
                try:
                    sel = int(user_input) - 1
                    if 0 <= sel < len(choices):
                        user_answer = choices[sel]
                except ValueError:
                    pass
            question['user_answer'] = user_answer
            # Display suggested answer for comparison
            print(f"Suggested Answer:\n{suggested}")
            
            if suggested and user_answer.strip().lower() == suggested.strip().lower():
                print("Correct!") # Added for consistency
            else:
                # Only provide AI feedback if the answer differs
                console.print(Text("(Your answer differs from the suggested answer.)", style="bold yellow"))
                try:
                    sys_prompt = (
                        "You are a helpful Kubernetes instructor. "
                        "Provide constructive feedback on the user's answer compared to the suggested answer."
                    )
                    user_prompt = (
                        f"Question: {question['question']}\n"
                        f"Suggested Answer:\n{suggested}\n"
                        f"User Answer:\n{user_answer}"
                    )
                    feedback = ai_chat(sys_prompt, user_prompt)
                except Exception as e:
                    feedback = f"[AI feedback error: {e}]"
                if feedback:
                    console.print(Text("\nAI Feedback:\n", style="bold cyan"))
                    console.print(feedback)
                question['ai_feedback'] = feedback
            
            last_generated_q = question
            print('r)etry, c)orrect, m)issed, s)ource, d)elete question')
            post_answer_choice = post_answer_menu()
            idx = handle_post_answer(question, questions, current_question_index, post_answer_choice)
            if idx is None: # Only break if handle_post_answer explicitly returns None
                break
            current_question_index = idx
    print("Quiz session finished.")

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

def post_answer_menu() -> str:
    """Display the post-answer menu and return the user's choice."""
    # Read the user's choice for post-answer actions
    return input().strip().lower()
def _open_manifest_editor(template: str = "") -> str:
    """
    Open a manifest editor for Kubernetes YAML content.
    Writes the provided template to a temp file, opens the EDITOR, and returns edited content.
    """
    import tempfile, os
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.yaml') as tmpfile:
        tmpfile.write(template or "")
        tmpfile.flush()
        tmp_path = tmpfile.name
    editor = os.environ.get('EDITOR', 'vim') or 'vim'
    os.system(f'{editor} {tmp_path}')
    try:
        with open(tmp_path, 'r') as tmpfile:
            content = tmpfile.read()
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
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
        # Handle review of uncategorized on-disk questions
        if question_type == "Static":
            static_quiz()
            return

        # Ask for Subject Matter
        subject_matter = select_topic()
        if subject_matter == "Back":
            continue
        # Handle manifest question type separately
        if internal_qtype == 'manifest':
            # Ask for number of questions
            try:
                count_str = inquirer.text(message="How many questions would you like? ").execute()
                count = int(count_str)
                if count <= 0:
                    raise ValueError
            except Exception:
                print("Invalid number. Returning to quiz menu.")
                continue

            # Generate manifest questions
            gen = QuestionGenerator()
            if _llm_utils.ai_chat is _original_llm_ai_chat:
                _llm_utils.ai_chat = ai_chat
            questions = gen.generate_question_set(
                count=count,
                question_type=internal_qtype,
                subject_matter=subject_matter
            )
            if not questions:
                print(f"No manifest questions generated for topic '{subject_matter}'.")
                return

            # Loop through questions
            for question in questions:
                print(f"\nQuestion: {question.get('question', '')}")
                manifest_content = _open_manifest_editor()
                print("Your answer:")
                print(manifest_content)
                suggested = question.get('suggested_answer') or question.get('answer', '')
                if manifest_content.strip() == suggested.strip():
                    print("Correct!")
                else:
                    print("Suggested Answer:")
                    print(suggested)
            return

        # Ask for number of questions
        try:
            count_str = inquirer.text(message="How many questions would you like? ").execute()
            count = int(count_str)
            if count <= 0:
                raise ValueError
        except Exception:
            print("Invalid number. Returning to quiz menu.")
            continue

        questions = []
        # Load stored questions from disk if requested
        if internal_qtype == "stored":
            base_dir = os.path.join(os.getcwd(), 'questions', 'stored')
            # Load all JSON files
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
            # Filter by subject matter (topic)
            questions = [q for q in all_qs if q.get('topic') == subject_matter]
            if not questions:
                print(f"No stored questions found for subject '{subject_matter}'.")
                continue
            # Limit to requested count
            if count < len(questions):
                questions = questions[:count]
            elif count > len(questions):
                print(f"Only {len(questions)} stored questions available; showing all.")
            # Ensure question_type field is present
            for q in questions:
                if 'question_type' not in q:
                    q['question_type'] = q.get('type', 'stored')
        else:
            # Generate AI questions for other types
            gen = QuestionGenerator()
            # Ensure QuestionGenerator uses CLI ai_chat (without overwriting test stubs)
            if _llm_utils.ai_chat is _original_llm_ai_chat:
                _llm_utils.ai_chat = ai_chat
            questions = gen.generate_question_set(
                count=count,
                question_type=internal_qtype,
                subject_matter=subject_matter
            )
            # Check for generation failures
            if any(isinstance(q.get('question'), str) and q['question'].startswith("Failed to generate AI question") for q in questions):
                print("AI generation failed. Please try the stored quiz mode via 'Stored' option.")
                return
            if not questions:
                print(f"No questions generated for topic '{subject_matter}'.")
                continue

        quiz_session(questions)
        return # Exit quiz_menu after session


def main():
    """Main entry point for the Kubelingo CLI application."""
    console = Console()
    while True:
        console.print(ASCII_ART, style="bold green")
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