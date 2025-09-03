#!/usr/bin/env python3
# CLI entrypoint for Kubelingo AI tools
import sys
from InquirerPy import inquirer
from rich.console import Console

from question_generator import QuestionGenerator, DifficultyLevel, KubernetesTopics

console = Console()

def generate_question():
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
    console.print_json(q)

def main():
    console.rule("[bold cyan]Kubelingo AI[/bold cyan]")
    while True:
        choice = inquirer.select(
            message="Select an action:",
            choices=[
                "Generate Question",
                "Exit"
            ],
            default="Generate Question"
        ).execute()
        if choice == "Generate Question":
            generate_question()
        else:
            console.print("[bold red]Goodbye![/bold red]")
            sys.exit(0)

if __name__ == "__main__":
    main()