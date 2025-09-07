#!/usr/bin/env python3
"""
CLI entry point for Kubelingo application.
Displays the main menu as per requirements.md specifications.
"""
import sys
import os
import json
import glob
from InquirerPy import inquirer
from InquirerPy.utils import get_style
from rich.console import Console
from rich.text import Text


# ASCII art banner for Kubelingo (disabled for now)
ASCII_ART = r"""
                                        bbbbbbb
KKKKKKKKK    KKKKKKK                    b:::::b                                  lllllll   iiii
K:::::::K    K:::::K                    b:::::b                                  l:::::l  i::::i
K:::::::K    K:::::K                    b:::::b                                  l:::::l   iiii
K:::::::K   K::::::K                    b:::::b                                  l:::::l
KK::::::K  K:::::KKK uuuuuu    uuuuuu   b:::::bbbbbbbbb         eeeeeeeeeeee     l:::::l  iiiiii  nnnn  nnnnnnnn      ggggggggg   gggg   ooooooooooo
  K:::::K K:::::K    u::::u    u::::u   b::::::::::::::bb     ee::::::::::::ee   l:::::l  i::::i  n::nn::::::::nn    g:::::::::ggg:::g oo:::::::::::oo
  K::::::K:::::K     u::::u    u::::u   b::::::::::::::::b   e::::::eeeee:::::ee l:::::l  i::::i  n:::::::::::::nn  g::::::::::::::::g o:::::::::::::::o
  K:::::::::::K      u::::u    u::::u   b:::::bbbbb:::::::b e::::::e     e:::::e l:::::l  i:::::i  n::::::::::::::n g::::::ggggg::::::g go:::::ooooo::::o
  K:::::::::::K      u::::u    u::::u   b:::::b    b::::::b e:::::::eeeee::::::e l:::::l  i:::::i  n:::::nnnn:::::n g:::::g     g:::::g o::::o     o::::o
  K::::::K:::::K     u::::u    u::::u   b:::::b     b:::::b e:::::::::::::::::e  l:::::l  i:::::i  n::::n    n::::n g:::::g     g:::::g o::::o     o::::o
  K:::::K K:::::K    u::::u    u::::u   b:::::b     b:::::b e::::::eeeeeeeeeee   l:::::l  i:::::i  n::::n    n::::n g:::::g     g:::::g o::::o     o::::o
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

# Define a custom style for InquirerPy prompts
STYLE = get_style({
    "questionmark": "#e5c07b",
    "question": "#c678dd",
    "answer": "#61afef",
    "pointer": "#98c379",
    "instruction": "#abb2bf",
}, style_override=False)

def colorize_ascii_art(art: str) -> str:
    """Apply any color/styling to the ASCII art (no-op placeholder)."""
    return art

def quiz_session(category: str) -> None:
    """Run a simple quiz session on stored questions in the given category."""
    base_dir = os.path.join(os.getcwd(), 'questions', category.lower())
    if not os.path.isdir(base_dir):
        print(f"No {category} questions found.")
        return
    found_any = False
    for filepath in glob.glob(os.path.join(base_dir, '*.json')):
        filename = os.path.basename(filepath)
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
        except Exception:
            print(f"Skipping malformed question file (expected dictionary, got error): {filename}")
            continue
        if not isinstance(data, dict):
            print(f"Skipping malformed question file (expected dictionary, got {type(data).__name__}): {filename}")
            continue
        found_any = True
        # Placeholder: present the question
    if not found_any:
        print(f"No {category} questions found.")
    # Prompt to quit quiz
    action = inquirer.select(
        message="Select an action:",
        choices=["Quit Quiz"]
    ).execute()
    if action == "Quit Quiz":
        return

def import_menu() -> None:
    """Display import menu to select question category for quiz session."""
    choice = inquirer.select(
        message="Import Menu:",
        choices=["File/Folder Path", "URL", "Back"],
        style=STYLE
    ).execute()
    if choice == 'Back':
        return
    # TODO: Implement import logic
    pass

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
    
    text = Text("      1. Set Gemini API Key (current: ")
    text.append(mask(gemini), style="yellow")
    text.append(f" {('('+status(gemini)+')') if gemini else ''}", style="green")
    text.append(f") (Model: {models['gemini']})")
    console.print(text)

    text = Text("      2. Set OpenAI API Key (current: ")
    text.append(mask(openai), style="yellow")
    text.append(f" {('('+status(openai,'openai')+')') if openai else ''}", style="green")
    text.append(f") (Model: {models['openai']})")
    console.print(text)

    text = Text("      3. Set OpenRouter API Key (current: ")
    text.append(mask(openrouter), style="yellow")
    text.append(f" {('('+status(openrouter)+')') if openrouter else ''}", style="green")
    text.append(f") (Model: {models['openrouter']})")
    console.print(text)

    text = Text("      4. Set Perplexity API Key (current: ")
    text.append(mask(perplexity), style="yellow")
    text.append(f" {('('+status(perplexity)+')') if perplexity else ''}", style="green")
    text.append(f") (Model: {models['perplexity']})")
    console.print(text)

    console.print()
    console.print("    --- AI Provider Selection ---", style="bold cyan")
    provider = config.get("KUBELINGO_LLM_PROVIDER", "")
    provider_disp = provider or "none"
    
    text = Text("      5. Choose AI Provider (current: ")
    text.append(provider_disp, style="yellow")
    text.append(")")
    console.print(text)

    console.print("      6. Back")
    choice = input("? Enter your choice: ").strip()
    # TODO: implement choice actions
    return

def quiz_menu() -> None:
    """Display the quiz menu and start a quiz session."""
    choice = inquirer.select(
        message="Quiz Menu:",
        choices=[
            "True/False",
            "Vocab",
            "Multiple Choice",
            "Imperative (Commands)",
            "Declarative (Manifests)",
            "Stored",
            "Back",
        ],
        style=STYLE,
    ).execute()

    if choice == "Back":
        return
    else:
        quiz_session(choice)

def main() -> None:
    """Display the main menu and dispatch to import."""
    while True:
        # Banner disabled
        # print(colorize_ascii_art(ASCII_ART))
        choice = inquirer.select(
            message="Main Menu:",
            choices=["quiz", "import", "settings", "exit"],
            style=STYLE
        ).execute()
        if choice.lower() == "exit":
            print("Goodbye!")
            sys.exit(0)
        elif choice.lower() == "import":
            import_menu()
        elif choice.lower() == "settings":
            settings_menu()
        elif choice.lower() == "quiz":
            quiz_menu()

if __name__ == "__main__":
    main()