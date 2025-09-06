import sys
import os
import json
import glob
import shutil
import webbrowser
import subprocess
import tempfile
import time
import getpass

from InquirerPy import inquirer
from rich.console import Console
from rich.syntax import Syntax
from dotenv import dotenv_values

from question_generator import QuestionGenerator, KubernetesTopics
from k8s_manifest_generator import ManifestGenerator
import requests
import yaml
import uuid




console = Console()

TRIVIA_DESCRIPTIONS = {
    KubernetesTopics.PODS.value: "A basic unit of deployment in Kubernetes, representing a single instance of a running process in your cluster.",
    KubernetesTopics.DEPLOYMENTS.value: "Manages a replicated application, ensuring that a specified number of Pod replicas are running at all times.",
    KubernetesTopics.SERVICES.value: "An abstract way to expose an application running on a set of Pods as a network service.",
    KubernetesTopics.VOLUMES.value: "A directory, possibly with some data in it, which is accessible to the Containers in a Pod.",
    KubernetesTopics.CONFIGMAPS.value: "Used to store non-confidential data in key-value pairs.",
    KubernetesTopics.SECRETS.value: "Used to store sensitive information, such as passwords, OAuth tokens, and ssh keys.",
    KubernetesTopics.INGRESS.value: "An API object that manages external access to the services in a cluster, typically HTTP.",
    KubernetesTopics.RBAC.value: "A method of regulating access to computer or network resources based on the roles of individual users within your organization.",
    KubernetesTopics.NETWORKING.value: "The way Pods communicate with each other and with external services.",
    KubernetesTopics.MONITORING.value: "The process of collecting and analyzing data about the performance and health of your Kubernetes cluster and applications.",
    KubernetesTopics.SECURITY.value: "Practices and configurations to protect your Kubernetes cluster and applications from unauthorized access and attacks.",
    KubernetesTopics.TROUBLESHOOTING.value: "The process of identifying and resolving issues within your Kubernetes cluster or applications."
}

TRIVIA_TERMS = {
    KubernetesTopics.PODS.value: "Pod",
    KubernetesTopics.DEPLOYMENTS.value: "Deployment",
    KubernetesTopics.SERVICES.value: "Service",
    KubernetesTopics.VOLUMES.value: "Volume",
    KubernetesTopics.CONFIGMAPS.value: "ConfigMap",
    KubernetesTopics.SECRETS.value: "Secret",
    KubernetesTopics.INGRESS.value: "Ingress",
    KubernetesTopics.RBAC.value: "RBAC",
    KubernetesTopics.NETWORKING.value: "Networking",
    KubernetesTopics.MONITORING.value: "Monitoring",
    KubernetesTopics.SECURITY.value: "Security",
    KubernetesTopics.TROUBLESHOOTING.value: "Troubleshooting"
}

# Holds the most recently generated question for optional import
last_generated_q = None

# Holds the most recently generated question for optional import
last_generated_q = None

def _build_manifest(topic: str, vars: dict, question: str = None) -> str:
    """Build a suggested Kubernetes manifest based on topic, context variables, or via AI fallback."""
    # Helper values
    pod_name = vars.get('pod_name', 'demo-pod')
    image = vars.get('image', 'nginx:latest')
    port = vars.get('port')
    cpu = vars.get('cpu_limit')
    mem = vars.get('memory_limit')
    env_var = vars.get('env_var')
    env_val = vars.get('env_value')
    sidecar = vars.get('sidecar_image')
    dep_name = vars.get('deployment_name')
    replicas = vars.get('replicas')
    svc_dep = vars.get('deployment_name')
    svc_name = f"svc-{svc_dep}" if svc_dep else None
    # Build per-topic manifests
    if topic == KubernetesTopics.PODS.value:
        lines = [
            'apiVersion: v1',
            'kind: Pod',
            'metadata:',
            f'  name: {pod_name}',
            'spec:',
            '  containers:',
            '  - name: main',
            f'    image: {image}',
        ]
        if port:
            lines += ['    ports:', f'    - containerPort: {port}']
        if cpu and mem:
            lines += [
                '    resources:',
                '      limits:',
                f'        cpu: {cpu}',
                f'        memory: {mem}',
            ]
        if env_var and env_val:
            lines += [
                '    env:',
                f'    - name: {env_var}',
                f'      value: {env_val}',
            ]
        if sidecar:
            lines += [
                '  - name: sidecar',
                f'    image: {sidecar}',
            ]
        return '\n'.join(lines) + '\n'
    elif topic == KubernetesTopics.DEPLOYMENTS.value:
        # Deployment manifests
        lines = [
            'apiVersion: apps/v1',
            'kind: Deployment',
            'metadata:',
            f'  name: {dep_name}',
            'spec:',
            f'  replicas: {replicas}',
            '  selector:',
            '    matchLabels:',
            f'      app: {dep_name}',
            '  template:',
            '    metadata:',
            '      labels:',
            f'        app: {dep_name}',
            '    spec:',
            '      containers:',
            '      - name: main',
            f'        image: {image}',
        ]
        if env_var and env_val:
            lines += [
                '        env:',
                f'        - name: {env_var}',
                f'          value: {env_val}',
            ]
        if cpu and mem:
            lines += [
                '        resources:',
                '          limits:',
                f'            cpu: {cpu}',
                f'            memory: {mem}',
            ]
        if port:
            lines += [
                '        readinessProbe:',
                '          httpGet:',
                '            path: /',
                f'            port: {port}',
            ]
        return '\n'.join(lines) + '\n'
    elif topic == KubernetesTopics.SERVICES.value:
        # Service manifests
        svc_type = 'ClusterIP'
        if difficulty == DifficultyLevel.INTERMEDIATE.value:
            svc_type = 'NodePort'
        elif difficulty == DifficultyLevel.ADVANCED.value:
            svc_type = 'LoadBalancer'
        lines = [
            'apiVersion: v1',
            'kind: Service',
            'metadata:',
            f'  name: {svc_name}',
            'spec:',
            f'  type: {svc_type}',
            '  selector:',
            f'    app: {svc_dep}',
            '  ports:',
        ]
        if port is not None:
            lines += [
                f'  - port: {port}',
                f'    targetPort: {port}',
            ]
        return '\n'.join(lines) + '\n'
    elif topic == KubernetesTopics.VOLUMES.value:
        # Fallback to original volumes manifest for all difficulties
        pv_name = vars.get('pv_name', 'demo-pv')
        pvc_name = vars.get('pvc_name', 'demo-pvc')
        storage_capacity = vars.get('storage_capacity', '1Gi')
        access_mode = vars.get('access_mode', 'ReadWriteOnce')
        mount_path = vars.get('mount_path', '/data')
        # Separate YAML documents for PV, PVC, and Pod
        pv_manifest = [
            'apiVersion: v1',
            'kind: PersistentVolume',
            'metadata:',
            f'  name: {pv_name}',
            'spec:',
            '  capacity:',
            f'    storage: {storage_capacity}',
            f'  accessModes: ["{access_mode}"]',
        ]
        pvc_manifest = [
            'apiVersion: v1',
            'kind: PersistentVolumeClaim',
            'metadata:',
            f'  name: {pvc_name}',
            'spec:',
            f'  accessModes: ["{access_mode}"]',
            '  resources:',
            '    requests:',
            f'      storage: {storage_capacity}',
        ]
        pod_manifest = [
            'apiVersion: v1',
            'kind: Pod',
            'metadata:',
            f'  name: pod-{pvc_name}',
            'spec:',
            '  containers:',
            '  - name: main',
            '    image: nginx:latest',
            '    volumeMounts:',
            f'    - mountPath: {mount_path}',
            f'      name: {pvc_name}',
            '  volumes:',
            f'  - name: {pvc_name}',
            '    persistentVolumeClaim:',
            f'      claimName: {pvc_name}',
        ]
        # Join them with '---' separator
        return '\n---\n'.join([
            '\n'.join(pv_manifest),
            '\n'.join(pvc_manifest),
            '\n'.join(pod_manifest)
        ]) + '\n'
    # Fallback to AI-based generation if a question prompt is provided
    if question:
        try:
            from k8s_manifest_generator import ManifestGenerator
            mg = ManifestGenerator()
            prompt = (
                f"Generate a {difficulty} Kubernetes {topic} manifest for the following requirement:\n{question}"
            )
            return mg.generate_with_openai(prompt)
        except Exception:
            return ''
    return ''


def _display_post_answer_menu():
    """
    Displays the Post Answer menu and handles user choices.
    Returns True if 'again' is chosen, False if 'quit' is chosen, None otherwise.
    """
    while True:
        console.print("\n[bold]# Post Answer Menu[/bold]\n  again   - try again\n  correct - mark as correct\n  missed  - mark as missed\n  remove  - remove question\n")
        answer_action = inquirer.text(message="> ").execute().strip().lower()
        if answer_action == 'again':
            return True
        elif answer_action == 'correct':
            console.print("[green]Marked as correct.[/green]")
            return None
        elif answer_action == 'missed':
            console.print("[yellow]Marked as missed.[/yellow]")
            return None
        elif answer_action in ('remove', 'remove question'):
            console.print("[red]Question removed.[/red]")
            return None
        else:
            console.print("[red]Unknown command. Please try again.[/red]")


def answer_question(topic: str = None):
    """Interactive question answering and grading"""
    if topic is None:
        topic = inquirer.select(
            message="Select topic:",
            choices=[t.value for t in KubernetesTopics]
        ).execute()
    gen = QuestionGenerator()
    q = gen.generate_question(topic=topic, include_context=True)
    console.print(f"[bold cyan]Question:[/bold cyan] {q['question']}")
    if q.get('documentation_link'):
        console.print(f"[bold cyan]Documentation:[/bold cyan] [link={q['documentation_link']}]{q['documentation_link']}[/link]")
    console.print(f"[bold cyan]Topic:[/bold cyan] {q['topic']}")
    # scenario_context and success_criteria outputs are deprecated and removed
    user_input = inquirer.text(message="? ").execute().strip()
    if user_input.lower() == 'vim':
        user_ans = _open_manifest_editor(q)
    # Open editor for your answer manifest
def _open_manifest_editor(q):
    editor = os.environ.get('EDITOR', 'vim')
    with tempfile.NamedTemporaryFile(delete=False, suffix=".yaml") as tmp:
        tmp_path = tmp.name
        header = (
            f"# Question: {q['question']}\n"
            f"# Topic: {q['topic']}\n"
            "# Write your Kubernetes YAML manifest below.\n\n"
        )
        tmp.write(header.encode('utf-8'))
    console.print(f"[bold yellow]Opening {editor} to edit your answer...[/bold yellow]")
    editor_cmd = [editor]
    if editor == 'vim':
        vimrc_path = '/Users/user/Documents/GitHub/kubelingo/.vimrc'
        if os.path.exists(vimrc_path):
            editor_cmd.extend(['-u', vimrc_path])
    editor_cmd.append(tmp_path)
    subprocess.run(editor_cmd)
    with open(tmp_path, 'r') as f:
        edited_content = f.read()
    os.remove(tmp_path) # Clean up the temporary file
    return edited_content


    with open(tmp_path, 'r') as f:
        yaml_content = f.read()
    os.unlink(tmp_path)
    mg = ManifestGenerator()
    grading = mg.grade_manifest(yaml_content, q['question'])
    console.print("[bold green]Grading Results:[/bold green]")
    console.print(f"[bold]Score:[/bold] [bold green]{grading.get('score', 0)}/100[/bold green]")
    console.print(f"[bold]Grade:[/bold] [bold green]{grading.get('grade', 'N/A')}[/bold green]")
    if grading.get('summary'):
        console.print(f"[bold]Summary:[/bold] {grading['summary']}")
    recs = grading.get('recommendations', [])
    if recs:
        console.print("[bold yellow]Recommendations:[/bold yellow]")
        for rec in recs:
            console.print(f"    - [yellow]{rec}[/yellow]")
    # Optional static details
    details = grading.get('details', {})
    static_results = details.get('static_results', [])
    if static_results:
        console.print()
        console.print("[bold cyan]Static Tool Details:[/bold cyan]")
        for res in static_results:
            status = '[bold green]PASS[/bold green]' if res.get('passed') else '[bold red]FAIL[/bold red]'
            console.print(f"  {res.get('tool')}: {status} (Score: {res.get('score')})")
            for issue in res.get('issues', []):
                console.print(f"    - [red]{issue}[/red]")
    console.print()
    
def generate_question(topic: str = None):
    """Interactive manifest question generator (alias for answer_question)"""
    return answer_question(topic)


def generate_manifest():
    """Interactive manifest generator"""
    from k8s_manifest_generator import ManifestGenerator
    prompt = inquirer.text(message="Enter manifest prompt:").execute()
    console.print("[bold yellow]Generating manifest...[/bold yellow]\n")
    mg = ManifestGenerator()
    # Require at least one AI API key for manifest generation
    if not any(mg.env_vars.get(k) for k in ("OPENAI_API_KEY", "GEMINI_API_KEY", "XAI_API_KEY")):
        console.print("[bold red]Error: No AI API key found. Please configure OPENAI_API_KEY, GEMINI_API_KEY, or XAI_API_KEY.[/bold red]")
        console.print()
        return
    yaml_text = mg.generate_with_openai(prompt)
    console.print(Syntax(yaml_text, "yaml", theme="monokai", line_numbers=True))
    console.print()  # blank line

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


def colorize_ascii_art(ascii_art_string):
    """Applies a green and cyan pattern to the ASCII art string."""
    colors = ["#00FF00", "#00FFFF"]  # Green and Cyan
    lines = ascii_art_string.splitlines()
    colored_lines = []
    for i, line in enumerate(lines):
        color = colors[i % len(colors)]
        colored_lines.append(f"[{color}]{line}[/]")
    return "\n".join(colored_lines)

def set_key(dotenv_path, key, value):
    """Sets a key-value pair in the .env file."""
    if os.path.exists(dotenv_path):
        with open(dotenv_path, "r") as f:
            lines = f.readlines()
        with open(dotenv_path, "w") as f:
            found = False
            for line in lines:
                if line.startswith(key + "="):
                    f.write(f"{key}={value}\n")
                    found = True
                else:
                    f.write(line)
            if not found:
                f.write(f"{key}={value}\n")
    else:
        with open(dotenv_path, "w") as f:
            f.write(f"{key}={value}\n")
    
def post_answer_menu(q: dict, filepath: str, idx: int, total: int) -> int:
    """Present post-answer options and move the question file accordingly."""
    topic = q.get('topic', 'uncategorized')
    action = inquirer.select(
        message="# Post Answer - choose an action",
        choices=["Again", "Correct", "Missed", "Remove Question"]
    ).execute().lower()
    if action in ('again', 'retry'):
        return idx
    target_map = {'correct': 'correct', 'missed': 'missed', 'remove question': 'triage'}
    folder = target_map.get(action)
    if folder:
        dest_dir = os.path.join('questions', folder, topic)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, os.path.basename(filepath))
        shutil.move(filepath, dest)
    return idx

def quiz_session():
    """Interactive quiz session over uncategorized JSON questions."""
    files = sorted(glob.glob(os.path.join('questions', 'uncategorized', '*.json')))
    if not files:
        console.print("[bold yellow]No uncategorized questions found.[/bold yellow]")
        return
    idx = 0
    while 0 <= idx < len(files):
        path = files[idx]
        try:
            with open(path, 'r', encoding='utf-8') as f:
                q = json.load(f)
        except json.JSONDecodeError:
            idx += 1
            continue
        # Handle list of questions: split into individual files
        if isinstance(q, list):
            console.print(f"[bold yellow]{path} contains {len(q)} questions. Splitting into individual files...")
            folder = os.path.dirname(path)
            for item in q:
                if not isinstance(item, dict):
                    continue
                qid = item.get('id') or str(uuid.uuid4())
                new_file = os.path.join(folder, f"{qid}.json")
                with open(new_file, 'w', encoding='utf-8') as nf:
                    json.dump(item, nf, indent=2, ensure_ascii=False)
                console.print(f"Saved question {qid} to {new_file}")
            os.remove(path)
            files = sorted(glob.glob(os.path.join('questions', 'uncategorized', '*.json')))
            continue
        if not isinstance(q, dict):
            console.print(f"[bold red]Skipping malformed question file (expected dictionary, got {type(q).__name__}): {path}[/bold red]")
            idx += 1
            continue
        console.print(f"[bold cyan]Question {idx+1}/{len(files)}[/bold cyan]")
        if 'description' in q:
            console.print(f"[cyan]{q['description']}[/cyan]")
        elif 'question' in q:
            console.print(f"[cyan]{q['question']}[/cyan]")
        if q.get('documentation_link'):
            console.print(f"Documentation: [link={q['documentation_link']}]{q['documentation_link']}[/link]")
        cmd = inquirer.select(
            message="# Post Question - choose action",
            choices=["Backward", "Forward", "Solution", "Visit Source", "Quit Quiz"]
        ).execute().lower()
        if cmd == 'backward':
            idx = max(0, idx - 1)
            continue
        if cmd == 'forward':
            idx = min(len(files) - 1, idx + 1)
            continue
        if cmd == 'visit source' and q.get('documentation_link'):
            webbrowser.open(q['documentation_link'])
            continue
        if cmd == 'quit quiz':
            break
        if cmd == 'solution':
            ans = q.get('suggested_answer') or q.get('expected_answer') or ''
            console.print(f"[bold green]Solution:[/bold green] {ans}")
            idx = post_answer_menu(q, path, idx, len(files))
            files = sorted(glob.glob(os.path.join('questions', 'uncategorized', '*.json')))
            continue
        # Unknown command: repeat
    console.print()

def generate_trivia(topic: str = None):
    """Generate a reverse trivia (give description, ask for term) question."""
    if topic is None:
        topic = inquirer.select(
            message="Select topic:",
            choices=[t.value for t in KubernetesTopics]
        ).execute()
    gen = QuestionGenerator()
    qid = gen._generate_question_id()
    desc = TRIVIA_DESCRIPTIONS.get(topic, f"A Kubernetes {topic}.")
    term = TRIVIA_TERMS.get(topic, topic.rstrip('s').capitalize())
    console.print(f"[bold cyan]Description:[/bold cyan] {desc}")
    # Display Post Question Menu for Trivia
    console.print("\n[bold]# Post Question Menu[/bold]")
    console.print("  vim      - opens vim for manifest-based questions")
    console.print("  backward - previous question")
    console.print("  forward  - skip to next question")
    console.print("  solution - shows solution and the post-answer menu")
    console.print("  visit    - source (opens browser at source)")
    console.print("  quit     - back to main menu")
    user_ans = inquirer.text(message="Name this Kubernetes resource:").execute()
    norm_user = user_ans.strip().lower().rstrip('s')
    norm_term = term.strip().lower().rstrip('s')
    correct = norm_user == norm_term
    # Only show feedback and metadata when answer is incorrect
    if not correct:
        feedback = f"Expected '{term}', but got '{user_ans}'."
        console.print(f"[bold red]{feedback}[/bold red]")
    # Build output JSON without redundant fields on correct answer
    out = {
        'id': qid,
        'topic': topic,
        'description': desc,
        'expected_answer': term,
        'user_answer': user_ans,
    }
    if not correct:
        out['correct'] = False
        out['feedback'] = feedback
    console.print_json(data=out)
    console.print()
    # Display Post Answer Menu for Trivia
    console.print("[bold]# Post Answer Menu[/bold]")
    console.print("  again - try again (formerly 'retry')")
    console.print("  correct")
    console.print("  missed")
    console.print("  remove question")
    return


def generate_command(topic: str = None):
    """Generate a command-line question and collect the user's command."""
    if topic is None:
        topic = inquirer.select(
            message="Select topic:",
            choices=[t.value for t in KubernetesTopics]
        ).execute()
    gen = QuestionGenerator()
    # include_context=True to access context variables for command suggestions
    q = gen.generate_question(topic=topic, include_context=True)
    vars = q.get('context_variables', {})
    # Build kubectl command suggestion based on topic
    topic_key = q['topic']
    suggested = ""
    # Pods commands
    if topic_key == KubernetesTopics.PODS.value:
        flags = []
        if vars.get('port'):
            flags.append(f"--port={vars['port']}")
        if vars.get('env_var') and vars.get('env_value'):
            flags.append(f"--env={vars['env_var']}={vars['env_value']}")
        if vars.get('cpu_limit') and vars.get('memory_limit'):
            flags.append(f"--limits=cpu={vars['cpu_limit']},memory={vars['memory_limit']}")
        if vars.get('sidecar_image'):
            flags.append(f"--sidecar-image={vars['sidecar_image']}") # Assuming a flag for sidecar
        suggested = f"kubectl run {vars['pod_name']} --image={vars['image']}" + (" " + " ".join(flags) if flags else "")
    # Deployments commands
    elif topic_key == KubernetesTopics.DEPLOYMENTS.value:
        flags = [f"--replicas={vars['replicas']}"]
        if vars.get('port'):
            flags.append(f"--port={vars['port']}")
        if vars.get('env_var') and vars.get('env_value'):
            flags.append(f"--env={vars['env_var']}={vars['env_value']}")
        if vars.get('cpu_limit') and vars.get('memory_limit'):
            flags.append(f"--limits=cpu={vars['cpu_limit']},memory={vars['memory_limit']}")
        suggested = f"kubectl create deployment {vars['deployment_name']} --image={vars['image']}" + (" " + " ".join(flags) if flags else "")
    # Services commands
    elif topic_key == KubernetesTopics.SERVICES.value:
        suggested = f"kubectl expose deployment {vars['deployment_name']} --port={vars['port']} --type=ClusterIP"
    # ConfigMaps commands
    elif topic_key == KubernetesTopics.CONFIGMAPS.value:
        suggested = f"kubectl create configmap {vars['configmap_name']} --from-literal={vars['configmap_key']}={vars['configmap_value']}"
    # Fallback for other topics
    else:
        suggested = ""
    console.print(f"[bold cyan]Question:[/bold cyan] {q['question']}")
    if q.get('documentation_link'):
        console.print(f"[bold cyan]Documentation:[/bold cyan] [link={q['documentation_link']}]{q['documentation_link']}[/link]")

    # Display Post Question Menu options
    console.print(f"[bold green]Suggested Command:[/bold green] {suggested}")
    console.print("\n[bold]# Post Question Menu[/bold]")
    console.print("  vim      - opens vim for manifest-based questions")
    console.print("  backward - previous question")
    console.print("  forward  - skip to next question")
    console.print("  solution - shows solution and the post-answer menu")
    console.print("  visit    - source (opens browser at source)")
    console.print("  quit     - back to main menu")

    user_input = inquirer.text(message="? Your command: ").execute().strip()

    # Check if user_input is a menu action
    if user_input.lower() == 'solution':
        console.print(f"[bold green]Suggested Command:[/bold green] {suggested}")
        _display_post_answer_menu()
        return # Exit after showing solution and post-answer menu
    elif user_input.lower() == 'backward':
        console.print("[yellow]No previous question available in this mode.[/yellow]")
        # Re-prompt for command/menu action
        return generate_command(topic=topic) # This will regenerate a new question, not go back. Need to fix this later if true backward navigation is desired.
    elif user_input.lower() == 'forward':
        console.print("[yellow]No next question available in this mode.[/yellow]")
        # Re-prompt for command/menu action
        return generate_command(topic=topic) # This will regenerate a new question, not go forward. Need to fix this later if true forward navigation is desired.
    elif user_input.lower() == 'visit':
        if q.get('documentation_link'):
            webbrowser.open(q['documentation_link'])
        else:
            console.print("[red]No documentation link available.[/red]")
        # Re-prompt for command/menu action
        user_input = inquirer.text(message="? Your command: ").execute().strip() # Re-prompt after visit
    elif user_input.lower() in ('quit', 'quit quiz'):
        return # Exit generate_command function

    # If not a menu action, treat as user's command
    user_ans = user_input
    console.print(f"[bold green]Suggested Command:[/bold green] {suggested}")

    # Output full schema including the user's answer
    out = {
        'id': q['id'],
        'topic': q['topic'],
        'question': q['question'],
        'documentation_link': q.get('documentation_link'),
        'suggested_answer': suggested,
        'user_answer': user_ans
    }
    # Store latest generated command-question for optional import
    global last_generated_q
    last_generated_q = out
    console.print_json(data=out)
    console.print()
    # Call the new post-answer menu
    _display_post_answer_menu()


def quiz_menu():
    """Interactive Quiz submenu"""
    quiz_type = inquirer.select(
        message="Select quiz type:",
        choices=["Trivia", "Command", "Manifest", "Back"]
    ).execute()

    if quiz_type == "Back":
        return

    # Select topic once for continuous quiz
    topic = inquirer.select(
        message="Select topic:",
        choices=[t.value for t in KubernetesTopics]
    ).execute()

    while True:
        if quiz_type == "Manifest":
            generate_question(topic=topic)
        elif quiz_type == "Trivia":
            generate_trivia(topic=topic)
        elif quiz_type == "Command":
            generate_command(topic=topic)

        # Ask if the user wants another question of the same type and topic?
        continue_quiz = inquirer.select(
            message="Generate another question of the same type and topic?",
            choices=["Yes", "No"]
        ).execute()

        if continue_quiz == "No":
            # Explicitly return to main menu to avoid any lingering prompt issues
            return
    console.print()

def ai_chat(system_or_messages, user_prompt=None) -> str:
    """Call OpenAI chat completion to get a response. Supports single or multi-message inputs."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        console.print("[bold red]Error: OPENAI_API_KEY not set in environment.[/bold red]")
        return ""
    # Build message list
    if isinstance(system_or_messages, list):
        messages = system_or_messages
    else:
        system_prompt = system_or_messages
        user_content = user_prompt or ""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": messages,
        "temperature": 0.5
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        choice = data.get("choices", [])
        if choice:
            return choice[0].get("message", {}).get("content", "")
        return ""
    except Exception as e:
        console.print(f"[bold red]AI request failed:[/bold red] {e}")
        return ""

def review_menu():
    """Review submenu"""
    while True:
        choice = inquirer.select(
            message="Select review action:",
            choices=["Correct", "Incorrect", "Back"]
        ).execute()
        if choice == "Correct":
            review_correct()
        elif choice == "Incorrect":
            review_incorrect()
        else:
            break
    console.print()

def review_correct():
    """Review 'Correct' action: interactively review files for strengths."""
    prompt_msg = "Enter directory path to review (Correct) [questions/correct]:"
    raw = inquirer.text(message=prompt_msg).execute().strip()
    dir_path = raw or os.path.join(os.getcwd(), "questions", "correct")
    if not os.path.isdir(dir_path):
        console.print(f"[bold red]Directory not found:[/bold red] {dir_path}")
        return
    files = sorted([f for f in os.listdir(dir_path) if f.lower().endswith((".yaml", ".yml"))])
    if not files:
        console.print("[bold yellow]No YAML files found to review.[/bold yellow]")
        return
    selections = inquirer.checkbox(
        message="Select question file(s) to review (Correct) (use space to toggle, press Enter without selecting to review all):",
        choices=files
    ).execute()
    # If no files explicitly selected, review all
    if not selections:
        selections = files
    data_objs = []
    for fname in selections:
        path = os.path.join(dir_path, fname)
        try:
            raw = open(path, "r", encoding="utf-8").read()
            parsed = yaml.safe_load(raw)
        except Exception as e:
            console.print(f"[bold red]Failed to load {fname}:[/bold red] {e}")
            continue
        # Use structured data if mapping, else treat as raw content only
        if isinstance(parsed, dict):
            data = parsed
            is_mapping = True
        else:
            data = {}
            is_mapping = False
        user_ans = data.get("user_answer")
        if not user_ans:
            # For list-based files, prompt for the question itself
            if not is_mapping:
                prompt = "Enter your question:"
            else:
                prompt = f"Enter your answer for {fname}:"
            user_ans = inquirer.text(message=prompt).execute().strip()
            if is_mapping:
                data["user_answer"] = user_ans
                with open(path, "w", encoding="utf-8") as f:
                    yaml.safe_dump(data, f, indent=2, ensure_ascii=False)
        data_objs.append({
            "filename": fname,
            "raw": raw,
            "question": (data.get("question") or "").strip(),
            "suggested": (data.get("suggested_answer") or "").strip(),
            "user_answer": user_ans.strip()
        })
    if not data_objs:
        return
    sys_prompt = (
        "You are a Kubernetes expert and CKAD coach. "
        "Evaluate the user's answers versus the model answers and highlight what the user did well."
    )
    parts = []
    for obj in data_objs:
        parts.append(
            f"File: {obj['filename']}\n"
            f"Content:\n{obj['raw']}\n"
            f"Question: {obj['question']}\n"
            f"Model Answer: {obj['suggested']}\n"
            f"User Answer: {obj['user_answer']}"
        )
    user_prompt = "\n\n".join(parts)
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt}
    ]
    while True:
        resp = ai_chat(messages)
        console.print(f"\n[bold green]AI Feedback:[/bold green]\n{resp}")
        follow = inquirer.text(message="Follow-up (blank to continue):").execute().strip()
        if not follow:
            break
        messages.append({"role": "assistant", "content": resp})
        messages.append({"role": "user", "content": follow})

def review_incorrect():
    """Review 'Incorrect' action: interactively review files for weaknesses."""
    prompt_msg = "Enter directory path to review (Incorrect) [questions/incorrect]:"
    raw = inquirer.text(message=prompt_msg).execute().strip()
    dir_path = raw or os.path.join(os.getcwd(), "questions", "incorrect")
    if not os.path.isdir(dir_path):
        console.print(f"[bold red]Directory not found:[/bold red] {dir_path}")
        return
    files = sorted([f for f in os.listdir(dir_path) if f.lower().endswith((".yaml", ".yml"))])
    if not files:
        console.print("[bold yellow]No YAML files found to review.[/bold yellow]")
        return
    selections = inquirer.checkbox(
        message="Select question file(s) to review (Incorrect) (use space to toggle, press Enter without selecting to review all):",
        choices=files
    ).execute()
    # If no files explicitly selected, review all
    if not selections:
        selections = files
    data_objs = []
    for fname in selections:
        path = os.path.join(dir_path, fname)
        try:
            raw = open(path, "r", encoding="utf-8").read()
            parsed = yaml.safe_load(raw)
        except Exception as e:
            console.print(f"[bold red]Failed to load {fname}:[/bold red] {e}")
            continue
        if isinstance(parsed, dict):
            data = parsed
            is_mapping = True
        else:
            data = {}
            is_mapping = False
        user_ans = data.get("user_answer")
        if not user_ans:
            # For list-based files, prompt for the question itself
            if not is_mapping:
                prompt = "Enter your question:"
            else:
                prompt = f"Enter your answer for {fname}:"
            user_ans = inquirer.text(message=prompt).execute().strip()
            if is_mapping:
                data["user_answer"] = user_ans
                with open(path, "w", encoding="utf-8") as f:
                    yaml.safe_dump(data, f, indent=2, ensure_ascii=False)
        data_objs.append({
            "filename": fname,
            "raw": raw,
            "question": (data.get("question") or "").strip(),
            "suggested": (data.get("suggested_answer") or "").strip(),
            "user_answer": user_ans.strip()
        })
    if not data_objs:
        return
    sys_prompt = (
        "You are a Kubernetes expert and CKAD coach. "
        "Evaluate the user's answers versus the model answers and highlight where the user needs improvement."
    )
    parts = []
    for obj in data_objs:
        parts.append(
            f"File: {obj['filename']}\n"
            f"Content:\n{obj['raw']}\n"
            f"Question: {obj['question']}\n"
            f"Model Answer: {obj['suggested']}\n"
            f"User Answer: {obj['user_answer']}"
        )
    user_prompt = "\n\n".join(parts)
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt}
    ]
    while True:
        resp = ai_chat(messages)
        console.print(f"\n[bold red]AI Feedback:[/bold red]\n{resp}")
        follow = inquirer.text(message="Follow-up (blank to continue):").execute().strip()
        if not follow:
            break
        messages.append({"role": "assistant", "content": resp})
        messages.append({"role": "user", "content": follow})

def import_menu():
    """Import submenu"""
    while True:
        choice = inquirer.select(
            message="Select import action:",
            choices=["Uncategorized", "From URL", "From File Path", "Back"]
        ).execute()
        if choice == "Uncategorized":
            import_uncategorized()
        elif choice == "From URL":
            import_from_url()
        elif choice == "From File Path":
            import_from_file()
        else:
            break
    console.print()

def import_uncategorized():
    """Handle uncategorized imports: either save the last-generated question or start a quiz session."""
    global last_generated_q
    # If there's a recently generated question, offer to save it
    if last_generated_q:
        console.print_json(data=last_generated_q)
        save = inquirer.select(
            message="Save this question to uncategorized?",
            choices=["Yes", "No"]
        ).execute()
        if save == "Yes":
            path = os.path.join('questions', 'uncategorized', f"{last_generated_q['id']}.json")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(last_generated_q, f, indent=2, ensure_ascii=False)
            console.print(f"[green]Question saved to {path}[/green]")
        else:
            console.print("[yellow]Question discarded.[/yellow]")
        last_generated_q = None
        console.print()
    # Start a quiz over existing uncategorized questions
    quiz_session()
    console.print()

def import_from_url():
    """Generate a Kubernetes question using AI based on content at a URL."""
    global last_generated_q
    url = inquirer.text(message="Enter the URL to fetch content from:").execute().strip()
    if not url:
        console.print("[yellow]No URL provided.[/yellow]")
        console.print()
        return
    if not (url.startswith("http://") or url.startswith("https://")):
        console.print(f"[bold red]Invalid URL: {url}[/bold red]")
        console.print()
        return
    console.print("[bold yellow]Fetching content...[/bold yellow]")
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        raw = resp.text
    except Exception as e:
        console.print(f"[bold red]Failed to fetch URL: {e}[/bold red]")
        console.print()
        return
    sys_prompt = (
        "You are a Kubernetes expert. Based on the following file content, generate a Kubernetes question and a model answer. "
        "Provide the output as JSON with keys: id, topic, difficulty, question, suggested_answer."
    )
    console.print("[bold yellow]Generating question from URL content...[/bold yellow]")
    ai_resp = ai_chat(sys_prompt, raw)
    console.print()
    try:
        q = json.loads(ai_resp)
        if 'id' not in q:
            q['id'] = url
        console.print_json(data=q)
        last_generated_q = q
    except Exception:
        console.print(f"[bold cyan]Generated response:[/bold cyan]\n{ai_resp}")
        last_generated_q = {"question": ai_resp, "raw": raw, "id": url}
    console.print()

def import_from_file():
    """Generate a Kubernetes question using AI based on a local file's content."""
    global last_generated_q
    file_path = inquirer.filepath(message="Enter path to the file to use as context:").execute().strip()
    if not file_path:
        console.print("[yellow]No file path provided.[/yellow]")
        console.print()
        return
    if not os.path.isfile(file_path):
        console.print(f"[bold red]File not found: {file_path}[/bold red]")
        console.print()
        return
    try:
        raw = open(file_path, "r", encoding="utf-8").read()
    except Exception as e:
        console.print(f"[bold red]Failed to read file: {e}[/bold red]")
        console.print()
        return
    sys_prompt = (
        "You are a Kubernetes expert. "
        "Based on the following file content, generate a Kubernetes question and a model answer. "
        "Provide the output as JSON with keys: id, topic, difficulty, question, suggested_answer."
    )
    console.print("[bold yellow]Generating question from file...[/bold yellow]")
    resp = ai_chat(sys_prompt, raw)
    console.print()
    try:
        q = json.loads(resp)
        # Ensure an id for saving
        if 'id' not in q:
            q['id'] = os.path.splitext(os.path.basename(file_path))[0]
        console.print_json(data=q)
        last_generated_q = q
    except Exception:
        console.print(f"[bold cyan]Generated response:[/bold cyan]\n{resp}")
        last_generated_q = {"question": resp, "raw": raw, "id": os.path.splitext(os.path.basename(file_path))[0]}
    console.print()

def subject_matter_menu(message="Select subject matter:"):
    """Select subject matter submenu"""
    choice = inquirer.select(
        message=message,
        choices=[t.value for t in KubernetesTopics] + ["Back"]
    ).execute()
    if choice == "Back":
        return None
    return choice


def test_api_keys():
    """Tests the validity of API keys for different providers."""
    statuses = {"gemini": False, "openai": False, "openrouter": False}

    # Test Gemini
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        # This is a placeholder for actual validation logic
        statuses["gemini"] = len(gemini_key) > 10

    # Test OpenAI
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        statuses["openai"] = openai_key.startswith("sk-")

    # Test OpenRouter
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    if openrouter_key:
        statuses["openrouter"] = len(openrouter_key) > 10

    return statuses


def handle_keys_menu():
    """Handles the API key configuration menu."""
    while True:
        statuses = test_api_keys()
        if not any(statuses.values()):
            console.print("[bold red]Warning: No valid API keys found. Without a valid API key, you will just be string matching against a single suggested answer.")

        console.print("\n[bold cyan]--- API Key Configuration ---[/bold cyan]")
        # Load existing config to display current state
        config = dotenv_values(".env")
        gemini_key = config.get("GEMINI_API_KEY", "Not Set")
        openai_key = config.get("OPENAI_API_KEY", "Not Set")
        openrouter_key = config.get("OPENROUTER_API_KEY", "Not Set")

        statuses = test_api_keys()
        gemini_display = (
            f"[green]****{gemini_key[-4:]} (Valid)[/green]"
            if statuses["gemini"]
            else f"[red]****{gemini_key[-4:]} (Invalid)[/red]"
        )
        openai_display = (
            f"[green]****{openai_key[-4:]} (Valid)[/green]"
            if statuses["openai"]
            else f"[red]****{openai_key[-4:]} (Invalid)[/red]"
        )
        openrouter_display = (
            f"[green]****{openrouter_key[-4:]} (Valid)[/green]"
            if statuses["openrouter"]
            else f"[red]****{openrouter_key[-4:]} (Invalid)[/red]"
        )

        console.print(f"  [bold]1.[/bold] Set Gemini API Key (current: {gemini_display}) (Model: gemini-1.5-flash-latest)")
        console.print(f"  [bold]2.[/bold] Set OpenAI API Key (current: {openai_display}) (Model: gpt-3.5-turbo)")
        console.print(f"  [bold]3.[/bold] Set OpenRouter API Key (current: {openrouter_display}) (Model: deepseek/deepseek-r1-0528:free)")

        # AI Provider selection
        provider = config.get("KUBELINGO_LLM_PROVIDER", "")
        provider_display = f"[green]{provider}[/green]" if provider else f"[red]None[/red]"

        console.print("\n[bold cyan]--- AI Provider Selection ---[/bold cyan]")
        console.print(f"  [bold]4.[/bold] Choose AI Provider (current: {provider_display})")
        console.print(f"  [bold]5.[/bold] Back")

        choice = inquirer.text(message="Enter your choice:").execute()

        if choice == '1':
            key = getpass.getpass("Enter your Gemini API Key: ").strip()
            if key:
                set_key(".env", "GEMINI_API_KEY", key)
                os.environ["GEMINI_API_KEY"] = key
                console.print("\n[green]Gemini API Key saved.[/green]")
                if not test_api_keys().get("gemini"):
                    console.print("[bold red]Invalid Gemini API Key. Please check your key.[/bold red]")
            else:
                console.print("\n[yellow]No key entered.[/yellow]")
            time.sleep(1)

        elif choice == '2':
            key = inquirer.text(message="Enter your OpenAI API Key:").execute()
            if key:
                set_key(".env", "OPENAI_API_KEY", key)
                os.environ["OPENAI_API_KEY"] = key
                console.print("\n[green]OpenAI API Key saved.[/green]")
                if not test_api_keys().get("openai"):
                    console.print("[bold red]Invalid OpenAI API Key. Please check your key.[/bold red]")
            else:
                console.print("\n[yellow]No key entered.[/yellow]")
            time.sleep(1)

        elif choice == '3':
            key = inquirer.text(message="Enter your OpenRouter API Key:").execute()
            if key:
                set_key(".env", "OPENROUTER_API_KEY", key)
                os.environ["OPENROUTER_API_KEY"] = key
                console.print("\n[green]OpenRouter API Key saved.[/green]")
                if not test_api_keys().get("openrouter"):
                    console.print("[bold red]Invalid OpenRouter API Key. Please check your key.[/bold red]")
            else:
                console.print("\n[yellow]No key entered.[/yellow]")
            time.sleep(1)

        elif choice == '4':
            provider_choice = inquirer.select(
                message="Select AI Provider:",
                choices=["openrouter", "gemini", "openai", "none (disable AI)"]
            ).execute()
            sel = provider_choice if provider_choice != "none (disable AI)" else ""
            set_key(".env", "KUBELINGO_LLM_PROVIDER", sel)
            os.environ["KUBELINGO_LLM_PROVIDER"] = sel
            console.print(f"\n[green]AI Provider set to {sel or 'none'}.[/green]")
            time.sleep(1)

        elif choice == '5':
            return

        else:
            console.print("[bold red]Invalid choice. Please try again.[/bold red]")
            time.sleep(1)


def _cli_entrypoint():
    """Internal entrypoint for CLI commands and interactive mode."""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "generate-question":
            generate_question()
        elif command == "answer-question":
            answer_question()
        elif command == "generate-manifest":
            generate_manifest()
        else:
            console.print(f"[bold red]Unknown command: {command}[/bold red]")
            sys.exit(1)
    else:
        # Interactive mode
        while True:
            choice = inquirer.select(
                message="Select an action:",
                choices=[
                    "Quiz",
                    "Review",
                    "Import",
                    "Settings",
                    "Exit"
                ],
                default="Quiz"
            ).execute()
            choice = choice.lower()
            if choice == "settings":
                handle_keys_menu()
            elif choice == "import":
                import_menu()
            elif choice == "review":
                review_menu()
            elif choice == "quiz":
                quiz_menu()
            else:
                console.print("[bold red]Goodbye![/bold red]")
                sys.exit(0)

def main():
    """Main CLI entrypoint for external calls and tests."""
    console.print(colorize_ascii_art(ASCII_ART))
    _cli_entrypoint()


if __name__ == "__main__":
    main()
