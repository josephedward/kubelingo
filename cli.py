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

def answer_question():
    """Interactive question answering and grading"""
    # Select or generate a question
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
    console.print(f"[bold cyan]Question:[/bold cyan] {q['question']}")
    console.print(f"[bold cyan]Topic:[/bold cyan] {q['topic']}, [bold cyan]Difficulty:[/bold cyan] {q['difficulty']}")
    if include_context and q.get('scenario_context'):
        console.print("[bold cyan]Scenario Context:[/bold cyan]")
        for key, val in q['scenario_context'].items():
            console.print(f"  {key}: {val}")
    console.print("[bold cyan]Success Criteria:[/bold cyan]")
    for crit in q['success_criteria']:
        console.print(f"  - {crit}")
    console.print()  # blank line
    # Prompt for answer file
    path = inquirer.text(message="Enter path to your YAML answer file:").execute()
    if not os.path.isfile(path):
        console.print(f"[bold red]Error: File '{path}' not found[/bold red]")
        console.print()
        return
    with open(path, 'r') as f:
        yaml_content = f.read()
    mg = ManifestGenerator()
    grading = mg.grade_manifest(yaml_content, q['question'])
    console.print("[bold green]Grading Results:[/bold green]")
    console.print(f"Score: {grading.get('score', 0)}/100")
    console.print(f"Grade: {grading.get('grade', 'N/A')}")
    if grading.get('summary'):
        console.print(f"Summary: {grading['summary']}")
    recs = grading.get('recommendations', [])
    if recs:
        console.print("[bold yellow]Recommendations:[/bold yellow]")
        for rec in recs:
            console.print(f"  - {rec}")
    # Optional static details
    details = grading.get('details', {})
    static_results = details.get('static_results', [])
    if static_results:
        console.print()  
        console.print("[bold cyan]Static Tool Details:[/bold cyan]")
        for res in static_results:
            status = 'PASS' if res.get('passed') else 'FAIL'
            console.print(f"  {res.get('tool')}: {status} (Score: {res.get('score')})")
            for issue in res.get('issues', []):
                console.print(f"    - {issue}")
    console.print()  # blank line

def generate_manifest():
    """Interactive manifest generator"""
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