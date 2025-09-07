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
    """Display import menu to choose between file path or URL."""
    choice = inquirer.select(
        message="Import Menu:",
        choices=["File/Folder Path", "URL", "Back"]
    ).execute()
    if choice == "Back":
        return
    if choice == "File/Folder Path":
        path = inquirer.text(message="Enter file or folder path:").execute()
        print(f"Importing questions from path: {path}")
        # TODO: handle file/folder import
    elif choice == "URL":
        url = inquirer.text(message="Enter URL to import from:").execute()
        print(f"Importing questions from URL: {url}")
        # TODO: handle URL import

def main() -> None:
    """Display the main menu and dispatch to import."""
    while True:
        # Banner disabled
        # print(colorize_ascii_art(ASCII_ART))
        choice = inquirer.select(
            message="Main Menu:",
            choices=["quiz", "import", "settings", "exit"]
        ).execute()
        if choice.lower() == "exit":
            print("Goodbye!")
            sys.exit(0)
        elif choice.lower() == "import":
            import_menu()
        else:
            # Other menu options to be implemented
            continue

if __name__ == "__main__":
    main()