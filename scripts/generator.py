#!/usr/bin/env python3
"""
Unified script for generating various quiz assets for Kubelingo.

This script combines the functionality of multiple individual generator scripts
into a single interface with subcommands.
"""
import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

# --- Pre-emptive sys.path setup ---
# Ensure the project root is in the Python path for kubelingo module imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Load real OpenAI package, avoiding local openai.py stub if present
# This is a precaution from one of the original scripts.
cwd = os.getcwd()
sys_path_backup = sys.path.copy()
sys.path = [p for p in sys.path if p not in ('', cwd)]
try:
    import openai
except ImportError:
    # This is a soft failure; only commands requiring openai will fail.
    openai = None
finally:
    sys.path = sys_path_backup

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    from kubelingo.utils.ui import yaml
except ImportError:
    # Fallback if pyyaml is part of a module that isn't found
    try:
        import yaml
    except ImportError:
        yaml = None


# --- Kubelingo module imports ---
try:
    from kubelingo.database import (
        add_question,
        get_db_connection,
        get_questions_by_source_file,
        init_db,
    )
    from kubelingo.modules.question_generator import AIQuestionGenerator
    from kubelingo.question import Question, ValidationStep
except ImportError as e:
    print(
        f"Warning: Failed to import some kubelingo modules. "
        f"Some features may not work. Details: {e}",
        file=sys.stderr,
    )
    # Define dummy classes/functions if modules are missing so the script can load
    Question = dict
    ValidationStep = dict
    AIQuestionGenerator = None
    get_questions_by_source_file = None
    init_db = None
    add_question = None
    get_db_connection = None


# --- from scripts/generate_from_pdf.py ---

def _get_existing_prompts_for_pdf_gen() -> List[str]:
    """Fetches all existing question prompts from the database."""
    prompts = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT prompt FROM questions")
        rows = cursor.fetchall()
        prompts = [row[0] for row in rows if row[0]]
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Found {len(prompts)} existing questions in the database.")
    return prompts


def _extract_text_from_pdf(pdf_path: str) -> str:
    """Extracts text from a PDF file."""
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}", file=sys.stderr)
        sys.exit(1)

    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        print(f"Extracted {len(text.split())} words from {pdf_path}.")
        return text
    except Exception as e:
        print(f"Error processing PDF file: {e}", file=sys.stderr)
        sys.exit(1)


def _generate_questions_from_text(
    text: str, existing_prompts: List[str], num_questions_per_chunk: int = 5
) -> List[Dict[str, Any]]:
    """Generates new questions from text using AI, avoiding existing ones."""
    from kubelingo.integrations.llm import get_llm_client
    provider = os.environ.get("AI_PROVIDER", "gemini").lower()
    try:
        llm_client = get_llm_client(provider)
    except Exception as e:
        print(f"Error initializing LLM client for provider '{provider}': {e}", file=sys.stderr)
        sys.exit(1)

    system_prompt = """You are an expert Kubernetes administrator and trainer creating quiz questions for the CKAD exam from a provided document.
Your task is to generate new questions based on the text. The questions can be about basic concepts and definitions, or about specific commands.
The questions should be unique and not overlap with the provided list of existing questions.
Output ONLY a YAML list of question objects. Each object must have 'id', 'prompt', 'answers' (a list), 'explanation', and 'source'. Use a generic source like 'Killer Shell PDF'.
The 'id' should be a unique, perhaps using a slug of the question.

Example output format for a command question:
- id: create-pod-with-image
  prompt: How do you create a pod named 'nginx' with the image 'nginx:latest'?
  answers:
    - "kubectl run nginx --image=nginx:latest"
  explanation: "The 'kubectl run' command is used to create a pod from an image."
  source: "Killer Shell PDF"

Example output format for a basic definition question:
- id: what-is-a-service
  prompt: What is the purpose of a Service in Kubernetes?
  answers:
    - "A Service in Kubernetes is an abstract way to expose an application running on a set of Pods as a network service. It provides a stable endpoint (IP address and port) for a group of pods."
  explanation: "Services enable loose coupling between microservices and provide service discovery."
  source: "Killer Shell PDF"
"""

    words = text.split()
    chunk_size = 4000  # words per chunk
    chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]

    all_generated_questions = []
    existing_prompts_set = {p.strip().lower() for p in existing_prompts}

    for i, chunk in enumerate(chunks):
        print(f"Processing chunk {i+1}/{len(chunks)}...")

        user_prompt = f"""
Here is a chunk of text from a Kubernetes document:
---
{chunk}
---

Here is a list of existing question prompts to avoid creating duplicates:
---
{existing_prompts}
---

Please generate {num_questions_per_chunk} new questions from the text chunk above. Ensure they are in the specified YAML format.
"""

        try:
            content = llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.5,
                json_mode=True # The prompt asks for YAML, but it's a JSON-compatible list of objects.
            )
            try:
                if content.strip().startswith("```yaml"):
                    content = content.strip()[7:-3].strip()
                elif content.strip().startswith("```"):
                    content = content.strip()[3:-3].strip()

                generated_questions = yaml.safe_load(content)
                if isinstance(generated_questions, list):
                    newly_added_count = 0
                    for q in generated_questions:
                        # Handle both 'prompt' and 'question' as possible keys from the AI
                        prompt_text = q.get('prompt', q.get('question', '')).strip().lower()
                        if prompt_text and prompt_text not in existing_prompts_set:
                            all_generated_questions.append(q)
                            existing_prompts_set.add(prompt_text)
                            newly_added_count += 1
                    print(f"Successfully generated and filtered {newly_added_count} new questions from chunk {i+1}.")
                else:
                    print(f"Warning: AI returned non-list data for chunk {i+1}. Skipping.", file=sys.stderr)
            except (yaml.YAMLError, TypeError) as e:
                print(f"Warning: Could not parse YAML response from AI for chunk {i+1}. Error: {e}", file=sys.stderr)
                print("AI Response was:\n" + content, file=sys.stderr)

        except openai.APIError as e:
            print(f"OpenAI API error on chunk {i+1}: {e}", file=sys.stderr)

    return all_generated_questions


def handle_from_pdf(args):
    """Handles the 'from-pdf' subcommand."""
    if not fitz:
        print("PyMuPDF not found. Please install it with 'pip install pymupdf'", file=sys.stderr)
        sys.exit(1)
    if not yaml:
        print("PyYAML not found. Please install it with 'pip install pyyaml'", file=sys.stderr)
        sys.exit(1)
    if not get_db_connection:
        print("Could not import get_db_connection. Check kubelingo installation.", file=sys.stderr)
        sys.exit(1)

    existing_prompts = _get_existing_prompts_for_pdf_gen()
    pdf_text = _extract_text_from_pdf(args.pdf_path)
    new_questions = _generate_questions_from_text(pdf_text, existing_prompts, args.num_questions_per_chunk)

    if not new_questions:
        print("No new questions were generated. Exiting.")
        return

    output_dir = os.path.dirname(args.output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    try:
        with open(args.output_file, 'w') as f:
            yaml.dump(new_questions, f, default_flow_style=False, sort_keys=False)
        print(f"\nSuccessfully saved {len(new_questions)} new questions to {args.output_file}")
        print("Please review the generated file before importing it into the database.")
    except Exception as e:
        print(f"Error writing to output file: {e}", file=sys.stderr)


# --- from scripts/generate_ai_quiz.py ---

def _load_shared_context_for_ai_quiz():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    path = os.path.join(root, 'shared_context.md')
    try:
        with open(path, encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Warning: shared_context.md not found at {path}. Using empty context.")
        return ''


def _generate_ai_quiz_questions(examples, n):
    from kubelingo.integrations.llm import get_llm_client
    provider = os.environ.get("AI_PROVIDER", "gemini").lower()
    try:
        llm_client = get_llm_client(provider)
    except Exception as e:
        print(f"Error initializing LLM client for provider '{provider}': {e}", file=sys.stderr)
        sys.exit(1)

    shared = _load_shared_context_for_ai_quiz()
    system_msg = {
        'role': 'system',
        'content': shared + "\nYou are a quiz generator for Kubernetes kubectl commands."
    }
    user_prompt = (
        f"Generate {n} quiz items as a JSON array of objects with 'question' and 'answer' fields. "
        "Each answer must be a valid kubectl command. Use the same format as the examples below.\n"
        "Examples: " + json.dumps(examples)
    )
    user_msg = {'role': 'user', 'content': user_prompt}
    
    text = llm_client.chat_completion(
        messages=[system_msg, user_msg],
        temperature=0.7,
        json_mode=True
    )
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print('Failed to parse JSON from AI response:', e)
        print('Response was:', text)
        return []


def _validate_ai_quiz_item(item):
    q = item.get('question', '').strip()
    a = item.get('answer', '').strip()
    if not q or not a:
        return False, 'Missing question or answer.'
    if not a.startswith('kubectl '):
        return False, "Answer does not start with 'kubectl '."
    # Basic resource type validation
    resource_types = [
        'pod', 'service', 'deployment', 'replicaset', 'statefulset', 'daemonset',
        'configmap', 'secret', 'job', 'cronjob', 'node', 'namespace', 'ingress',
        'persistentvolume', 'persistentvolumeclaim', 'pv', 'pvc'
    ]
    if not any(rt in q.lower() for rt in resource_types):
        return False, 'Question does not mention a Kubernetes resource type.'
    return True, ''


def handle_ai_quiz(args):
    """Handles the 'ai-quiz' subcommand."""
    examples = [
        { 'question': 'How do you list all running pods in the default namespace?',
          'answer': 'kubectl get pods --field-selector=status.phase=Running' },
        { 'question': 'How do you delete a deployment named frontend in the prod namespace?',
          'answer': 'kubectl delete deployment frontend -n prod' }
    ]
    if args.output:
        out_path = args.output
    else:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        out_dir = os.path.join(project_root, 'question-data', 'json')
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, 'ai_generated_quiz.json')

    if args.mock:
        items = [
            { 'question': 'How do you delete a pod named my-pod in the default namespace?',
              'answer': 'kubectl delete pod my-pod' },
            { 'question': 'List services in namespace prod',
              'answer': 'kubectl get svc -n prod' },
            { 'question': 'Expose deployment my-app on port 80',
              'answer': 'expose deployment my-app --port=80' },
            { 'question': 'How to get cluster version?',
              'answer': 'kubectl version' }
        ]
    else:
        items = _generate_ai_quiz_questions(examples, args.num)

    valid = []
    for idx, item in enumerate(items, start=1):
        ok, msg = _validate_ai_quiz_item(item)
        if ok:
            valid.append(item)
        else:
            print(f'Item {idx} invalid: {msg}')

    if not valid:
        print('No valid items to save.')
        sys.exit(0)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(valid, f, indent=2)
    print(f'Saved {len(valid)} valid items to {out_path}')


# --- from scripts/generate_resource_reference_quiz.py ---

def handle_resource_reference(args):
    """Generates the resource_reference.yaml quiz manifest."""
    resources = [
        ("bindings", "", "v1", True, "Binding"),
        ("componentstatuses", "cs", "v1", False, "ComponentStatus"),
        ("configmaps", "cm", "v1", True, "ConfigMap"),
        ("endpoints", "ep", "v1", True, "Endpoints"),
        ("events", "ev", "v1", True, "Event"),
        ("limitranges", "limits", "v1", True, "LimitRange"),
        ("namespaces", "ns", "v1", False, "Namespace"),
        ("nodes", "no", "v1", False, "Node"),
        ("persistentvolumeclaims", "pvc", "v1", True, "PersistentVolumeClaim"),
        ("persistentvolumes", "pv", "v1", False, "PersistentVolume"),
        ("pods", "po", "v1", True, "Pod"),
        ("podtemplates", "", "v1", True, "PodTemplate"),
        ("replicationcontrollers", "rc", "v1", True, "ReplicationController"),
        ("resourcequotas", "quota", "v1", True, "ResourceQuota"),
        ("secrets", "", "v1", True, "Secret"),
        ("serviceaccounts", "sa", "v1", True, "ServiceAccount"),
        ("services", "svc", "v1", True, "Service"),
        ("mutatingwebhookconfigurations", "", "admissionregistration.k8s.io/v1", False, "MutatingWebhookConfiguration"),
        ("validatingwebhookconfigurations", "", "admissionregistration.k8s.io/v1", False, "ValidatingWebhookConfiguration"),
        ("customresourcedefinitions", "crd,crds", "apiextensions.k8s.io/v1", False, "CustomResourceDefinition"),
        ("apiservices", "", "apiregistration.k8s.io/v1", False, "APIService"),
        ("controllerrevisions", "", "apps/v1", True, "ControllerRevision"),
        ("daemonsets", "ds", "apps/v1", True, "DaemonSet"),
        ("deployments", "deploy", "apps/v1", True, "Deployment"),
        ("replicasets", "rs", "apps/v1", True, "ReplicaSet"),
        ("statefulsets", "sts", "apps/v1", True, "StatefulSet"),
        ("tokenreviews", "", "authentication.k8s.io/v1", False, "TokenReview"),
        ("localsubjectaccessreviews", "", "authorization.k8s.io/v1", True, "LocalSubjectAccessReview"),
        ("selfsubjectaccessreviews", "", "authorization.k8s.io/v1", False, "SelfSubjectAccessReview"),
        ("selfsubjectrulesreviews", "", "authorization.k8s.io/v1", False, "SelfSubjectRulesReview"),
        ("subjectaccessreviews", "", "authorization.k8s.io/v1", False, "SubjectAccessReview"),
        ("horizontalpodautoscalers", "hpa", "autoscaling/v2", True, "HorizontalPodAutoscaler"),
        ("cronjobs", "cj", "batch/v1", True, "CronJob"),
        ("jobs", "", "batch/v1", True, "Job"),
        ("certificatesigningrequests", "csr", "certificates.k8s.io/v1", False, "CertificateSigningRequest"),
        ("leases", "", "coordination.k8s.io/v1", True, "Lease"),
        ("endpointslices", "", "discovery.k8s.io/v1", True, "EndpointSlice"),
        ("flowschemas", "", "flowcontrol.apiserver.k8s.io/v1beta2", False, "FlowSchema"),
        ("prioritylevelconfigurations", "", "flowcontrol.apiserver.k8s.io/v1beta2", False, "PriorityLevelConfiguration"),
        ("ingressclasses", "", "networking.k8s.io/v1", False, "IngressClass"),
        ("ingresses", "ing", "networking.k8s.io/v1", True, "Ingress"),
        ("networkpolicies", "netpol", "networking.k8s.io/v1", True, "NetworkPolicy"),
        ("runtimeclasses", "", "node.k8s.io/v1", False, "RuntimeClass"),
        ("poddisruptionbudgets", "pdb", "policy/v1", True, "PodDisruptionBudget"),
        ("podsecuritypolicies", "psp", "policy/v1beta1", False, "PodSecurityPolicy"),
        ("clusterrolebindings", "", "rbac.authorization.k8s.io/v1", False, "ClusterRoleBinding"),
        ("clusterroles", "", "rbac.authorization.k8s.io/v1", False, "ClusterRole"),
        ("rolebindings", "", "rbac.authorization.k8s.io/v1", True, "RoleBinding"),
        ("roles", "", "rbac.authorization.k8s.io/v1", True, "Role"),
        ("priorityclasses", "pc", "scheduling.k8s.io/v1", False, "PriorityClass"),
        ("csidrivers", "", "storage.k8s.io/v1", False, "CSIDriver"),
        ("csinodes", "", "storage.k8s.io/v1", False, "CSINode"),
        ("csistoragecapacities", "", "storage.k8s.io/v1", True, "CSIStorageCapacity"),
        ("storageclasses", "sc", "storage.k8s.io/v1", False, "StorageClass"),
        ("volumeattachments", "", "storage.k8s.io/v1", False, "VolumeAttachment"),
    ]

    out = []
    for resource, shortnames, api, ns, kind in resources:
        key = kind.lower()
        # Only include shortnames question if a shortname exists
        if shortnames:
            out.append((f"{key}::shortnames", f"What is the shortname for {kind}?", shortnames))
        out.append((f"{key}::apiversion", f"What is the API version for {kind}?", api))
        out.append((f"{key}::namespaced", f"Is {kind} a namespaced resource? (true/false)", str(ns).lower()))
        out.append((f"{key}::kind", f"What is the Kind name for the resource {kind}?", kind))

    fm = ["# Resource Reference Quiz Manifest",
          "# Tests for each resource: shortnames, API version, namespaced, kind",
          "---"]
    for qid, prompt, resp in out:
        # Only include shortnames questions when shortnames is non-empty
        if qid.endswith('::shortnames') and not resp:
            continue
        fm.append(f"- id: {qid}")
        fm.append(f"  question: \"{prompt}\"")
        fm.append("  type: command")
        fm.append("  metadata:")
        fm.append(f"    response: \"{resp}\"")
        fm.append("    category: \"Resource Reference\"")
        fm.append("    citation: \"https://kubernetes.io/docs/reference/generated/kubernetes-api/\"")
        fm.append("")

    # Use relative path to respect CWD for testing
    output_dir = Path('question-data/yaml/manifests')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'resource_reference.yaml'
    with open(output_path, 'w') as f:
        f.write("\n".join(fm))
    print(f"Generated {output_path} with {len(out)} questions.")


# --- from scripts/generate_kubectl_operations_quiz.py ---

def handle_kubectl_operations(args):
    """Generates the kubectl_operations.yaml quiz manifest."""
    ops = [
        ("alpha", "List the available commands that correspond to alpha features, which are not enabled in Kubernetes clusters by default."),
        ("annotate", "Add or update the annotations of one or more resources."),
        ("api-resources", "List the API resources that are available."),
        ("api-versions", "List the API versions that are available."),
        ("apply", "Apply or Update a resource from a file or stdin."),
        ("attach", "Attach to a running container either to view the output stream or interact with the container (stdin)."),
        ("auth", "Inspect authorization."),
        ("autoscale", "Automatically scale the set of pods that are managed by a replication controller."),
        ("certificate", "Modify certificate resources."),
        ("cluster-info", "Display endpoint information about the master and services in the cluster."),
        ("completion", "Output shell completion code for the specified shell (bash or zsh)."),
        ("config", "Modify kubeconfig files via subcommands."),
        ("convert", "Convert config files between different API versions."),
        ("cordon", "Mark a node as unschedulable."),
        ("cp", "Copy files and directories to and from containers."),
        ("create", "Create one or more resources from a file or stdin."),
        ("delete", "Delete resources either from a file, stdin, or specifying label selectors, names, or resource selectors."),
        ("describe", "Display the detailed state of one or more resources."),
        ("diff", "Diff file or stdin against live configuration."),
        ("drain", "Drain a node in preparation for maintenance."),
        ("edit", "Edit and update the definition of one or more resources on the server by using the default editor."),
        ("events", "List events."),
        ("exec", "Execute a command against a container in a pod."),
        ("explain", "Get documentation of various resources using kubectl explain."),
        ("expose", "Expose a resource (service, pod, or RC) as a new service."),
        ("get", "List one or more resources."),
        ("kustomize", "Build resources from a kustomization directory."),
        ("label", "Add or update the labels of one or more resources."),
        ("logs", "Print the logs for a container in a pod."),
        ("options", "List global command-line options for kubectl."),
        ("patch", "Update one or more fields of a resource using a patch."),
        ("plugin", "Provides utilities for interacting with kubectl plugins."),
        ("port-forward", "Forward one or more local ports to a pod."),
        ("proxy", "Run a proxy to the Kubernetes API server."),
        ("replace", "Replace a resource from a file or stdin."),
        ("rollout", "Manage the rollout of a resource like deployments, daemonsets, statefulsets."),
        ("run", "Run a specified image on the cluster."),
        ("scale", "Update the size of a resource (replica count)."),
        ("set", "Configure application resources using subcommands."),
        ("taint", "Update the taints on one or more nodes."),
        ("top", "Display resource usage of pods or nodes."),
        ("uncordon", "Mark a node as schedulable."),
        ("version", "Display the Kubernetes version running on client and server."),
        ("wait", "Wait for a specific condition on one or many resources.")
    ]
    out = ["# Kubectl Operations Quiz Manifest",
           "# Ask for operation names by description.",
           "---"]
    for op, desc in ops:
        out.append(f"- id: kubectl::{op}")
        out.append(f"  question: \"{desc}\"")
        out.append("  type: command")
        out.append("  metadata:")
        out.append(f"    response: \"{op}\"")
        out.append("    validator:")
        out.append("      type: ai")
        out.append(f"      expected: \"{op}\"")
        out.append("    category: \"Kubectl Operations\"")
        out.append("    citation: \"https://kubernetes.io/docs/reference/kubectl/#operations\"")
        out.append("")

    # Use relative path to respect CWD for testing
    output_dir = Path('question-data/yaml')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'kubectl_operations.yaml'
    with open(output_path, 'w') as f:
        f.write("\n".join(out))
    print(f"Generated {output_path} with {len(ops)} questions.")


# --- from scripts/generate_ai_questions.py ---

def handle_ai_questions(args):
    """Handles 'ai-questions' subcommand."""
    provider = os.environ.get("AI_PROVIDER", "gemini").lower()
    api_key_env = "GEMINI_API_KEY" if provider == "gemini" else "OPENAI_API_KEY"
    if api_key_env not in os.environ:
        print(f"Error: {api_key_env} environment variable not set for AI_PROVIDER='{provider}'.")
        sys.exit(1)
    if not all([AIQuestionGenerator, get_questions_by_source_file, yaml]):
        print("Missing kubelingo modules or PyYAML. Cannot generate AI questions.", file=sys.stderr)
        sys.exit(1)

    base_questions = []
    if args.example_source_file:
        print(f"Loading example questions from source file '{args.example_source_file}' in the database...")
        question_dicts = get_questions_by_source_file(args.example_source_file)

        if not question_dicts:
            print(f"Warning: No example questions found in the database for source file '{args.example_source_file}'.")
        else:
            for q_dict in question_dicts:
                try:
                    validation_steps = [
                        ValidationStep(**vs) for vs in q_dict.get('validation_steps', []) if vs
                    ]
                    if not validation_steps and q_dict.get('type') == 'command' and q_dict.get('response'):
                        validation_steps.append(ValidationStep(cmd=q_dict['response'], matcher={'exit_code': 0}))

                    categories = q_dict.get('categories')
                    if not categories:
                        category_str = q_dict.get('category')
                        categories = [category_str] if category_str else ['General']

                    base_questions.append(Question(
                        id=q_dict.get('id', ''),
                        prompt=q_dict.get('prompt', ''),
                        response=q_dict.get('response'),
                        type=q_dict.get('type', ''),
                        pre_shell_cmds=q_dict.get('pre_shell_cmds', []),
                        initial_files=q_dict.get('initial_files', {}),
                        validation_steps=validation_steps,
                        explanation=q_dict.get('explanation'),
                        categories=categories,
                        difficulty=q_dict.get('difficulty'),
                        metadata=q_dict.get('metadata', {})
                    ))
                except (TypeError, KeyError) as e:
                    print(f"Warning: Could not convert question dict from DB to Question object: {e}")
            print(f"Using {len(base_questions)} questions from the database as examples.")

    generator = AIQuestionGenerator()

    subject_for_ai = args.subject
    if not base_questions:
        print("No base questions provided as examples. Using a more detailed prompt for the AI.")
        if args.category == 'Basic':
            subject_for_ai = f"Generate {args.num_questions} questions for a 'Basic term/definition recall' quiz about the Kubernetes topic: '{args.subject}'. The questions should test fundamental concepts and definitions, suitable for a beginner."
        elif args.category == 'Command':
            subject_for_ai = f"Generate {args.num_questions} questions for a 'Command-based' quiz about the Kubernetes topic: '{args.subject}'. The questions should result in a single kubectl command as an answer."
        elif args.category == 'Manifest':
            subject_for_ai = f"Generate {args.num_questions} questions for a 'Manifest-based' quiz about the Kubernetes topic: '{args.subject}'. The questions should require creating or editing a Kubernetes YAML manifest."

    print(f"Generating {args.num_questions} questions about '{args.subject}'...")
    new_questions = generator.generate_questions(
        subject=subject_for_ai,
        num_questions=args.num_questions,
        base_questions=base_questions,
        category=args.category,
        exclude_terms=[]
    )

    if not new_questions:
        print("AI failed to generate any questions.")
        return

    print(f"Successfully generated {len(new_questions)} questions.")

    question_dicts = [asdict(q) for q in new_questions]

    for q_dict in question_dicts:
        if 'review' in q_dict:
            del q_dict['review']

    output_dir = os.path.dirname(args.output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    if os.path.exists(args.output_file):
        overwrite = input(f"File '{args.output_file}' already exists. Overwrite? (y/N): ").lower()
        if overwrite != 'y':
            print("Operation cancelled.")
            return

    with open(args.output_file, 'w', encoding='utf-8') as f:
        yaml.safe_dump(question_dicts, f, default_flow_style=False, sort_keys=False, indent=2)

    print(f"\nSuccessfully saved {len(new_questions)} questions to '{args.output_file}'.")


# --- from scripts/generate_validation_steps.py ---

def _generate_steps_for_validation(answer_yaml: str):
    try:
        obj = yaml.safe_load(answer_yaml)
    except Exception:
        return []
    kind = obj.get('kind')
    metadata = obj.get('metadata', {})
    name = metadata.get('name')
    namespace = metadata.get('namespace')
    if not kind or not name:
        return []
    steps = []
    base = kind.lower()

    def add(cmd, matcher):
        steps.append({'cmd': cmd, 'matcher': matcher})

    # metadata.name
    cmd = f"kubectl get {base} {name}"
    if namespace:
        cmd += f" -n {namespace}"
    cmd += " -o jsonpath='{.metadata.name}'"
    add(cmd, {'value': name})

    # metadata.namespace
    if namespace:
        cmd = f"kubectl get {base} {name} -n {namespace} -o jsonpath='{{.metadata.namespace}}'"
        add(cmd, {'value': namespace})

    spec = obj.get('spec', {}) or {}
    # replicas
    replicas = spec.get('replicas')
    if replicas is not None:
        cmd = f"kubectl get {base} {name}"
        if namespace:
            cmd += f" -n {namespace}"
        cmd += " -o jsonpath='{.spec.replicas}'"
        add(cmd, {'value': replicas})

    # containers: Pod vs other resources
    containers = None
    if base == 'pod':
        containers = spec.get('containers', [])
        path = '.spec.containers[0]'
    else:
        tmpl = spec.get('template', {}) or {}
        containers = tmpl.get('spec', {}).get('containers', []) or []
        path = '.spec.template.spec.containers[0]'
    if containers:
        image = containers[0].get('image')
        if image:
            cmd = f"kubectl get {base} {name}"
            if namespace:
                cmd += f" -n {namespace}"
            cmd += f" -o jsonpath='{{{path}.image}}'"
            add(cmd, {'value': image})
        resources = containers[0].get('resources', {}) or {}
        for kind_res in ('requests', 'limits'):
            part = resources.get(kind_res, {}) or {}
            for key, val in part.items():
                jsonpath = f"{{{path}.resources.{kind_res}.{key}}}"
                cmd = f"kubectl get {base} {name}"
                if namespace:
                    cmd += f" -n {namespace}"
                cmd += f" -o jsonpath='{jsonpath}'"
                add(cmd, {'value': val})
        for probe in ('readinessProbe', 'livenessProbe'):
            pr = containers[0].get(probe, {}) or {}
            exec_block = pr.get('exec') or {}
            if isinstance(exec_block, dict):
                cm = exec_block.get('command') or []
                if cm:
                    cmd = f"kubectl get {base} {name}"
                    if namespace:
                        cmd += f" -n {namespace}"
                    cmd += f" -o jsonpath='{{{path}.{probe}.exec.command}}'"
                    add(cmd, {'contains': cm[0]})
            for attr in ('initialDelaySeconds', 'periodSeconds', 'timeoutSeconds', 'failureThreshold'):
                val = pr.get(attr)
                if val is not None:
                    cmd = f"kubectl get {base} {name}"
                    if namespace:
                        cmd += f" -n {namespace}"
                    cmd += f" -o jsonpath='{{{path}.{probe}.{attr}}}'"
                    add(cmd, {'value': val})
    return steps


def _process_file_for_validation(path: Path, overwrite: bool):
    data = json.loads(path.read_text(encoding='utf-8'))
    changed = False
    for q in data:
        steps = _generate_steps_for_validation(q.get('answer', ''))
        if steps:
            q['validation_steps'] = steps
            changed = True
    if not changed:
        print(f"No validation_steps generated for {path}")
        return
    dest = path if overwrite else path.with_suffix('.validated.json')
    dest.write_text(json.dumps(data, indent=2), encoding='utf-8')
    print(f"Wrote updated questions to {dest}")


def handle_validation_steps(args):
    """Handles 'validation-steps' subcommand."""
    if not yaml:
        print("PyYAML not found. Please install it with 'pip install pyyaml'", file=sys.stderr)
        sys.exit(1)
    paths = []
    if args.in_path.is_dir():
        paths = list(args.in_path.glob('*.json'))
    else:
        paths = [args.in_path]
    for p in paths:
        _process_file_for_validation(p, args.overwrite)


# --- from scripts/generate_service_account_questions.py ---

def _generate_sa_questions_list():
    """Return a list of question dicts in unified format."""
    questions = []
    # Question 0
    ans0 = "apiVersion: v1\nkind: ServiceAccount\nmetadata:\n  name: sa-reader\n  namespace: default"
    questions.append({
        "id": "service_accounts::0", "prompt": "Create a ServiceAccount named 'sa-reader' in the 'default' namespace.",
        "type": "command", "pre_shell_cmds": [], "initial_files": {},
        "validation_steps": [{"cmd": ans0, "matcher": {"exit_code": 0}}],
        "explanation": None, "categories": ["Service Account"], "difficulty": None, "metadata": {"answer": ans0}
    })
    # Question 1
    ans1 = "apiVersion: v1\nkind: ServiceAccount\nmetadata:\n  name: sa-deployer\n  namespace: dev-namespace"
    questions.append({
        "id": "service_accounts::1", "prompt": "Create a ServiceAccount named 'sa-deployer' in the 'dev-namespace' namespace.",
        "type": "command", "pre_shell_cmds": [], "initial_files": {},
        "validation_steps": [{"cmd": ans1, "matcher": {"exit_code": 0}}],
        "explanation": None, "categories": ["Service Account"], "difficulty": None, "metadata": {"answer": ans1}
    })
    # Question 2
    ans2 = "apiVersion: v1\nkind: ServiceAccount\nmetadata:\n  name: sa-db\n  namespace: prod\nimagePullSecrets:\n- name: db-secret"
    questions.append({
        "id": "service_accounts::2", "prompt": "Create a ServiceAccount named 'sa-db' in the 'prod' namespace with imagePullSecret 'db-secret'.",
        "type": "command", "pre_shell_cmds": [], "initial_files": {},
        "validation_steps": [{"cmd": ans2, "matcher": {"exit_code": 0}}],
        "explanation": None, "categories": ["Service Account"], "difficulty": None, "metadata": {"answer": ans2}
    })
    return questions


def handle_service_account(args):
    """Handles 'service-account' subcommand."""
    questions = _generate_sa_questions_list()
    if args.num and args.num > 0:
        questions = questions[:args.num]
    json_out = json.dumps(questions, indent=2)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(json_out)
        print(f"Wrote {len(questions)} questions to {args.output}")
    else:
        print(json_out)
    if args.to_db:
        if not all([init_db, add_question]):
            print("Kubelingo DB functions not available. Cannot add to DB.", file=sys.stderr)
            sys.exit(1)
        init_db()
        added = 0
        for q in questions:
            try:
                add_question(
                    id=q['id'], prompt=q['prompt'], source_file='service_accounts',
                    response=q['metadata']['answer'], category=q.get('categories', [None])[0],
                    source='script', validation_steps=q.get('validation_steps'), validator=None
                )
                added += 1
            except Exception as e:
                print(f"Warning: could not add question '{q['id']}' to DB: {e}")
        print(f"Requested to add {len(questions)} questions; successfully added {added} to the kubelingo database.")


# --- from scripts/generate_manifests.py ---

def _process_json_file_for_manifest(fname, base_dir, json_dir, manifest_dir, solutions_dir):
    path = os.path.join(json_dir, fname)
    with open(path) as f:
        data = json.load(f)
    base = os.path.splitext(fname)[0]
    entries = []
    sol_dir = os.path.join(solutions_dir, base)
    os.makedirs(sol_dir, exist_ok=True)
    for idx, item in enumerate(data):
        qid = f"{base}::{idx}"
        question = item.get('prompt') or item.get('prompts', [{}])[0].get('prompt') or item.get('question')
        if 'prompt' in item:
            qid = f"{base}::{idx}"
            question = item['prompt']
            sol = (item.get('answer') or item.get('response') or
                   item.get('correct_yaml') or item.get('metadata', {}).get('answer') or
                   item.get('metadata', {}).get('response'))
            if not sol:
                continue
            ext = '.yaml' if sol.strip().startswith(('apiVersion', 'kind', '{', '<')) else '.sh'
            sol_path = os.path.join(sol_dir, f"{idx}{ext}")
            with open(sol_path, 'w') as sf:
                sf.write(sol.strip() + '\n')
            entries.append((qid, question, os.path.relpath(sol_path, base_dir)))
        elif 'prompts' in item:
            for jdx, sp in enumerate(item['prompts']):
                qid = f"{base}::{idx}-{jdx}"
                question = sp.get('prompt')
                sol = sp.get('correct_yaml') or sp.get('response')
                if not sol:
                    steps = sp.get('validation_steps', [])
                    sol = '\n'.join(s.get('cmd', '') for s in steps if 'cmd' in s).strip()
                if not sol:
                    continue
                ext = '.yaml' if sol.splitlines()[0].strip().startswith(('apiVersion', 'kind', '{', '<')) else '.sh'
                sol_path = os.path.join(sol_dir, f"{idx}-{jdx}{ext}")
                with open(sol_path, 'w') as sf:
                    sf.write(sol + '\n')
                entries.append((qid, question, os.path.relpath(sol_path, base_dir)))
        else:
            continue
    manifest_path = os.path.join(manifest_dir, f"{base}.yaml")
    with open(manifest_path, 'w') as mf:
        mf.write(f"# Generated from {fname}\n---\n")
        for qid, question, solfile in entries:
            mf.write(f"- id: {qid}\n  question: \"{question}\"\n  solution_file: \"{solfile}\"\n  source: \"https://kubernetes.io/docs/reference/kubectl/cheatsheet/\"\n")
    print(f"Generated {manifest_path}: {len(entries)} entries")


def handle_manifests(args):
    """Generates manifests and solutions from all JSON files."""
    # base_dir is the CWD from which the script is run. This allows testing.
    base_dir = Path.cwd()
    data_dir = base_dir / 'question-data'
    json_dir_default = data_dir / 'json'
    manifest_dir = data_dir / 'yaml' / 'manifests'
    solutions_dir = data_dir / 'yaml' / 'solutions'

    manifest_dir.mkdir(parents=True, exist_ok=True)
    solutions_dir.mkdir(parents=True, exist_ok=True)

    json_files_dir = Path(getattr(args, 'json_dir', json_dir_default))
    if not json_files_dir.is_dir():
        print(f"Error: JSON source directory not found: {json_files_dir}", file=sys.stderr)
        sys.exit(1)

    for fname in os.listdir(json_files_dir):
        if fname.endswith('.json'):
            _process_json_file_for_manifest(fname, str(base_dir), json_files_dir, manifest_dir, solutions_dir)


def main():
    """Main entrypoint for the generator script."""
    parser = argparse.ArgumentParser(
        description="Unified script for generating various quiz assets for Kubelingo.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest='command', required=True, help='Sub-command help')

    # from-pdf
    p_from_pdf = subparsers.add_parser('from-pdf', help="Generate Kubelingo quiz questions from a PDF.")
    p_from_pdf.add_argument("--pdf-path", required=True, help="Path to the PDF file.")
    p_from_pdf.add_argument("--output-file", required=True, help="Path to save the generated YAML file.")
    p_from_pdf.add_argument("--num-questions-per-chunk", type=int, default=5, help="Number of questions to generate per text chunk.")
    p_from_pdf.set_defaults(func=handle_from_pdf)

    # ai-quiz
    p_ai_quiz = subparsers.add_parser('ai-quiz', help='Generate and validate Kubernetes quizzes via OpenAI')
    p_ai_quiz.add_argument('--num', type=int, default=5, help='Number of questions to generate')
    p_ai_quiz.add_argument('--mock', action='store_true', help='Use mock data for testing validation')
    p_ai_quiz.add_argument('--output', default=None, help='Output JSON file path')
    p_ai_quiz.set_defaults(func=handle_ai_quiz)

    # resource-reference
    p_ref = subparsers.add_parser('resource-reference', help="Generate a YAML quiz for Kubernetes resource references.")
    p_ref.set_defaults(func=handle_resource_reference)

    # kubectl-operations
    p_ops = subparsers.add_parser('kubectl-operations', help="Generate the Kubectl Operations quiz manifest.")
    p_ops.set_defaults(func=handle_kubectl_operations)

    # ai-questions
    p_ai_q = subparsers.add_parser('ai-questions', help="Generate AI questions and save them to a YAML file.")
    p_ai_q.add_argument("--subject", required=True, help="Subject for the new questions (e.g., 'Kubernetes Service Accounts').")
    p_ai_q.add_argument("--category", choices=['Basic', 'Command', 'Manifest'], default='Command', help="Category of questions to generate.")
    p_ai_q.add_argument("--num-questions", type=int, default=3, help="Number of questions to generate.")
    p_ai_q.add_argument("--example-source-file", help="Filename of a quiz module to use as a source of example questions from the database.")
    p_ai_q.add_argument("--output-file", required=True, help="Path to the output YAML file.")
    p_ai_q.set_defaults(func=handle_ai_questions)

    # validation-steps
    p_val = subparsers.add_parser('validation-steps', help="Generate validation_steps for Kubernetes questions")
    p_val.add_argument('in_path', type=Path, help="JSON file or directory to process")
    p_val.add_argument('--overwrite', action='store_true', help="Overwrite original files")
    p_val.set_defaults(func=handle_validation_steps)

    # service-account
    p_sa = subparsers.add_parser('service-account', help="Generate static Kubernetes ServiceAccount questions.")
    p_sa.add_argument('--to-db', action='store_true', help='Add generated questions to the kubelingo database')
    p_sa.add_argument('-n', '--num', type=int, default=0, help='Number of questions to output (default: all)')
    p_sa.add_argument('-o', '--output', type=str, help='Write generated questions to a JSON file')
    p_sa.set_defaults(func=handle_service_account)

    # manifests
    p_man = subparsers.add_parser('manifests', help="Generates YAML quiz manifests and solution files from question-data JSON.")
    p_man.set_defaults(func=handle_manifests)

    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
