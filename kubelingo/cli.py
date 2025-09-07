#!/usr/bin/env python3
"""
CLI entry point for Kubelingo application.
Displays the main menu as per requirements.md specifications.
"""
import sys
import os
import json
import glob
import yaml
from InquirerPy import inquirer
from InquirerPy.utils import get_style
from kubelingo.importer import import_from_file
from kubelingo.question_generator import QuestionGenerator
from rich.console import Console
from rich.text import Text
import requests
from kubelingo.llm_utils import ai_chat
from kubelingo.constants import SUBJECT_MATTERS


# LLM providers and question types for testing and flows
LLM_PROVIDERS = ["gemini", "openai", "openrouter", "perplexity"]
QUESTION_TYPES = ["tf", "mcq", "vocab", "imperative", "declarative", "stored"]

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
  K:::::::::::K      u::::u    u::::u   b:::::bbbbb:::::::b e::::::e     e:::::e l:::::l  i:::::i  n::::::::::::::n g::::::ggggg::::::g go:::::ooooo::::o
  K:::::::::::K      u::::u    u::::u   b:::::b    b::::::b e:::::::eeeee::::::e l:::::l  i:::::i  n:::::nnnn:::::n g:::::g     g:::::g o::::o     o::::o
  K::::::K:::::K     u::::u    u::::u   b:::::b     b:::::b e:::::::::::::::::e  l:::::l  i:::::i  n::::n    n::::n g:::::g     g:::::g o::::o     o::::o
  K:::::K K:::::K    u:::::uuuu:::::u   b:::::b     b:::::b e::::::eeeeeeeeeee   l:::::l  i:::::i  n::::n    n::::n g:::::g     g:::::g o::::o     o:::::o
KK::::::K  K:::::KKK u:::::uuuu:::::u   b:::::b     b:::::b e:::::::e            l:::::l i:::::i  n::::n    n::::n g::::::g    g:::::g o:::::ooooo:::::o
K:::::::K   K::::::K u:::::::::::::::uu b:::::bbbbbb::::::b e::::::::e           l:::::l i:::::i  n::::n    n::::n g:::::::ggggg:::::g o:::::ooooo:::::o
K:::::::K    K:::::K  u:::::::::::::::u b:::::::::::::::b     ee:::::::::::::e   l:::::l i:::::i  n::::n    n::::n  g::::::::::::::::g o:::::::::::::::o
K:::::::K    K:::::K   uu::::::::uu:::u b:::::::::::::::b     ee:::::::::::::e   l:::::l i:::::i  n::::n    n::::n   gg::::::::::::::g  oo:::::::::::oo
KKKKKKKKK    KKKKKKK     uuuuuuuu  uuuu bbbbbbbbbbbbbbbb        eeeeeeeeeeeeee   lllllll iiiiiii  nnnnnn    nnnnnn     gggggggg::::::g    ooooooooooo
                                                                                                                               g:::::g
                                                                                                                   gggggg      g:::::g
                                                                                                                   g:::::gg   gg:::::g
                                                                                                                    g::::::ggg:::::::g
                                                                                                                     gg:::::::::::::g
                                                                                                                       ggg::::::ggg
                                                                                                                          gggggg
"""
from kubelingo.constants import SUBJECT_MATTERS

# Define a custom style for InquirerPy prompts
STYLE = get_style({
    "questionmark": "#e5c07b",
    "question": "#c678dd",
    "answer": "#61afef",
    "pointer": "#98c379",
    "instruction": "#abb2bf",
}, style_override=False)

def handle_post_answer(question: dict, questions: list, current_question_index: int) -> int:
    """Handle the post-answer menu and return the new question index."""
    choice = post_answer_menu()
    if choice == 'r':
        # retry same question
        return current_question_index
    elif choice == 'c':
        # save as correct and remove from question list
        save_question(question, os.path.join(os.getcwd(), 'questions', 'correct'))
        print("Question saved as correct.")
        questions.pop(current_question_index)
        return current_question_index % len(questions) if questions else None
    elif choice == 'm':
        # save as missed and remove from question list
        save_question(question, os.path.join(os.getcwd(), 'questions', 'missed'))
        print("Question saved as missed.")
        questions.pop(current_question_index)
        return current_question_index % len(questions) if questions else None
    elif choice == 's':
        # display source and return to the same question
        print(f"Source: {question.get('source', 'N/A')}")
        return current_question_index
    elif choice == 'd':
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
        return current_question_index % len(questions) if questions else None
    # move to next question by default
    return (current_question_index + 1) % len(questions)

def quiz_session(questions: list) -> None:
    """Run a simple quiz session on a given list of questions."""
    console = Console()
    if not questions:
        print("No questions to run a quiz session.")
        return

    original_num_questions = len(questions)
    questions_answered_count = 0
    current_question_index = 0

    while questions_answered_count < original_num_questions:
        if not questions: # If all questions are removed (e.g., by 'd'), exit
            break

        question = questions[current_question_index]

        print(f"\nQuestion: {question['question']}")
        
        if 'choices' in question:
            for j, choice in enumerate(question['choices']):
                print(f"  {j+1}. {choice}")

        print("v)im, c)lear, n)next, p)revious, a)nswer, s)ource, q)quit")

        user_input = input()

        if user_input == 'q':
            break
        elif user_input == 'n':
            current_question_index = (current_question_index + 1) % len(questions)
            continue
        elif user_input == 'p':
            current_question_index = (current_question_index - 1) % len(questions)
            continue
        elif user_input == 'a':
            suggested = question.get('suggested_answer') or question.get('answer', '')
            console.print(Text("Suggested Answer:", style="bold magenta"))
            console.print(Text(suggested, style="green"))
            idx = handle_post_answer(question, questions, current_question_index)
            if idx is None or not questions:
                break
            current_question_index = idx
            questions_answered_count += 1
        elif user_input == 's':
            source = question.get('source', 'N/A')
            print(f"Source: {source}")
            continue
        elif user_input == 'v':
            print("Vim mode is not implemented yet.")
            continue
        elif user_input == 'c':
            os.system('cls' if os.name == 'nt' else 'clear')
            continue
        else:
            # Treat input as an answer; record and grade it
            user_answer = user_input
            # Map numeric choice to actual option if applicable
            if 'choices' in question and user_input.isdigit():
                try:
                    sel = int(user_input) - 1
                    if 0 <= sel < len(question['choices']):
                        user_answer = question['choices'][sel]
                except ValueError:
                    pass
            question['user_answer'] = user_answer
            suggested = question.get('suggested_answer') or question.get('answer', '')
            console.print(Text("Suggested Answer:", style="bold magenta"))
            console.print(Text(suggested, style="green"))
            if suggested and user_answer.strip().lower() == suggested.strip().lower():
                console.print(Text("(Your answer matches the suggested answer verbatim.)", style="bold green"))
            else:
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
            idx = handle_post_answer(question, questions, current_question_index)
            if idx is None or not questions:
                break
            current_question_index = idx
            questions_answered_count += 1
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

def post_answer_menu() -> str:
    """Display the post-answer menu and return the user's choice."""
    print("r)etry, c)orrect, m)issed, s)ource, d)elete question")
    while True:
        choice = input().strip().lower()
        if choice in ['r', 'c', 'm', 's', 'd']:
            return choice
        else:
            print("Invalid choice. Please try again.")

def quiz_menu() -> None:
    """Display the quiz menu and start a quiz session."""
    while True: # Loop to allow returning from subject matter selection
        question_type_choices = [
            "true/false",
            "vocabulary",
            "multiple choice",
            "imperative",
            "declarative",
            "stored",
            "Back",
        ]

        question_type = inquirer.select(
            message="- Type Menu",
            choices=question_type_choices,
            style=STYLE
        ).execute()

        if question_type == "Back":
            return

        questions = []
        if question_type == "Stored":
            base_dir = os.path.join(os.getcwd(), 'questions', 'stored')
            question_files = glob.glob(os.path.join(base_dir, '*.yaml'))
            if not question_files:
                print(f"No questions found in the Stored category.")
                return
            for file_path in question_files:
                with open(file_path, 'r') as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, list):
                        questions.extend(data)
            if not questions:
                print(f"No questions found for the selected category.")
                return
            quiz_session(questions)
            return # Exit quiz_menu after stored quiz session

        # If not 'Stored', then ask for Subject Matters
        subject_matter_choices = SUBJECT_MATTERS + ["Back"]
        subject_matter = inquirer.select(
            message="- Subject Matters",
            choices=subject_matter_choices,
            style=STYLE
        ).execute()

        if subject_matter == "Back":
            continue # Go back to type selection

        try:
            count_str = inquirer.text(message="How many questions would you like? ").execute()
            count = int(count_str)
        except Exception:
            print("Invalid number. Returning to quiz menu.")
            continue # Go back to type selection

        gen = QuestionGenerator()
        # Pass question_type and topic to generate_question_set
        questions = gen.generate_question_set(count=count, question_type=question_type, subject_matter=subject_matter)

        if not questions:
            print(f"No questions found for the selected category.")
            continue # Go back to type selection

        quiz_session(questions)
        return # Exit quiz_menu after AI quiz session


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
