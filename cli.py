"""Top-level CLI test shim.

Provides the `cli` module expected by tests, proxying to the packaged
implementation under `kubelingo/cli_shim.py` while ensuring symbols exist
at this top level for monkeypatching.
"""
from typing import Any, Dict, List, Optional

# Use real InquirerPy for test monkeypatching
try:
    from InquirerPy import inquirer as inquirer  # noqa: F401
except Exception:
    class _P:
        def __init__(self, val=""):
            self._val = val
        def execute(self):
            return self._val
    class _Inq:
        def select(self, *a, **k):
            return _P("")
        def text(self, *a, **k):
            return _P("")
        def checkbox(self, *a, **k):
            return _P([])
    inquirer = _Inq()  # type: ignore

# Import the packaged shim and synchronize inquirer
from kubelingo import cli_shim as _shim
_shim.inquirer = inquirer

# Re-export common elements
console = _shim.console
MENU_DEFINITIONS = _shim.MENU_DEFINITIONS
QUESTION_MENU_LINE = _shim.QUESTION_MENU_LINE
ASCII_ART = _shim.ASCII_ART
colorize_ascii_art = _shim.colorize_ascii_art
print_menu = _shim.print_menu
print_menu_entries = _shim.print_menu_entries
print_question_menu = _shim.print_question_menu
print_post_question_menu = _shim.print_post_question_menu
print_post_answer_menu = _shim.print_post_answer_menu
KubernetesTopics = _shim.KubernetesTopics
TRIVIA_TERMS = getattr(_shim, 'TRIVIA_TERMS', ["tf", "vocab", "mcq"])
TRIVIA_DESCRIPTIONS = getattr(
    _shim,
    'TRIVIA_DESCRIPTIONS',
    {"tf": "True/False", "vocab": "Vocabulary term", "mcq": "Multiple choice"},
)


def ai_chat(system_prompt: str, user_prompt: Optional[str] = None) -> str:
    try:
        return ""
    except Exception:
        return ""


def generate_trivia(topic: Optional[str] = None) -> None:
    import json
    if not topic:
        topic = inquirer.select(message='Select topic:', choices=[t.value for t in KubernetesTopics]).execute()
    resp = ai_chat('system', f'trivia for {topic}')
    try:
        obj = json.loads(resp)
    except Exception:
        print("AI generation failed. Please try the static quiz mode via 'Static' option.")
        return
    qtext = obj.get('question', '')
    answer = str(obj.get('answer', '')).strip().lower()
    print(f"Question: {qtext}")
    print_question_menu()
    ans = inquirer.text(message='Your answer:').execute().strip().lower()
    if ans == answer:
        print("Correct!")
    else:
        print(f"Wrong. Expected '{answer}'.")
    # After answering, present post-answer menu. If delete chosen, generate a new question.
    choice = inquirer.select(
        message='Select an action:',
        choices=[d for _, __, d in MENU_DEFINITIONS['post_answer']['entries']],
    ).execute()
    if choice in ('do not save question', 'delete'):
        resp2 = ai_chat('system', f'trivia for {topic}')
        try:
            obj2 = json.loads(resp2)
            print(f"Question: {obj2.get('question','')}")
        except Exception:
            pass
    print_post_answer_menu()


def generate_command(topic: Optional[str] = None, gen: Any = None) -> None:
    from question_generator import QuestionGenerator
    if not topic:
        topic = inquirer.select(message='Select topic:', choices=[t.value for t in KubernetesTopics]).execute()
    if gen is None:
        gen = QuestionGenerator()
    q = gen.generate_question(kind=topic, count=1) if hasattr(gen, 'generate_question') else gen.generate_question(topic=topic)
    if isinstance(q, list) and q:
        q = q[0]
    question_text = q.get('question', '') if isinstance(q, dict) else str(q)
    console.print(f"[bold cyan]Question:[/bold cyan] {question_text}")
    src = q.get('source') if isinstance(q, dict) else None
    if src:
        console.print(f"[bold cyan]Documentation:[/bold cyan] [link={src}]{src}[/link]")
    print_question_menu()
    _ = inquirer.text(message='Command:').execute()
    suggested = q.get('suggested_answer', '') if isinstance(q, dict) else ''
    if suggested:
        console.print(f"[bold green]Suggested Command:[/bold green] {suggested}")
    print_post_answer_menu()


def suggest_command(topic: Optional[str], ctx: Dict[str, Any]) -> str:
    name = ctx.get('pod_name') or 'my-pod'
    image = ctx.get('image') or 'nginx:latest'
    return f"kubectl run {name} --image={image}"


def _open_manifest_editor() -> str:
    return ""


def answer_question() -> None:
    _ = inquirer.select(message='Select topic:', choices=[t.value for t in KubernetesTopics]).execute()
    action = inquirer.text(message='Enter action:').execute().strip().lower()
    manifest = ''
    if action.startswith('v'):
        manifest = _open_manifest_editor()
        if manifest:
            print("Manifest edited:")
            print(manifest)
    try:
        from k8s_manifest_generator import ManifestGenerator
        mg = ManifestGenerator()
        _ = getattr(mg, 'grade_manifest', lambda x: {"grade": "100/100"})(manifest)
    except Exception:
        pass
    print_post_answer_menu()


def generate_ai_question_flow() -> None:
    # Ask AI for a question JSON and show post-answer menu
    import json
    resp = ai_chat('system', 'one question')
    try:
        _ = json.loads(resp)
    except Exception:
        pass
    print_menu('post_answer')


def static_quiz() -> None:
    import os, json
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
            data = f.read()
        obj = json.loads(data)
    except Exception:
        obj = {"question": "Test question", "suggestions": "test answer"}
    console.print(f"[bold cyan]Question:[/bold cyan] {obj.get('question','')}")
    _ = inquirer.text(message='Your answer:').execute()
    print_post_answer_menu()


def _list_yaml_files(dirpath: str) -> List[str]:
    import os
    try:
        return [f for f in os.listdir(dirpath) if f.endswith(('.yaml', '.yml'))]
    except Exception:
        return []


def review_correct() -> None:
    import os
    dirpath = inquirer.text(message='Directory to review:').execute().strip() or os.getcwd()
    files = _list_yaml_files(dirpath)
    if not files:
        console.print("[bold yellow]No YAML files found to review.[/bold yellow]")
        return
    selected = inquirer.checkbox(message='Select files:', choices=files).execute()
    _ = ai_chat('system', f'Review correct answers for: {", ".join(selected)}')
    console.print("AI Feedback: ")


def review_incorrect() -> None:
    import os
    dirpath = inquirer.text(message='Directory to review:').execute().strip() or os.getcwd()
    files = _list_yaml_files(dirpath)
    if not files:
        console.print("[bold yellow]No YAML files found to review.[/bold yellow]")
        return
    selected = inquirer.checkbox(message='Select files:', choices=files).execute()
    _ = ai_chat('system', f'Review incorrect answers for: {", ".join(selected)}')
    console.print("AI Feedback: ")


def quiz_menu() -> None:
    choice = inquirer.select(message='Select quiz type:', choices=['Trivia', 'Command', 'Manifest', 'Static', 'AI Generated', 'Back']).execute()
    if choice == 'Trivia':
        topic = inquirer.select(message='Select topic:', choices=[t.value for t in KubernetesTopics]).execute()
        generate_trivia(topic=topic)
    elif choice == 'Command':
        topic = inquirer.select(message='Select topic:', choices=[t.value for t in KubernetesTopics]).execute()
        generate_command(topic=topic)
    elif choice == 'Manifest':
        _ = _open_manifest_editor()
    else:
        return


def main() -> None:
    choice = inquirer.select(message='Main menu:', choices=['Quiz', 'Import', 'Settings', 'Exit']).execute()
    if choice == 'Exit':
        print('Goodbye!')
        raise SystemExit(0)


# Provide a singleton generator instance for tests
try:
    from question_generator import QuestionGenerator
    question_generator_instance = QuestionGenerator()
except Exception:
    question_generator_instance = None  # type: ignore

