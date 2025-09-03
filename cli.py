#!/usr/bin/env python3
# CLI entrypoint for Kubelingo AI tools
import sys
from InquirerPy import inquirer
from rich.console import Console
import os

from question_generator import QuestionGenerator, DifficultyLevel, KubernetesTopics
from k8s_manifest_generator import ManifestGenerator

console = Console()

def generate_question():
    """Interactive question generator"""
    topic = inquirer.select(
        message="Select topic:",
        choices=[t.value for t in KubernetesTopics]
    ).execute()
    difficulty = inquirer.select(
        message="Select difficulty:",
        choices=[lvl.value for lvl in DifficultyLevel]
    ).execute()
    include_context = inquirer.confirm(
        message="Include scenario context?",
        default=True
    ).execute()
    gen = QuestionGenerator()
    q = gen.generate_question(topic=topic, difficulty=difficulty, include_context=include_context)
    console.print_json(data=q)
    console.print()  # blank line for spacing

def generate_manifest():
    """Interactive manifest generator"""
def generate_manifest():
    prompt = inquirer.text(message="Enter manifest prompt:").execute()
    console.print("[bold yellow]Generating manifest...[/bold yellow]\n")
    mg = ManifestGenerator()
    # Require at least one AI API key for manifest generation
    if not any(mg.env_vars.get(k) for k in ("OPENAI_API_KEY", "GEMINI_API_KEY", "XAI_API_KEY")):
        console.print("[bold red]Error: No AI API key found. Please configure OPENAI_API_KEY, GEMINI_API_KEY, or XAI_API_KEY.[/bold red]")
        console.print()
        return
    yaml_text = mg.generate_with_openai(prompt)
    console.print(yaml_text)
    console.print()  # blank line

def main():
    """Main CLI loop"""
    console.print("[bold cyan]Kubelingo AI[/bold cyan]\n")
    while True:
        choice = inquirer.select(
            message="Select an action:",
            choices=[
                "Generate Question",
                "Answer Question",
                "Generate Manifest",
                "Exit"
            ],
            default="Generate Question"
        ).execute()
        if choice == "Generate Question":
            generate_question()
        elif choice == "Answer Question":
            answer_question()
        elif choice == "Generate Manifest":
            generate_manifest()
        else:
            console.print("[bold red]Goodbye![/bold red]")
            sys.exit(0)

if __name__ == "__main__":
    main()