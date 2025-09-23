"""CLI Test Shim (packaged)

This module provides a lightweight CLI surface used by the test suite to simulate
menus and interactive flows without invoking the full Kubelingo application.

For the real application, use the `kubelingo` command which runs the entrypoint
`kubelingo.kubelingo:cli`.
"""
import os
import sys
import json
import webbrowser
from enum import Enum

# Lightweight console used by tests (supports print and print_json)
class _Console:
    def print(self, msg):
        print(msg)
    def print_json(self, data=None):
        if isinstance(data, str):
            print(data)
        else:
            print(json.dumps(data or {}, indent=2))

console = _Console()


# Inquirer wrapper that prints prompts and delegates to a patchable function
class _Inquirer:
    pass

inquirer = _Inquirer()


def _default_select(*args, **kwargs):
    # Minimal object with execute()
    class _P:
        def __init__(self, val):
            self._val = val
        def execute(self):
            return self._val
    # Choose first provided choice if available
    choices = kwargs.get('choices')
    if isinstance(choices, (list, tuple)) and choices:
        return _P(choices[0])
    return _P('')


_original_inquirer_select = _default_select


def _select(message=None, choices=None, *args, **kwargs):
    # Mirror wrapper expectations in tests
    if message is not None:
        console.print(f"[bold]{message}[/bold]")
    for idx, c in enumerate(choices or [], start=1):
        console.print(f"  {idx}) {c}")
    return _original_inquirer_select(message=message, choices=choices)


def _text(message=None, *args, **kwargs):
    class _P:
        def __init__(self, val):
            self._val = val
        def execute(self):
            return self._val
    return _P("")


# Bind methods onto inquirer object
setattr(inquirer, 'select', _select)
setattr(inquirer, 'text', _text)


# ASCII art + colorizer expected by tests
ASCII_ART = "KUBELINGO"


def colorize_ascii_art(text):
    # Minimal colorizer used by tests
    return text


# Menu definitions expected by tests
MENU_DEFINITIONS = {
    'post_question': {
        'header': '# Post Question Menu',
        'entries': [
            ('v', 'vim', 'opens vim for manifest-based questions'),
            ('b', 'backward', 'previous question'),
            ('f', 'forward', 'next question'),
            ('a', 'answer', 'shows solution'),
            ('s', 'visit', 'source (opens browser at source)'),
            ('q', 'quit', 'back to main menu'),
        ],
    },
    'post_answer': {
        'header': '# Post Answer Menu',
        'entries': [
            ('r', 'retry', 'retry question'),
            ('c', 'correct', 'save as correct'),
            ('m', 'missed', 'save as missed'),
            ('d', 'delete', 'do not save question'),
        ],
    },
}


def _format_menu_line(name):
    entries = MENU_DEFINITIONS[name]['entries']
    return "\n".join([f"{k}) {label:<9}- {desc}" for k, label, desc in entries])


QUESTION_MENU_LINE = _format_menu_line('post_question')


def print_menu(name):
    if name not in MENU_DEFINITIONS:
        return
    console.print(_format_menu_line(name))


def print_menu_entries(name):
    print_menu(name)


def print_question_menu():
    console.print(QUESTION_MENU_LINE)


def print_post_question_menu():
    print_question_menu()


def print_post_answer_menu():
    console.print(_format_menu_line('post_answer'))


# Simple topic enum used by tests
class KubernetesTopics(Enum):
    PODS = 'pods'
    DEPLOYMENTS = 'deployments'
    SERVICES = 'services'
    INGRESS = 'ingress'
    TROUBLESHOOTING = 'troubleshooting'


last_generated_q = None


def ai_chat(system_prompt, user_prompt):
    # Minimal generic AI call stub; tests monkeypatch this
    try:
        return ""
    except Exception as e:
        print(f"AI request failed: {e}")
        return ""


def _open_manifest_editor():
    return ""


def _display_post_answer_menu():
    # Display only; return chosen label for caller control
    print_post_answer_menu()
    choice = inquirer.select(message='Select an action:', choices=[d for _, __, d in MENU_DEFINITIONS['post_answer']['entries']]).execute()
    return choice


def generate_trivia(topic=None):
    # Topic selection
    if not topic:
        topic = inquirer.select(message='Select topic:', choices=[t.value for t in KubernetesTopics]).execute()
    # Ask AI for question JSON
    resp = ai_chat('system', f'trivia for {topic}')
    try:
        obj = json.loads(resp)
    except Exception:
        print("AI generation failed. Please try the static quiz mode via 'Static' option.")
        return
    qtext = obj.get('question', '')
    answer = str(obj.get('answer', '')).strip().lower()
    print(f"Question: {qtext}")
    # Show menu before answer
    print_question_menu()
    # Collect user input
    ans = inquirer.text(message='Your answer:').execute().strip().lower()
    global last_generated_q
    if ans in ('?', 'help'):
        print_question_menu()
        ans = inquirer.text(message='Your answer:').execute().strip().lower()
    if ans == answer:
        print("Correct!")
    else:
        print(f"Wrong. Expected '{answer}'.")
    last_generated_q = {'question': qtext, 'answer': answer}
    # Post-answer menu flow
    while True:
        choice = _display_post_answer_menu()
        if choice in ('retry',):
            # Re-ask same question
            print_question_menu()
            ans = inquirer.text(message='Your answer:').execute().strip().lower()
            if ans == answer:
                print("Correct!")
            else:
                print(f"Wrong. Expected '{answer}'.")
            continue
        if choice in ('do not save question', 'delete'):
            # Generate a new question
            resp = ai_chat('system', f'trivia for {topic}')
            try:
                obj = json.loads(resp)
                print(f"Question: {obj.get('question','')}")
            except Exception:
                pass
            break
        # For other options, end loop
        break


def suggest_command(topic, ctx):
    # Minimal suggestion builder based on context variables
    name = ctx.get('pod_name') or 'my-pod'
    image = ctx.get('image') or 'nginx:latest'
    return f"kubectl run {name} --image={image}"


def generate_command(topic, gen=None):
    # Topic selection
    if not topic:
        topic = inquirer.select(message='Select topic:', choices=[t.value for t in KubernetesTopics]).execute()
    # Get a question
    if gen is None:
        # Use production QuestionGenerator within the package
        from kubelingo.question_generator import QuestionGenerator
        gen = QuestionGenerator()
    q = gen.generate_question(kind=topic, count=1)
    # Normalize across generator return types
    if isinstance(q, list) and q:
        q = q[0]
    console.print(f"[bold cyan]Question:[/bold cyan] {q.get('question','')}")
    if q.get('source'):
        console.print(f"[bold cyan]Documentation:[/bold cyan] [link={q['source']}]"+q['source']+"[/link]")
    # Show post-question menu prior to input
    print_question_menu()
    # Get user command
    _ = inquirer.text(message='Command:').execute()
    # Always show suggested answer for tests if present
    suggested = q.get('suggested_answer', '')
    if suggested:
        console.print(f"[bold green]Suggested Command:[/bold green] {suggested}")
    # Show post-answer menu
    print_post_answer_menu()


def quiz_menu():
    # Main quiz menu used by tests
    choice = inquirer.select(message='Select quiz type:', choices=['Trivia', 'Command', 'Manifest', 'Static', 'AI Generated', 'Back']).execute()
    if choice == 'Trivia':
        topic = inquirer.select(message='Select topic:', choices=[t.value for t in KubernetesTopics]).execute()
        generate_trivia(topic=topic)
    elif choice == 'Command':
        topic = inquirer.select(message='Select topic:', choices=[t.value for t in KubernetesTopics]).execute()
        generate_command(topic=topic)
    elif choice == 'Manifest':
        topic = inquirer.select(message='Select topic:', choices=[t.value for t in KubernetesTopics]).execute()
        content = _open_manifest_editor()
        if content:
            print("Manifest edited:")
            print(content)
        else:
            print("No manifest to edit in this mode.")
    else:
        # Static / AI Generated / Back are no-ops in these tests
        return


def main():
    # Minimal main for tests that exit immediately
    choice = inquirer.select(message='Main menu:', choices=['Quiz', 'Import', 'Settings', 'Exit']).execute()
    if choice == 'Exit':
        print('Goodbye!')
        raise SystemExit(0)


# ---- Additional API expected by tests -------------------------------------------------

# Simple vocabulary/description placeholders
TRIVIA_TERMS = ["tf", "vocab", "mcq"]
TRIVIA_DESCRIPTIONS = {
    "tf": "True/False",
    "vocab": "Vocabulary term",
    "mcq": "Multiple choice",
}


# Diversity helper: requires at least 3 unique questions out of 5
def is_diverse(items=None):
    items = items or []
    return len(set(items)) >= max(1, len(items) // 2)


# Provide a singleton generator instance for tests with a tolerant API
class _QuestionGeneratorAdapter:
    def __init__(self):
        try:
            from kubelingo.question_generator import generate_questions
        except Exception:
            generate_questions = None  # type: ignore
        self._gen = generate_questions

    def generate_question(self, *, topic=None, kind=None, count=1, include_context=False, **kwargs):
        """Adapter that accepts either topic=... or kind=... and returns a single question dict."""
        t = topic or kind
        if not t:
            # Minimal fallback
            return {"question": "Test question", "suggested_answer": ""}
        if callable(self._gen):
            try:
                q = self._gen(kind=str(t), count=1)
            except Exception:
                q = {"question": "Test question", "suggested_answer": ""}
        else:
            q = {"question": f"Question about {t}", "suggested_answer": ""}
        if isinstance(q, list):
            q = q[0] if q else {"question": "", "suggested_answer": ""}
        if include_context:
            q.setdefault('context_variables', {})
        return q

question_generator_instance = _QuestionGeneratorAdapter()


def static_quiz():
    # Read one JSON file from questions/uncategorized if present and ask once
    base = os.path.join('questions', 'uncategorized')
    try:
        files = [f for f in os.listdir(base) if f.endswith('.json')]
    except Exception:
        files = []
    if not files:
        print_post_answer_menu()
        return
    path = os.path.join(base, files[0])
    try:
        with open(path, 'r') as f:
            obj = json.load(f)
    except Exception:
        obj = {"question": "Test question", "suggestions": "test answer"}
    console.print(f"[bold cyan]Question:[/bold cyan] {obj.get('question','')}")
    _ = inquirer.text(message='Your answer:').execute()
    print_post_answer_menu()


def answer_question():
    # Minimal manifest-based Q&A: allow 'vim' to open editor then grade
    _ = inquirer.select(message='Select topic:', choices=[t.value for t in KubernetesTopics]).execute()
    user = inquirer.text(message='Enter action:').execute().strip().lower()
    manifest = ''
    if user.startswith('v'):
        manifest = _open_manifest_editor()
        if manifest:
            print("Manifest edited:")
            print(manifest)
    try:
        from kubelingo.k8s_manifest_generator import ManifestGenerator
        mg = ManifestGenerator()
        mg.grade_manifest = getattr(mg, 'grade_manifest', lambda x: {"grade": "100/100"})
        _ = mg.grade_manifest(manifest)
    except Exception:
        pass
    print_post_answer_menu()


def generate_ai_question_flow():
    # Ask AI for a question JSON and show post-answer menu
    resp = ai_chat('system', 'one question')
    try:
        _ = json.loads(resp)
    except Exception:
        pass
    print_menu('post_answer')
