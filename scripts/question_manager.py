#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A unified command-line interface for managing and maintaining Kubelingo questions and YAML files.
"""
import argparse
import os
import sys
import sqlite3
import datetime
import shutil
import logging
import uuid
import subprocess
import json
import time
import tempfile
import re
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional, Dict, Any, Set, Tuple
import difflib
import hashlib

# --- Imports from generator.py ---

# Add project root to path to allow imports from kubelingo
try:
    project_root = Path(__file__).resolve().parent.parent
    DATA_DIR = project_root / 'question-data'
    YAML_QUIZ_DIR = project_root / 'yaml' / 'questions'
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    import yaml
    from tqdm import tqdm
    from rich.console import Console
    from rich.progress import track
    import llm
    import questionary

    # Kubelingo imports
    import kubelingo.database as db_mod
    from kubelingo.database import (
        get_db_connection, add_question, init_db, get_all_questions
    )
    from kubelingo.question import Question, ValidationStep, QuestionSubject
    from kubelingo.modules.question_generator import AIQuestionGenerator
    from kubelingo.modules.yaml_loader import YAMLLoader
    from kubelingo.modules.ai_categorizer import AICategorizer
    from kubelingo.integrations.llm import get_llm_client
    from kubelingo.utils import path_utils
    from kubelingo.utils.path_utils import (
        get_project_root, get_live_db_path, find_yaml_files_from_paths,
        get_all_question_dirs, get_all_yaml_files_in_repo, find_and_sort_files_by_mtime,
        find_yaml_files, find_sqlite_files, get_all_sqlite_files_in_repo
    )
    from kubelingo.utils.config import (
        YAML_BACKUP_DIRS, DATABASE_FILE, QUESTION_DIRS, MASTER_DATABASE_FILE,
        SECONDARY_MASTER_DATABASE_FILE, SQLITE_BACKUP_DIRS
    )
    from kubelingo.utils.ui import Fore, Style

    # Define a default backup file path, similar to other manager scripts.
    BACKUP_DATABASE_FILE = project_root / "backups" / "kubelingo.db"
    YAML_QUIZ_BACKUP_DIR = project_root / "question-data" / "yaml-bak"
except ImportError as e:
    print(f"Error: A required module is not available: {e}. "
          "Please ensure all dependencies are installed and you run this from the project root.", file=sys.stderr)
    sys.exit(1)


# Optional imports for specific generators
try:
    import openai
except ImportError:
    openai = None

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


# --- Handlers from original question_manager.py ---

class MockArgs:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)



def handle_build_index(args):
    """Handler for building/updating the question index from YAML files."""
    print("Building question index from YAML files...")
    question_dir = Path(args.directory)
    if not question_dir.is_dir():
        print(f"Error: Directory not found at {question_dir}", file=sys.stderr)
        sys.exit(1)

    yaml_files = list(question_dir.rglob('*.yaml')) + list(question_dir.rglob('*.yml'))
    
    if not yaml_files:
        print(f"No YAML files found in {question_dir}", file=sys.stderr)
        return

    conn = db_mod.get_db_connection()
    try:
        db_mod.index_yaml_files(yaml_files, conn, verbose=not args.quiet)
        print("Index build complete.")
    finally:
        conn.close()


def handle_list_triaged(args):
    """Lists all questions marked for triage."""
    conn = db_mod.get_db_connection()
    if not conn:
        print("Could not connect to database.", file=sys.stderr)
        sys.exit(1)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM questions WHERE triage = 1")
        triaged_ids = {row[0] for row in cursor.fetchall()}

        if not triaged_ids:
            print("No triaged questions found.")
            return

        loader = YAMLLoader()
        # Discover all YAML files from configured directories
        all_yaml_files = loader.discover()

        found_questions = []
        for file_path in all_yaml_files:
            try:
                questions_in_file = loader.load_file(file_path)
                for q in questions_in_file:
                    if q.id in triaged_ids:
                        found_questions.append(q)
            except Exception as e:
                print(f"Warning: Could not process file {file_path}: {e}", file=sys.stderr)

        if not found_questions:
            print("No triaged questions found in YAML files (database may be out of sync).")
        else:
            print(f"Found {len(found_questions)} triaged questions:")
            for q in sorted(found_questions, key=lambda x: x.id):
                print(f"  - ID: {q.id}\n    Prompt: {q.prompt[:100]}...")
    except Exception as e:
        print(f"Error listing triaged questions: {e}", file=sys.stderr)
        if "no such column: triage" in str(e):
            print("Hint: The 'triage' column might be missing. You may need to update your database schema.", file=sys.stderr)
    finally:
        conn.close()


def handle_set_triage_status(args):
    """Sets the triage status for a given question ID."""
    conn = db_mod.get_db_connection()
    if not conn:
        print("Could not connect to database.", file=sys.stderr)
        sys.exit(1)
    
    status_bool = not args.un_triage # True for triage, False for un-triage

    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE questions SET triage = ? WHERE id = ?", (status_bool, args.question_id))
        if cursor.rowcount == 0:
            print(f"Error: Question with ID '{args.question_id}' not found.")
        else:
            conn.commit()
            action = "Triaged" if status_bool else "Un-triaged"
            print(f"Successfully {action} question with ID '{args.question_id}'.")
    except Exception as e:
        print(f"Error updating triage status: {e}", file=sys.stderr)
        if "no such column: triage" in str(e):
            print("Hint: The 'triage' column might be missing. You may need to update your database schema.", file=sys.stderr)
    finally:
        conn.close()

def handle_remove_question(args):
    """Deletes a question from the database by its ID."""
    conn = db_mod.get_db_connection()
    if not conn:
        print("Could not connect to database.", file=sys.stderr)
        sys.exit(1)

    try:
        # First, check if the question exists in the database
        cursor = conn.cursor()
        cursor.execute("SELECT source_file FROM questions WHERE id = ?", (args.question_id,))
        row = cursor.fetchone()
        if not row:
            print(f"Error: Question with ID '{args.question_id}' not found in the database.")
            return

        source_file = row[0]
        prompt = "Could not load prompt from YAML."
        try:
            loader = YAMLLoader()
            full_path = get_project_root() / source_file
            questions_in_file = loader.load_file(str(full_path))
            for q in questions_in_file:
                if q.id == args.question_id:
                    prompt = q.prompt
                    break
        except Exception:
            pass  # Prompt remains as the error message

        confirm = questionary.confirm(f"Are you sure you want to delete question '{args.question_id}' ({prompt[:50]}...)?").ask()
        if not confirm:
            print("Deletion cancelled.")
            return

        cursor.execute("DELETE FROM questions WHERE id = ?", (args.question_id,))
        if cursor.rowcount == 0:
            print(f"Error: Question with ID '{args.question_id}' not found during deletion.")
        else:
            conn.commit()
            print(f"Successfully deleted question with ID '{args.question_id}'.")
    except Exception as e:
        print(f"Error deleting question: {e}", file=sys.stderr)
    finally:
        conn.close()


# --- Functions from original generator.py ---

def _get_existing_prompts_for_pdf_gen() -> List[str]:
    """Fetches all existing question prompts from YAML files."""
    prompts = []
    loader = YAMLLoader()
    all_yaml_files = loader.discover()
    print("Loading existing prompts from YAML files...")

    for file_path in track(all_yaml_files, description="Scanning YAMLs..."):
        try:
            questions_in_file = loader.load_file(file_path)
            for q in questions_in_file:
                if q.prompt:
                    prompts.append(q.prompt)
        except Exception as e:
            print(f"Warning: Could not process file {file_path}: {e}", file=sys.stderr)

    print(f"Found {len(prompts)} existing questions in YAML files.")
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
    if not openai or not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set, or openai package not installed.", file=sys.stderr)
        sys.exit(1)

    client = openai.OpenAI()

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
            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.5,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
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


def _load_shared_context_for_ai_quiz():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    path = os.path.join(root, 'shared_context.md')
    try:
        with open(path, encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Warning: shared_context.md not found at {path}. Using empty context.")
        return ''


def _generate_ai_quiz_questions(api_key, examples, n):
    if not isinstance(openai.api_key, str) or len(openai.api_key) == 0:
        openai.api_key = api_key
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
    client = openai.OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model='gpt-3.5-turbo',
        messages=[system_msg, user_msg],
        temperature=0.7,
        response_format={"type": "json_object"},
    )
    text = resp.choices[0].message.content.strip()
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
    if not openai:
        print("Error: openai package not found. Please install with 'pip install openai'.")
        sys.exit(1)

    api_key = os.getenv('OPENAI_API_KEY')
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
        if not api_key:
            print('Error: Missing OPENAI_API_KEY environment variable.')
            sys.exit(1)
        items = _generate_ai_quiz_questions(api_key, examples, args.num)

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
        fm.append("    category: \"api-discovery-docs\"")
        fm.append("    citation: \"https://kubernetes.io/docs/reference/generated/kubernetes-api/\"")
        fm.append("")

    # Use relative path to respect CWD for testing
    output_dir = Path('yaml/questions')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'resource_reference.yaml'
    with open(output_path, 'w') as f:
        f.write("\n".join(fm))
    print(f"Generated {output_path} with {len(out)} questions.")


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
        out.append("    category: \"linux-syntax\"")
        out.append("    citation: \"https://kubernetes.io/docs/reference/kubectl/#operations\"")
        out.append("")

    # Use relative path to respect CWD for testing
    output_dir = Path('yaml/questions')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'kubectl_operations.yaml'
    with open(output_path, 'w') as f:
        f.write("\n".join(out))
    print(f"Generated {output_path} with {len(ops)} questions.")


def handle_ai_questions(args):
    """Handles 'ai-questions' subcommand."""
    if not all([AIQuestionGenerator, YAMLLoader, yaml, get_llm_client]):
        print("Missing kubelingo modules or PyYAML. Cannot generate AI questions.", file=sys.stderr)
        sys.exit(1)

    try:
        llm_client = get_llm_client()
    except (ValueError, ImportError) as e:
        print(f"Failed to initialize LLM client: {e}", file=sys.stderr)
        print("Please ensure your AI provider and API key are configured correctly.", file=sys.stderr)
        sys.exit(1)

    base_questions = []
    if args.example_source_file:
        print(f"Loading example questions from YAML source file '{args.example_source_file}'...")
        loader = YAMLLoader()
        try:
            base_questions = loader.load_file(args.example_source_file)
        except Exception as e:
            print(f"Warning: Could not load example questions from '{args.example_source_file}': {e}", file=sys.stderr)
            base_questions = []

        if not base_questions:
            print(f"Warning: No example questions found in source file '{args.example_source_file}'.")
        else:
            print(f"Using {len(base_questions)} questions from the source file as examples.")

    generator = AIQuestionGenerator(llm_client=llm_client)

    # The generator expects specific types like 'socratic', 'command', etc.
    # UI uses friendlier names like 'Basic'.
    category_map = {
        'Basic': 'socratic',
        'Command': 'command',
        'Manifest': 'yaml_author', # Default to authoring for generation
    }
    internal_category = category_map.get(args.category, args.category.lower())

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
        category=internal_category,
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


def _generate_sa_questions_list():
    """Return a list of question dicts in unified format."""
    questions = []
    # Question 0
    ans0 = "apiVersion: v1\nkind: ServiceAccount\nmetadata:\n  name: sa-reader\n  namespace: default"
    questions.append({
        "id": "service_accounts::0", "prompt": "Create a ServiceAccount named 'sa-reader' in the 'default' namespace.",
        "type": "command", "pre_shell_cmds": [], "initial_files": {},
        "validation_steps": [{"cmd": ans0, "matcher": {"exit_code": 0}}],
        "explanation": None, "categories": ["Service Account"], "metadata": {"answer": ans0}
    })
    # Question 1
    ans1 = "apiVersion: v1\nkind: ServiceAccount\nmetadata:\n  name: sa-deployer\n  namespace: dev-namespace"
    questions.append({
        "id": "service_accounts::1", "prompt": "Create a ServiceAccount named 'sa-deployer' in the 'dev-namespace' namespace.",
        "type": "command", "pre_shell_cmds": [], "initial_files": {},
        "validation_steps": [{"cmd": ans1, "matcher": {"exit_code": 0}}],
        "explanation": None, "categories": ["Service Account"], "metadata": {"answer": ans1}
    })
    # Question 2
    ans2 = "apiVersion: v1\nkind: ServiceAccount\nmetadata:\n  name: sa-db\n  namespace: prod\nimagePullSecrets:\n- name: db-secret"
    questions.append({
        "id": "service_accounts::2", "prompt": "Create a ServiceAccount named 'sa-db' in the 'prod' namespace with imagePullSecret 'db-secret'.",
        "type": "command", "pre_shell_cmds": [], "initial_files": {},
        "validation_steps": [{"cmd": ans2, "matcher": {"exit_code": 0}}],
        "explanation": None, "categories": ["Service Account"], "metadata": {"answer": ans2}
    })
    return questions


def handle_service_account(args):
    """Handles 'service-account' subcommand."""
    questions = _generate_sa_questions_list()
    if args.num and args.num > 0:
        questions = questions[:args.num]
    json_out = json.dumps(questions, indent=2)
    if args.output:
        output_dir = os.path.dirname(args.output)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
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


# --- Functions from original yaml_manager.py ---

def do_consolidate(args):
    """
    Finds all YAML quiz files, extracts unique questions based on their 'prompt',
    and consolidates them into a single YAML file.
    """
    output_file = Path(args.output) if args.output else \
        Path(project_root) / 'backups' / 'yaml' / f'consolidated_unique_questions_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.yaml'

    print(f"{Fore.CYAN}--- Consolidating unique YAML questions ---{Style.RESET_ALL}")

    try:
        all_yaml_files = get_all_yaml_files_in_repo()
        print(f"Found {len(all_yaml_files)} YAML files to scan in the repository.")
    except Exception as e:
        print(f"{Fore.RED}Error finding YAML files: {e}{Style.RESET_ALL}")
        return

    unique_questions: List[Dict[str, Any]] = []
    seen_prompts: Set[str] = set()
    total_questions_count = 0
    files_with_questions_count = 0

    for file_path in all_yaml_files:
        questions_in_file = []
        try:
            with file_path.open('r', encoding='utf-8') as f:
                documents = yaml.safe_load_all(f)
                for data in documents:
                    if not data:
                        continue
                    if isinstance(data, dict) and 'questions' in data and isinstance(data.get('questions'), list):
                        questions_in_file.extend(data['questions'])
                    elif isinstance(data, list):
                        questions_in_file.extend(data)

        except (yaml.YAMLError, IOError):
            continue

        if questions_in_file:
            files_with_questions_count += 1
            for question in questions_in_file:
                if isinstance(question, dict) and 'prompt' in question:
                    total_questions_count += 1
                    prompt = question.get('prompt')
                    if prompt and prompt not in seen_prompts:
                        seen_prompts.add(prompt)
                        unique_questions.append(question)

    print(f"Scanned {len(all_yaml_files)} YAML files.")
    print(f"Processed {files_with_questions_count} files containing questions.")
    print(f"Found {total_questions_count} questions in total, with {len(unique_questions)} being unique.")

    if not unique_questions:
        print(f"{Fore.YELLOW}No unique questions found to consolidate.{Style.RESET_ALL}")
        return

    output_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump({'questions': unique_questions}, f, sort_keys=False, indent=2)
        print(f"\n{Fore.GREEN}Successfully consolidated {len(unique_questions)} unique questions to:{Style.RESET_ALL}")
        print(str(output_file))
    except IOError as e:
        print(f"{Fore.RED}Error writing to output file {output_file}: {e}{Style.RESET_ALL}")


def _process_with_gemini(prompt, model="gemini-2.0-flash"):
    """Uses the llm-gemini plugin to process a prompt with the specified model."""
    try:
        model_instance = llm.get_model(model)
        response = model_instance.prompt(prompt)
        return response.text().strip()
    except Exception as e:
        logging.error(f"Error processing with Gemini: {e}")
        return None

def _add_question_for_create_quizzes(conn, id, prompt, source_file, response, category, source, validation_steps, validator, review):
    """Adds a question to the database, handling JSON serialization for complex fields."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO questions (
                id, prompt, source_file, response, category, source,
                validation_steps, validator, review
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                prompt=excluded.prompt,
                source_file=excluded.source_file,
                response=excluded.response,
                category=excluded.category,
                source=excluded.source,
                validation_steps=excluded.validation_steps,
                validator=excluded.validator,
                review=excluded.review;
        """, (
            id, prompt, str(source_file), response, category, source,
            json.dumps(validation_steps) if validation_steps is not None else None,
            json.dumps(validator) if validator is not None else None,
            review
        ))
    except sqlite3.Error as e:
        logging.error(f"Failed to add question {id}: {e}")

def do_create_quizzes(args):
    """Indexes YAML files from a consolidated backup and populates the database."""
    logging.info("Starting to create quizzes from consolidated YAML backup.")
    
    proj_root = get_project_root()
    yaml_dir = proj_root / 'yaml'

    logging.info(f"Looking for consolidated question files in: {yaml_dir}")

    if not yaml_dir.is_dir():
        logging.error(f"YAML directory not found at: {yaml_dir}")
        return

    logging.info("Scanning for latest consolidated question file...")
    consolidated_files = sorted(yaml_dir.glob('consolidated_unique_questions_*.yaml'), reverse=True)

    if not consolidated_files:
        logging.warning(f"No 'consolidated_unique_questions_*.yaml' files found in '{yaml_dir}'.")
        return
    
    latest_file = consolidated_files[0]
    yaml_files = [latest_file]

    logging.info(f"Found latest consolidated file. Processing: {latest_file}")
    
    db_path = ":memory:"
    conn = get_db_connection(db_path)
    init_db(db_path=db_path, clear=True)
    logging.info("In-memory database initialized and schema created.")

    question_count = 0
    
    for yaml_file in yaml_files:
        logging.info(f"Processing file: {yaml_file}")
        try:
            with open(yaml_file, 'r') as f:
                data = yaml.safe_load(f)

            if isinstance(data, dict):
                questions_data = data.get('questions')
            else:
                questions_data = data

            if not isinstance(questions_data, list):
                logging.error(f"Skipping file {yaml_file}: Expected a list of questions, but got {type(questions_data)}.")
                continue

            for q_data in questions_data:
                q_id = q_data.get('id')
                q_type = q_data.get('type')
                
                exercise_category = q_type
                if not exercise_category:
                    logging.warning(f"Skipping question {q_id} in {yaml_file}: missing type.")
                    continue
                
                prompt = q_data.get('prompt')
                if not prompt:
                    logging.warning(f"Skipping question {q_id}: Missing 'prompt'.")
                    continue

                if q_type == 'manifest':
                    if 'vim' not in q_data.get('tools', []):
                        logging.warning(f"Skipping manifest question {q_id}: 'vim' tool is required.")
                        continue
                    if 'kubectl apply' not in q_data.get('validation', []):
                        logging.warning(f"Skipping manifest question {q_id}: 'kubectl apply' validation is required.")
                        continue

                _add_question_for_create_quizzes(
                    conn=conn, id=q_id, prompt=prompt, source_file=str(yaml_file),
                    response=q_data.get('response'), category=exercise_category,
                    source=q_data.get('source'), validation_steps=q_data.get('validation'),
                    validator=q_data.get('validator'), review=q_data.get('review', False)
                )
                question_count += 1
                logging.info(f"Added question ID: {q_id} with category '{exercise_category}'.")

        except yaml.YAMLError as e:
            logging.error(f"Error parsing YAML file {yaml_file}: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred while processing {yaml_file}: {e}")
    
    if question_count > 0:
        conn.commit()
        logging.info(f"Successfully added {question_count} questions to the in-memory database.")

        live_db_path = Path(get_live_db_path())
        dump_filename = f"quiz_dump_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        dump_path = live_db_path.parent / dump_filename
        
        with open(dump_path, 'w') as f:
            for line in conn.iterdump():
                f.write(f'{line}\n')
        
        logging.info(f"Database dump created at: {dump_path}")
        logging.info(f"To load this dump into your main database, run:")
        logging.info(f"sqlite3 '{live_db_path}' < '{dump_path}'")
    else:
        logging.info("No new questions were added to the database.")
        
    conn.close()
    logging.info("Quiz creation process finished.")

def _question_to_key(q: Question) -> str:
    """Creates a canonical, hashable key from a Question object for deduplication."""
    d = asdict(q)
    d.pop('id', None)
    d.pop('source_file', None)
    cleaned_dict = {k: v for k, v in d.items() if v is not None}
    return json.dumps(cleaned_dict, sort_keys=True, default=str)

def do_deduplicate(args):
    """Deduplicate YAML questions in a directory and consolidate them."""
    source_dir = Path(args.directory)
    if not source_dir.is_dir():
        print(f"Error: Directory not found at '{source_dir}'")
        exit(1)
    output_file = Path(args.output_file) if args.output_file else source_dir / "unique_questions.yaml"
    loader = YAMLLoader()
    yaml_files = list(source_dir.rglob("*.yaml")) + list(source_dir.rglob("*.yml"))
    if not yaml_files:
        print(f"No YAML files found in '{source_dir}'.")
        return
    print(f"Found {len(yaml_files)} YAML files to process...")
    unique_questions: Dict[str, Question] = {}
    total_questions = 0
    duplicates_found = 0
    for file_path in yaml_files:
        try:
            questions = loader.load_file(str(file_path))
            total_questions += len(questions)
            for q in questions:
                key = _question_to_key(q)
                if key not in unique_questions:
                    unique_questions[key] = q
                else:
                    duplicates_found += 1
        except Exception as e:
            print(f"Warning: Could not process file {file_path}: {e}")
            continue
    print("\nScan complete.")
    print(f"  - Total questions found: {total_questions}")
    print(f"  - Duplicate questions found: {duplicates_found}")
    print(f"  - Unique questions: {len(unique_questions)}")
    if args.dry_run:
        print("\nDry run enabled. No files will be written.")
        return
    questions_for_yaml = [asdict(q) for q in unique_questions.values()]
    cleaned_questions_for_yaml = []
    for q_dict in questions_for_yaml:
        cleaned_questions_for_yaml.append({k: v for k, v in q_dict.items() if v is not None})
    output_data = {"questions": cleaned_questions_for_yaml}
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(output_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        print(f"\nSuccessfully wrote {len(unique_questions)} unique questions to '{output_file}'.")
    except IOError as e:
        print(f"\nError writing to output file '{output_file}': {e}")
        exit(1)

def _compare_questions(questions1: List[Question], questions2: List[Question]):
    """Compares two lists of Question objects and prints the differences."""
    q1_map = {q.id: q for q in questions1}
    q2_map = {q.id: q for q in questions2}
    added_ids = q2_map.keys() - q1_map.keys()
    removed_ids = q1_map.keys() - q2_map.keys()
    common_ids = q1_map.keys() & q2_map.keys()
    modified_ids = []
    for q_id in common_ids:
        if str(q1_map[q_id]) != str(q2_map[q_id]):
            modified_ids.append(q_id)
    if added_ids:
        print(f"--- Added ({len(added_ids)}) ---")
        for q_id in sorted(list(added_ids)): print(f"  + {q_id}")
    if removed_ids:
        print(f"--- Removed ({len(removed_ids)}) ---")
        for q_id in sorted(list(removed_ids)): print(f"  - {q_id}")
    if modified_ids:
        print(f"--- Modified ({len(modified_ids)}) ---")
        for q_id in sorted(modified_ids): print(f"  ~ {q_id}")
    if not any([added_ids, removed_ids, modified_ids]):
        print("No changes detected.")
    print("-" * 20)

def do_diff(args):
    """Diff YAML backup files to track changes in questions."""
    loader = YAMLLoader()
    if len(args.files) == 2:
        path1, path2 = Path(args.files[0]), Path(args.files[1])
        if not path1.is_file() or not path2.is_file():
            print("Error: One or both files not found.", file=sys.stderr)
            sys.exit(1)
        print(f"Comparing {path1.name} to {path2.name}...")
        questions1 = loader.load_file(str(path1))
        questions2 = loader.load_file(str(path2))
        _compare_questions(questions1, questions2)
    elif len(args.files) == 0:
        print(f"No files specified. Discovering backups in: {', '.join(YAML_BACKUP_DIRS)}")
        try:
            all_files = find_yaml_files_from_paths(YAML_BACKUP_DIRS)
        except Exception as e:
            print(f"Error scanning directories: {e}", file=sys.stderr)
            sys.exit(1)
        if len(all_files) < 2:
            print("Not enough backup files found to compare.", file=sys.stderr)
            sys.exit(1)
        sorted_files = sorted(all_files, key=lambda p: p.stat().st_mtime)
        files_to_compare = sorted_files
        if args.range.lower() != 'all':
            try:
                num = int(args.range)
                if num < 1: raise ValueError
                if len(sorted_files) > num: files_to_compare = sorted_files[-(num + 1):]
            except (ValueError, TypeError):
                print(f"Invalid range: '{args.range}'. Please provide a positive integer or 'all'.", file=sys.stderr)
                sys.exit(1)
        if len(files_to_compare) < 2:
            print("Not enough backup files in the specified range to compare.", file=sys.stderr)
            sys.exit(1)
        print(f"Found {len(sorted_files)} backups. Comparing {len(files_to_compare) - 1} version(s) sequentially...")
        for i in range(len(files_to_compare) - 1):
            path1, path2 = files_to_compare[i], files_to_compare[i + 1]
            print(f"\nComparing {path1.name} -> {path2.name}")
            questions1 = loader.load_file(str(path1))
            questions2 = loader.load_file(str(path2))
            _compare_questions(questions1, questions2)
    else:
        print("Please provide either two files to compare, or no files to compare all backups.", file=sys.stderr)
        sys.exit(1)

def _row_to_question_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Converts a sqlite3.Row object to a dictionary, deserializing JSON fields."""
    q_dict = dict(row)
    for key, value in q_dict.items():
        if isinstance(value, str) and (value.strip().startswith('{') or value.strip().startswith('[')):
            try:
                q_dict[key] = json.loads(value)
            except json.JSONDecodeError:
                # Not a JSON string, leave as is
                pass
    return q_dict


def _export_db_to_yaml_func(output_file: str, db_path: Optional[str] = None) -> int:
    """Exports questions referenced in the database to a single YAML file."""
    conn = get_db_connection(db_path=db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM questions")
    all_meta = cursor.fetchall()
    conn.close()

    loader = YAMLLoader()
    project_root = get_project_root()
    
    questions_by_file = {}
    for meta_row in all_meta:
        source_file = meta_row['source_file']
        if source_file not in questions_by_file:
            questions_by_file[source_file] = []
        questions_by_file[source_file].append(meta_row['id'])

    all_questions_content = {}
    for source_file, _ in questions_by_file.items():
        try:
            full_path = project_root / source_file
            questions = loader.load_file(str(full_path))
            for q in questions:
                all_questions_content[q.id] = asdict(q)
        except Exception as e:
            print(f"Warning: Could not load questions from {source_file}: {e}", file=sys.stderr)

    exported_questions = []
    for meta_row in all_meta:
        q_id = meta_row['id']
        if q_id in all_questions_content:
            # Merge DB metadata over YAML content
            content = all_questions_content[q_id]
            meta_dict = _row_to_question_dict(meta_row)
            content.update(meta_dict)
            exported_questions.append(content)

    with open(output_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(exported_questions, f, default_flow_style=False, sort_keys=False)
        
    print(f"Exported {len(exported_questions)} questions to {output_file}")
    return len(exported_questions)

def do_export(args):
    """Export questions DB to YAML."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.output:
        out_file = args.output
    else:
        out_dir = YAML_BACKUP_DIRS[0] if YAML_BACKUP_DIRS else "backups"
        os.makedirs(out_dir, exist_ok=True)
        out_file = os.path.join(out_dir, f"questions_{timestamp}.yaml")
    _export_db_to_yaml_func(out_file)

def do_import_ai(args):
    """Import questions from YAML files into a new SQLite database with AI-powered categorization."""
    if os.path.exists(args.output_db):
        overwrite = input(f"{Fore.YELLOW}Warning: Output database '{args.output_db}' already exists. Overwrite? (y/n): {Style.RESET_ALL}").lower()
        if overwrite != 'y':
            print("Operation cancelled.")
            return
        os.remove(args.output_db)
    try:
        categorizer = AICategorizer()
    except (ImportError, ValueError) as e:
        print(f"{Fore.RED}Failed to initialize AI Categorizer: {e}{Style.RESET_ALL}")
        sys.exit(1)
    print(f"Initializing new database at: {args.output_db}")
    init_db(db_path=args.output_db)
    conn = get_db_connection(db_path=args.output_db)
    search_dirs = args.search_dir or get_all_question_dirs()
    yaml_files = find_yaml_files(search_dirs)
    if not yaml_files:
        print(f"{Fore.YELLOW}No YAML files found in the specified directories.{Style.RESET_ALL}")
        return
    print(f"Found {len(yaml_files)} YAML file(s) to process...")
    all_questions = []
    loader = YAMLLoader()
    for file_path in yaml_files:
        try:
            questions = loader.load_file(str(file_path))
            all_questions.extend(questions)
        except Exception as e:
            print(f"{Fore.YELLOW}Warning: Could not process file '{file_path}': {e}{Style.RESET_ALL}")
    unique_questions: Dict[str, Question] = {}
    for q in all_questions:
        if q.prompt and q.prompt not in unique_questions:
            unique_questions[q.prompt] = q
    print(f"Found {len(unique_questions)} unique questions. Categorizing with AI...")
    processed_count = 0
    try:
        cursor = conn.cursor()
        with tqdm(total=len(unique_questions), desc="Categorizing Questions") as pbar:
            for question in unique_questions.values():
                q_dict = asdict(question)
                q_id = q_dict.get('id')
                prompt = q_dict.get('prompt')
                ai_categories = categorizer.categorize_question(q_dict)

                # Start with values from YAML, then override with AI
                category = q_dict.get('schema_category') or q_dict.get('type')
                subject = q_dict.get('subject_matter')

                if ai_categories:
                    category = ai_categories.get('exercise_category', category)
                    subject = ai_categories.get('subject_matter', subject)

                # The `add_question` function handles JSON serialization.
                add_question(
                    conn=conn,
                    id=q_id,
                    prompt=prompt,
                    source_file=q_dict.get('source_file'),
                    answers=q_dict.get('answers'),
                    category=category,
                    subject=subject,
                    source=q_dict.get('source'),
                    type=q_dict.get('question_type') or q_dict.get('type'),
                    validator=q_dict.get('validator'),
                    review=q_dict.get('review', False),
                    explanation=q_dict.get('explanation'),
                    validation_steps=q_dict.get('validation_steps')
                )
                processed_count += 1
                pbar.update(1)
        conn.commit()
    finally:
        if conn: conn.close()
    print(f"\n{Fore.GREEN}Successfully processed and added {processed_count} questions to '{args.output_db}'.{Style.RESET_ALL}")

INDEX_FILE_PATH = project_root / "backups" / "index.yaml"

def _get_file_metadata(path: Path) -> dict:
    """Gathers metadata for a given file."""
    stat = path.stat()
    return {
        "path": str(path.relative_to(project_root)), "size_bytes": stat.st_size,
        "last_modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }

def do_index(args):
    """Finds all YAML files and creates an index file with their metadata."""
    print(f"{Fore.CYAN}--- Indexing all YAML files in repository ---{Style.RESET_ALL}")
    try:
        all_files = find_yaml_files(QUESTION_DIRS)
        if not all_files:
            all_files = get_all_yaml_files_in_repo()
        print("Directories scanned for YAML files:")
        for d in QUESTION_DIRS: print(f"  {d}")
        print("YAML files to index:")
        for p in all_files: print(f"  {p}")
        if not all_files:
            print(f"{Fore.YELLOW}No YAML files found to index in QUESTION_DIRS or repository.{Style.RESET_ALL}")
            return
        print(f"Found {len(all_files)} YAML files to index.")
        index_data = {
            "last_updated": datetime.datetime.now().isoformat(),
            "files": [_get_file_metadata(p) for p in all_files],
        }
        INDEX_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(INDEX_FILE_PATH, "w") as f:
            yaml.safe_dump(index_data, f, indent=2)
        print(f"{Fore.GREEN}Successfully created YAML index at: {INDEX_FILE_PATH}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}An error occurred: {e}{Style.RESET_ALL}")

def _categorize_with_gemini(prompt: str) -> dict:
    """Uses llm-gemini to categorize a question."""
    try:
        result = subprocess.run(
            ["llm", "-m", "gemini-2.0-flash", "-o", "json_object", f"Categorize: {prompt}"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        return json.loads(result.stdout)
    except Exception as e:
        logging.error(f"Error categorizing with llm-gemini: {e}")
        return {}

def do_init(args):
    """Initializes the database from consolidated YAML backups."""
    logging.info("Starting database initialization from consolidated YAML backups...")
    root = get_project_root()
    conn = get_db_connection()
    try:
        backup_dir = root / 'yaml' / 'consolidated_backup'
        if not backup_dir.is_dir():
            logging.warning(f"Consolidated backup directory not found: {backup_dir}")
            return

        yaml_files = sorted(list(backup_dir.glob('**/*.yaml')) + list(backup_dir.glob('**/*.yml')))
        if not yaml_files:
            logging.info(f"No YAML files found in {backup_dir}.")
            return

        logging.info(f"Found {len(yaml_files)} YAML files to process in {backup_dir}.")

        # Clear the database and re-initialize the schema.
        init_db(clear=True, conn=conn)
        logging.info("Database cleared for initialization.")
        
        # Use the central indexing function to populate the DB.
        db_mod.index_yaml_files(yaml_files, conn, verbose=True)

    except Exception as e:
        logging.error(f"An error occurred during database initialization: {e}")
    finally:
        if conn:
            conn.close()
            
    logging.info(f"Database initialization complete.")

def do_list_backups(args):
    """Finds and prints all YAML backup files."""
    backup_dirs = YAML_BACKUP_DIRS
    if not backup_dirs:
        if not args.path_only:
            print("No YAML backup directories are configured.", file=sys.stderr)
        sys.exit(1)
    try:
        backup_files = find_and_sort_files_by_mtime(backup_dirs, [".yaml", ".yml"])
    except Exception as e:
        if not args.path_only:
            print(f"Error scanning directories: {e}", file=sys.stderr)
        sys.exit(1)
    if not backup_files:
        if not args.path_only:
            print("No YAML backup files found.")
        sys.exit(0)
    if args.path_only:
        for f in backup_files:
            print(f)
    else:
        print(f"Searching for YAML backup files in: {', '.join(backup_dirs)}...")
        print(f"\nFound {len(backup_files)} backup file(s), sorted by most recent:\n")
        for f in backup_files:
            mod_time = f.stat().st_mtime
            mod_time_str = datetime.datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
            print(f"- {mod_time_str} | {f.name} ({f.parent})")

EXERCISE_TYPE_TO_CATEGORY = {
    "socratic": "Basic", "command": "Command", "yaml_author": "Manifest",
    "yaml_edit": "Manifest", "live_k8s_edit": "Manifest",
}

def _analyze_file(path):
    """Analyzes a single YAML file and returns statistics about its questions."""
    loader = YAMLLoader()
    try:
        questions = loader.load_file(str(path))
    except Exception as e:
        return {'file': str(path), 'error': f'parse error: {e}'}
    total = len(questions)
    breakdown = {"Basic": Counter(), "Command": Counter(), "Manifest": Counter(), "Unknown": Counter()}
    for q in questions:
        ex_type = getattr(q, "type", "Unknown Type") or "Unknown"
        subject = (getattr(q, 'metadata', None) or {}).get('category', "Uncategorized") or "Uncategorized"
        if subject == "Uncategorized": subject = "Vim"
        major_category = EXERCISE_TYPE_TO_CATEGORY.get(ex_type, "Unknown")
        if subject in ["Resource Reference", "Kubectl Operations"]: major_category = "Basic"
        breakdown[major_category][subject] += 1
    breakdown = {k: v for k, v in breakdown.items() if v}
    breakdown_dict = {k: dict(v) for k, v in breakdown.items()}
    category_counts = {cat: sum(counts.values()) for cat, counts in breakdown.items()}
    size = path.stat().st_size
    mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(path.stat().st_mtime))
    return {
        'file': str(path), 'size': size, 'mtime': mtime, 'total': total,
        'category_counts': category_counts, 'breakdown': breakdown_dict,
    }

def do_backup_stats(args):
    """Show stats for the latest YAML backup file found in the given paths."""
    scan_paths = args.paths or YAML_BACKUP_DIRS
    try:
        files = find_yaml_files_from_paths(scan_paths)
    except Exception as e:
        print(f"Error scanning directories: {e}", file=sys.stderr)
        sys.exit(1)
    if args.pattern:
        regex = re.compile(args.pattern)
        files = [f for f in files if regex.search(str(f))]
    if not files:
        print(f"No YAML files found in {', '.join(scan_paths)}")
        sys.exit(0)
    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    if not args.json:
        print(f"Found {len(files)} backup files. Analyzing latest: {latest_file}", file=sys.stderr)
    stats = [_analyze_file(latest_file)]
    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        for s in stats:
            if 'error' in s:
                print(f"{s['file']}: {s['error']}")
            else:
                print(f"File: {s['file']}")
                print(f" Size: {s['size']} bytes  Modified: {s['mtime']}")
                print(f" Total questions: {s['total']}")
                print(" Questions by Exercise Category:")
                for category, count in sorted(s['category_counts'].items(), key=lambda x: -x[1]):
                    print(f"  {category}: {count}")
                    subject_counts = s.get('breakdown', {}).get(category, {})
                    for subject, sub_count in sorted(subject_counts.items(), key=lambda x: -x[1]):
                        print(f"    - {subject}: {sub_count}")
                print()

def do_statistics(args):
    """Calculates and prints statistics about questions in YAML files."""
    loader = YAMLLoader()
    yaml_files: List[Path] = []
    if args.path:
        target_path = Path(args.path)
        if not target_path.exists():
            print(f"Error: Path does not exist: {target_path}", file=sys.stderr)
            sys.exit(1)
        if target_path.is_dir():
            print(f"Scanning for YAML files in: {target_path}")
            yaml_files = find_yaml_files([str(target_path)])
        elif target_path.is_file():
            if target_path.suffix.lower() not in ['.yaml', '.yml']:
                print(f"Error: Specified file is not a YAML file: {target_path}", file=sys.stderr)
                sys.exit(1)
            yaml_files = [target_path]
    else:
        search_dirs = QUESTION_DIRS
        print(f"No path specified. Searching in default question directories: {', '.join(search_dirs)}")
        yaml_files = find_yaml_files(search_dirs)
    if not yaml_files:
        print("No YAML files found to analyze.")
        return
    all_questions: List[Question] = []
    print(f"Found {len(yaml_files)} YAML file(s). Loading questions...")
    for file_path in yaml_files:
        try:
            questions_from_file = loader.load_file(str(file_path))
            if questions_from_file:
                all_questions.extend(questions_from_file)
        except Exception as e:
            print(f"Warning: Could not load or parse {file_path}: {e}", file=sys.stderr)
            continue
    if not all_questions:
        print("No questions could be loaded from the specified YAML files.")
        return
    type_counts = Counter(q.type for q in all_questions if hasattr(q, 'type') and q.type)
    category_counts = Counter(q.category for q in all_questions if hasattr(q, 'category') and q.category)
    print(f"\n--- YAML Question Statistics ---")
    print(f"Total Questions Found: {len(all_questions)}")
    print("\n--- Questions by Exercise Type ---")
    if type_counts:
        for q_type, count in type_counts.most_common(): print(f"  - {q_type:<20} {count}")
    else:
        print("  No questions with 'type' field found.")
    print("\n--- Questions by Subject Matter (Category) ---")
    if category_counts:
        for category, count in category_counts.most_common(): print(f"  - {category:<30} {count}")
    else:
        print("  No questions with 'category' field found.")

def do_group_backups(args):
    """
    Group all legacy YAML backup quizzes into a single "legacy_yaml" module.
    """
    conn = get_db_connection() # Uses live DB by default
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM questions WHERE source = 'backup'")
    total = cursor.fetchone()[0]
    if total == 0:
        print("No backup YAML questions found to group.")
        conn.close()
        return
    cursor.execute(
        "UPDATE questions SET source_file = 'legacy_yaml' WHERE source = 'backup'"
    )
    conn.commit()
    conn.close()
    print(f"Grouped {total} backup YAML questions into module 'legacy_yaml'.")
    try:
        shutil.copy2(DATABASE_FILE, BACKUP_DATABASE_FILE)
        print(f"Database backup updated at: {BACKUP_DATABASE_FILE}")
    except Exception as e:
        print(f"Failed to backup database: {e}")

def do_import_bak(args):
    """
    Import all YAML-backed quiz questions into the live Kubelingo database.
    """
    init_db()
    yaml_bak_dir = project_root / 'question-data' / 'yaml-bak'
    if not yaml_bak_dir.is_dir():
        print(f"Backup YAML directory not found: {yaml_bak_dir}")
        return

    loader = YAMLLoader()
    total = 0
    conn = get_db_connection()
    try:
        for pattern in ('*.yaml', '*.yml'):
            for path in sorted(yaml_bak_dir.glob(pattern)):
                print(f"Importing questions from: {path.name}")
                try:
                    questions = loader.load_file(str(path))
                except Exception as e:
                    print(f"  Failed to load {path.name}: {e}")
                    continue
                for q in questions:
                    steps = [asdict(s) for s in getattr(q, 'validation_steps', [])]
                    validator = None
                    metadata = getattr(q, 'metadata', {}) or {}
                    expected = metadata.get('correct_yaml')
                    if expected:
                        validator = {'type': 'yaml', 'expected': expected}
                    try:
                        add_question(
                            conn=conn,
                            id=q.id,
                            prompt=q.prompt,
                            source_file=path.name,
                            response=getattr(q, 'response', None),
                            category=(q.categories[0] if getattr(q, 'categories', None) else getattr(q, 'category', None)),
                            source='backup',
                            validation_steps=steps,
                            validator=validator,
                        )
                        total += 1
                    except Exception as e:
                        print(f"  Could not add {q.id}: {e}")
    finally:
        if conn:
            conn.close()

    print(f"Imported {total} questions from YAML backup into the DB.")

    try:
        shutil.copy2(DATABASE_FILE, BACKUP_DATABASE_FILE)
        print(f"Database backup created at: {BACKUP_DATABASE_FILE}")
    except Exception as e:
        print(f"Failed to backup database: {e}")

def do_migrate_all(args):
    """
    Migrate all YAML-based quiz questions into the Kubelingo SQLite database.
    """
    init_db()
    loader = YAMLLoader()
    dirs = [Path(d) for d in QUESTION_DIRS]
    total_added = 0
    conn = get_db_connection()
    try:
        for yaml_dir in dirs:
            if not yaml_dir.is_dir():
                continue
            print(f"Processing YAML directory: {yaml_dir}")
            patterns = ['*.yaml', '*.yml', '*.yaml.bak']
            for pat in patterns:
                for path in sorted(yaml_dir.glob(pat)):
                    try:
                        questions = loader.load_file(str(path))
                    except Exception as e:
                        print(f"Failed to load {path}: {e}")
                        continue
                    if not questions:
                        continue
                    source_file = path.name
                    for q in questions:
                        vs = []
                        for step in getattr(q, 'validation_steps', []):
                            vs.append(asdict(step))
                        validator = None
                        metadata = getattr(q, 'metadata', {}) or {}
                        expected = metadata.get('correct_yaml')
                        if expected:
                            validator = {'type': 'yaml', 'expected': expected}
                        try:
                            add_question(
                                conn=conn,
                                id=q.id,
                                prompt=q.prompt,
                                source_file=source_file,
                                response=None,
                                category=(q.categories[0] if getattr(q, 'categories', None) else None),
                                source=getattr(q, 'source', None),
                                validation_steps=vs,
                                validator=validator,
                                # Preserve full question schema
                                question_type=getattr(q, 'type', None),
                                answers=getattr(q, 'answers', None),
                                correct_yaml=getattr(q, 'correct_yaml', None),
                                pre_shell_cmds=getattr(q, 'pre_shell_cmds', None),
                                initial_files=getattr(q, 'initial_files', None),
                                explanation=getattr(q, 'explanation', None),
                                schema_category=getattr(getattr(q, 'schema_category', None), 'value', None),
                            )
                            total_added += 1
                        except Exception as e:
                            print(f"Failed to add {q.id} from {source_file}: {e}")
    finally:
        if conn:
            conn.close()
    print(f"Migration complete: {total_added} YAML questions added to database.")

def do_migrate_bak(args):
    """
    Clears the database, loads all questions from YAML files in the backup
    directory, saves them to the database, and then creates a new pristine
    backup of the populated database.
    """
    print("Starting migration of questions from 'yaml-bak' directory to database...")

    # 1. Clear the existing database
    print("Clearing the database to ensure a fresh import...")
    init_db(clear=True)
    conn = get_db_connection()

    # 2. Load questions from yaml-bak
    print(f"Searching for YAML files in: {YAML_QUIZ_BACKUP_DIR}")
    if not os.path.isdir(YAML_QUIZ_BACKUP_DIR):
        print(f"Error: Backup directory not found at '{YAML_QUIZ_BACKUP_DIR}'")
        sys.exit(1)

    yaml_loader = YAMLLoader()
    total_questions_added = 0

    try:
        for filename in sorted(os.listdir(YAML_QUIZ_BACKUP_DIR)):
            if not filename.endswith(('.yaml', '.yml')):
                continue

            file_path = os.path.join(YAML_QUIZ_BACKUP_DIR, filename)
            print(f"  -> Processing file: {filename}")
            try:
                questions = yaml_loader.load_file(file_path)
                if not questions:
                    print(f"     No questions found in {filename}.")
                    continue

                intended_source_file = file_path.replace(os.sep + 'yaml-bak' + os.sep, os.sep + 'yaml' + os.sep)

                for q in questions:
                    add_question(
                        conn=conn,
                        id=q.id,
                        prompt=q.prompt,
                        source_file=intended_source_file,
                        response=getattr(q, 'response', None),
                        category=getattr(q, 'category', None),
                        source=getattr(q, 'source', "https://kubernetes.io/docs/home/"),
                        validation_steps=[asdict(vs) for vs in getattr(q, 'validation_steps', [])],
                        validator=getattr(q, 'validator', None),
                        explanation=getattr(q, 'explanation', None)
                    )
                total_questions_added += len(questions)
                print(f"     Added {len(questions)} questions from {filename}.")

            except Exception as e:
                print(f"     Error processing {filename}: {e}")
    finally:
        if conn:
            conn.close()

    print(f"\nTotal questions added to the database: {total_questions_added}")

    if total_questions_added == 0:
        print("\nNo questions were added. Aborting backup.")
        return

    print(f"\nBacking up new database to '{BACKUP_DATABASE_FILE}'...")
    try:
        backup_dir = os.path.dirname(BACKUP_DATABASE_FILE)
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        shutil.copyfile(DATABASE_FILE, BACKUP_DATABASE_FILE)
        print("Backup successful.")
        print(f"Pristine database at '{BACKUP_DATABASE_FILE}' has been updated.")
    except Exception as e:
        print(f"Error creating backup: {e}")

def _create_db_schema_for_verify(conn: sqlite3.Connection):
    """Creates the questions table in the SQLite database for verification."""
    # Use the canonical schema from the main database module
    db_mod.init_db(conn=conn)

def _import_yaml_to_db_for_verify(yaml_path: str, conn: sqlite3.Connection):
    """
    Reads questions from a YAML file and imports their metadata into the DB.
    """
    loader = YAMLLoader()
    source_file = os.path.basename(yaml_path)
    
    try:
        questions = loader.load_file(yaml_path)
    except FileNotFoundError:
        print(f"Error: YAML file not found at {yaml_path}", file=sys.stderr)
        return 0
    except Exception as e:
        print(f"Error parsing YAML file {yaml_path}: {e}", file=sys.stderr)
        return 0

    if not questions:
        print(f"Info: No questions found in {source_file}.")
        return 0

    inserted_count = 0
    for q in questions:
        # Calculate content hash from a stable representation of the question data.
        stable_repr = json.dumps(asdict(q), sort_keys=True, default=str)
        content_hash = hashlib.sha256(stable_repr.encode('utf-8')).hexdigest()

        # The add_question function from db_mod handles inserting only metadata.
        # It's safer to build the dict explicitly to avoid passing unwanted kwargs.
        db_dict = {
            'id': q.id,
            'source_file': source_file,
            'category_id': q.schema_category.value if q.schema_category else None,
            'subject_id': q.subject_matter.value if q.subject_matter else None,
            'review': q.review,
            'triage': q.triage,
            'content_hash': content_hash
        }
        try:
            # Use a raw cursor to do INSERT OR IGNORE, as add_question does REPLACE
            cursor = conn.cursor()
            columns = ', '.join(db_dict.keys())
            placeholders = ', '.join('?' * len(db_dict))
            sql = f"INSERT OR IGNORE INTO questions ({columns}) VALUES ({placeholders})"
            cursor.execute(sql, tuple(db_dict.values()))
            if cursor.rowcount > 0:
                inserted_count += 1
        except Exception as e:
            print(f"Error adding question {q.id} to DB: {e}", file=sys.stderr)
    
    conn.commit()
    skipped_duplicates = len(questions) - inserted_count
    print(f"Imported from {source_file}: Inserted {inserted_count} new questions, skipped {skipped_duplicates} duplicates.")
    return inserted_count

def do_verify(args):
    """Verify YAML question import to SQLite and loading from the database."""
    yaml_files = find_yaml_files_from_paths(args.paths)

    if not yaml_files:
        print("Error: No YAML files found in the provided paths.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(yaml_files)} YAML file(s) to process.")

    tmp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = tmp_db_file.name
    tmp_db_file.close()

    try:
        print(f"Using temporary database: {db_path}")

        conn = sqlite3.connect(db_path)
        _create_db_schema_for_verify(conn)

        total_imported = 0
        imported_files_map = {}  # basename -> count

        for yaml_file in yaml_files:
            num_imported = _import_yaml_to_db_for_verify(str(yaml_file), conn)
            if num_imported > 0:
                total_imported += num_imported
                imported_files_map[os.path.basename(str(yaml_file))] = num_imported

        conn.close()

        if total_imported == 0:
            print("No questions found in any YAML file. Exiting.")
            return

        print(f"\nTotal questions imported: {total_imported}")
        print("\nVerifying import by querying the database...")

        verify_conn = sqlite3.connect(db_path)
        verify_cursor = verify_conn.cursor()

        verify_cursor.execute("SELECT DISTINCT source_file FROM questions")
        source_files_in_db = {row[0] for row in verify_cursor.fetchall()}

        imported_basenames = set(imported_files_map.keys())

        if not imported_basenames.issubset(source_files_in_db):
            missing = sorted(list(imported_basenames - source_files_in_db))
            print(f"ERROR: DB query did not discover the following source file(s): {', '.join(missing)}", file=sys.stderr)
            print(f"Discovered files in DB: {sorted(list(source_files_in_db))}", file=sys.stderr)
            sys.exit(1)

        print(f"Successfully discovered all {len(imported_files_map)} source file(s).")
        print("\nVerifying question counts...")

        total_loaded = 0
        mismatched_files = []
        for basename, num_imported in sorted(imported_files_map.items()):
            verify_cursor.execute("SELECT COUNT(*) FROM questions WHERE source_file = ?", (basename,))
            num_loaded = verify_cursor.fetchone()[0]
            total_loaded += num_loaded

            if num_loaded == num_imported:
                print(f"  ✅ '{basename}': Imported {num_imported}, DB query loaded {num_loaded}.")
            else:
                print(f"  ❌ '{basename}': Imported {num_imported}, DB query loaded {num_loaded}.")
                mismatched_files.append(basename)

        verify_conn.close()

        print("-" * 20)
        print(f"Total Imported: {total_imported}, Total Loaded by query: {total_loaded}")

        if not mismatched_files and total_imported == total_loaded:
            print("\nSUCCESS: The number of loaded questions matches the number of imported questions for all files.")
        else:
            print(f"\nERROR: Mismatch in question count detected for one or more files.", file=sys.stderr)
            sys.exit(1)

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"Temporary database {db_path} cleaned up.")

def do_recategorize_ai(args):
    """Recategorize questions in the database using AI, filling in missing fields."""
    print(f"{Fore.CYAN}--- Recategorizing questions with AI ---{Style.RESET_ALL}")
    try:
        categorizer = AICategorizer()
    except (ImportError, ValueError) as e:
        print(f"{Fore.RED}Failed to initialize AI Categorizer: {e}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Please ensure you have configured an AI provider and API key.{Style.RESET_ALL}")
        sys.exit(1)

    conn = get_db_connection()
    try:
        # Load all question content from YAML files
        loader = YAMLLoader()
        all_yaml_questions = []
        project_root_path = get_project_root()
        for file_path in loader.discover():
            try:
                # Ensure source_file is a relative path for consistency with DB
                relative_path = str(Path(file_path).relative_to(project_root_path))
                questions = loader.load_file(file_path)
                for q in questions:
                    q.source_file = relative_path
                all_yaml_questions.extend(questions)
            except Exception as e:
                print(f"Warning: Could not process file {file_path}: {e}", file=sys.stderr)
        
        all_yaml_questions_map = {q.id: q for q in all_yaml_questions}

        # Get question metadata from the database
        db_questions_metadata = get_all_questions(conn)

        questions_to_categorize_ids = set()
        if getattr(args, 'force', False):
            print("Forcing recategorization for all questions.")
            questions_to_categorize_ids = {q['id'] for q in db_questions_metadata}
        else:
            questions_to_categorize_ids = {
                q['id'] for q in db_questions_metadata
                if not q.get('category_id') or not q.get('subject_id')
            }

        if not questions_to_categorize_ids:
            print(f"{Fore.GREEN}All questions are already categorized. Use --force to re-run on all.{Style.RESET_ALL}")
            return

        print(f"Found {len(questions_to_categorize_ids)} questions to categorize.")

        updated_count = 0
        with tqdm(total=len(questions_to_categorize_ids), desc="Categorizing Questions") as pbar:
            for q_id in questions_to_categorize_ids:
                if q_id not in all_yaml_questions_map:
                    pbar.update(1)
                    continue

                question_obj = all_yaml_questions_map[q_id]
                q_dict = asdict(question_obj)
                
                ai_categories = categorizer.categorize_question(q_dict)
                if ai_categories:
                    stable_repr = json.dumps(q_dict, sort_keys=True, default=str)
                    content_hash = hashlib.sha256(stable_repr.encode('utf-8')).hexdigest()

                    db_metadata_update = {
                        'id': q_id,
                        'source_file': question_obj.source_file,
                        'category_id': ai_categories.get('exercise_category'),
                        'subject_id': ai_categories.get('subject_matter'),
                        'content_hash': content_hash,
                    }

                    # add_question will do an INSERT OR REPLACE, so this updates the question
                    add_question(conn, **db_metadata_update)
                    updated_count += 1
                pbar.update(1)

        conn.commit()
        print(f"\n{Fore.GREEN}Successfully categorized {updated_count} questions.{Style.RESET_ALL}")

    finally:
        conn.close()


def do_organize_generated(args):
    """Consolidate, import, and clean up AI-generated YAML questions."""
    source_dir = Path(args.source_dir)
    output_file = Path(args.output_file)

    if not source_dir.is_dir():
        print(f"Error: Source directory not found at '{source_dir}'", file=sys.stderr)
        sys.exit(1)

    print(f"--- Organizing generated questions from: {source_dir} ---")

    # 1. Deduplicate and consolidate
    print(f"Step 1: Consolidating unique questions into {output_file}...")

    loader = YAMLLoader()
    yaml_files = list(source_dir.rglob("*.yaml")) + list(source_dir.rglob("*.yml"))

    if not yaml_files:
        print("No YAML files found to organize.")
        return

    unique_questions: Dict[str, Question] = {}
    total_questions = 0
    duplicates_found = 0
    for file_path in yaml_files:
        try:
            questions = loader.load_file(str(file_path))
            total_questions += len(questions)
            for q in questions:
                key = _question_to_key(q)
                if key not in unique_questions:
                    unique_questions[key] = q
                else:
                    duplicates_found += 1
        except Exception as e:
            print(f"Warning: Could not process file {file_path}: {e}", file=sys.stderr)
            continue

    print(f"Scan complete. Found {total_questions} total questions, {duplicates_found} duplicates. Consolidating {len(unique_questions)} unique questions.")

    if not unique_questions:
        print("No valid questions found to process.")
        return

    if args.dry_run:
        print(f"[DRY RUN] Would write {len(unique_questions)} unique questions to '{output_file}'.")
    else:
        questions_for_yaml = [asdict(q) for q in unique_questions.values()]
        # clean up None values for cleaner YAML
        cleaned_questions_for_yaml = []
        for q_dict in questions_for_yaml:
            cleaned_questions_for_yaml.append({k: v for k, v in q_dict.items() if v is not None})
        
        output_data = {"questions": cleaned_questions_for_yaml}
        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                yaml.dump(output_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            print(f"Successfully wrote {len(unique_questions)} unique questions to '{output_file}'.")
        except IOError as e:
            print(f"Error writing to output file '{output_file}': {e}", file=sys.stderr)
            sys.exit(1)

    # 2. Update database
    print("\nStep 2: Updating database...")
    db_path = args.db_path or get_live_db_path()
    
    if not Path(db_path).exists() and not args.dry_run:
        print(f"Warning: Database not found at {db_path}. Skipping database operations.")
    else:
        conn = get_db_connection(db_path=db_path)
        try:
            # Delete old questions
            source_dir_pattern = str(source_dir) + '/%'
            print(f"Deleting questions from DB where source_file LIKE '{source_dir_pattern}'...")
            
            cursor = conn.cursor()
            if args.dry_run:
                if Path(db_path).exists():
                    cursor.execute("SELECT COUNT(*) FROM questions WHERE source_file LIKE ?", (source_dir_pattern,))
                    count = cursor.fetchone()[0]
                    print(f"[DRY RUN] Would delete {count} questions from the database.")
                else:
                    print(f"[DRY RUN] Database does not exist, would skip deletion.")

            else:
                cursor.execute("DELETE FROM questions WHERE source_file LIKE ?", (source_dir_pattern,))
                print(f"Deleted {cursor.rowcount} questions.")
                conn.commit()

            # Import new consolidated questions
            print(f"Importing questions from '{output_file}'...")
            if args.dry_run:
                print(f"[DRY RUN] Would import {len(unique_questions)} questions into the database.")
            else:
                # Call sqlite_manager to import the consolidated file
                sqlite_manager_path = project_root / 'scripts' / 'sqlite_manager.py'
                cmd = [
                    sys.executable,
                    str(sqlite_manager_path),
                    'create-from-yaml',
                    '--db-path', db_path,
                    '--yaml-files', str(output_file)
                ]
                # create-from-yaml will append to the DB if --clear is not used.
                try:
                    subprocess.run(cmd, check=True)
                except subprocess.CalledProcessError as e:
                    print(f"Error calling sqlite_manager.py: {e}", file=sys.stderr)
                    sys.exit(1)

        finally:
            if conn: conn.close()

    # 3. Clean up original files
    if not args.no_cleanup:
        print(f"\nStep 3: Cleaning up original files in {source_dir}...")
        if args.dry_run:
            print(f"[DRY RUN] Would delete {len(yaml_files)} original YAML files.")
        else:
            deleted_count = 0
            for file_path in yaml_files:
                try:
                    file_path.unlink()
                    deleted_count += 1
                except Exception as e:
                    print(f"Error deleting file {file_path}: {e}", file=sys.stderr)
            print(f"Deleted {deleted_count} original YAML files.")

    print("\nOrganization complete.")

# --- Functions from original generator.py ---


# --- Functions from sqlite_manager.py ---

# This was removed from config, define locally to avoid breaking script logic.
ENABLED_QUIZZES = {}


# --- Migrate from YAML ---
def do_migrate_from_yaml(args):
    """Migrates questions from YAML files to the SQLite database."""
    print("Initializing database...")
    init_db(clear=args.clear)
    if args.clear:
        print("Database cleared and re-initialized.")
    else:
        print("Database initialized.")

    yaml_loader = YAMLLoader()
    total_questions = 0

    yaml_files = []
    if args.file:
        p = Path(args.file)
        if p.exists():
            yaml_files.append(str(p))
        else:
            print(f"Error: File not found at '{args.file}'")
            return
    else:
        source_paths = []
        if args.source_dirs:
            for d in args.source_dirs:
                p = Path(d)
                if p.is_dir():
                    source_paths.append(p)
                else:
                    print(f"Warning: Provided source directory not found, skipping: {d}")
        else:
            # Default directories, as per documentation
            for subdir in ('yaml', 'yaml-bak', 'manifests'):
                source_paths.append(Path(DATA_DIR) / subdir)

        for quiz_dir in source_paths:
            print(f"Scanning quiz directory: {quiz_dir}")
            if not quiz_dir.is_dir():
                continue
            for pattern in ('*.yaml', '*.yml', '*.yaml.bak'):
                for p in quiz_dir.glob(pattern):
                    yaml_files.append(str(p))

    yaml_files = sorted(list(set(yaml_files)))  # de-duplicate and sort

    print(f"Found {len(yaml_files)} unique YAML quiz files to migrate.")

    for file_path in yaml_files:
        print(f"Processing {file_path}...")
        try:
            # Load questions as objects for structured data
            questions_obj: list[Question] = yaml_loader.load_file(file_path)
            
            # Load raw data to get attributes not on the Question dataclass, like 'review'
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_questions_data = yaml.load(f, Loader=yaml.FullLoader)
            raw_q_map = {
                item.get('id'): item for item in raw_questions_data if isinstance(item, dict)
            }

            for q in questions_obj:
                raw_q_data = raw_q_map.get(q.id, {})
                q_data = {
                    'id': q.id,
                    'prompt': q.prompt,
                    'response': q.response,
                    'category': q.category,
                    'source': getattr(q, 'source', None),
                    'validation_steps': [asdict(step) for step in q.validation_steps],
                    'validator': q.validator,
                    'source_file': os.path.basename(file_path),
                    'review': raw_q_data.get('review', False),
                    'explanation': getattr(q, 'explanation', None)
                }
                add_question(**q_data)
            total_questions += len(questions_obj)
            print(f"  Migrated {len(questions_obj)} questions.")
        except Exception as e:
            print(f"Error processing file {file_path}: {e}")

    print(f"\nMigration complete. Total questions migrated: {total_questions}")

    # Create a backup of the newly migrated database, clearly named in the repo
    try:
        backup_dir = os.path.dirname(BACKUP_DATABASE_FILE)
        os.makedirs(backup_dir, exist_ok=True)
        # Copy the active user DB (~/.kubelingo/kubelingo.db) into project backup
        shutil.copy2(DATABASE_FILE, BACKUP_DATABASE_FILE)
        print(f"Created a backup of the questions database at: {BACKUP_DATABASE_FILE}")
    except Exception as e:
        print(f"Could not create database backup: {e}")


# --- Normalize Source Paths ---
def do_normalize_sources(args):
    """Normalizes `source_file` to be just the basename."""
    db_path = args.db_path or get_live_db_path()
    # Connect to the questions database
    conn = get_db_connection(db_path=db_path)
    cursor = conn.cursor()
    # Fetch all current source_file values
    cursor.execute("SELECT id, source_file FROM questions")
    rows = cursor.fetchall()
    updated = 0
    for qid, src in rows:
        # Compute normalized basename
        base = os.path.basename(src) if src else src
        if base and base != src:
            cursor.execute(
                "UPDATE questions SET source_file = ? WHERE id = ?",
                (base, qid)
            )
            updated += 1
    conn.commit()
    conn.close()
    print(f"Updated {updated} source_file entries in {db_path}")


# --- List DB Modules ---
def do_list_modules(args):
    """Lists all quiz modules currently stored in the Kubelingo SQLite DB."""
    from kubelingo.modules.db_loader import DBLoader
    loader = DBLoader()
    modules = loader.discover()
    if not modules:
        print("No quiz modules found in the DB.")
        return
    print("Available DB quiz modules (module_name: question count):")
    for sf in modules:
        name, _ = os.path.splitext(sf)
        # Count questions in each module
        try:
            qs = loader.load_file(sf)
            count = len(qs)
        except Exception:
            count = 'error'
        print(f" - {name}: {count}")


# --- Prune Empty DBs ---
def is_db_empty(db_path: Path) -> bool:
    """Checks if a SQLite database is empty by looking for user-created tables."""
    if db_path.stat().st_size == 0:
        return True

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        )
        tables = cursor.fetchall()
        return len(tables) == 0
    except sqlite3.DatabaseError:
        print(f"Warning: Could not open '{db_path.relative_to(project_root)}' as a database. Skipping.")
        return False
    finally:
        if conn:
            conn.close()

def do_prune_empty(args):
    """Scans configured directories for SQLite files and removes any that are empty."""
    SCAN_DIRS = [
        project_root / ".kubelingo",
        project_root / "archive",
    ]
    SQLITE_EXTENSIONS = [".db", ".sqlite3"]

    print("Scanning for and removing empty databases...")
    deleted_count = 0
    for scan_dir in SCAN_DIRS:
        if not scan_dir.is_dir():
            continue

        print(f"-> Scanning directory: {scan_dir.relative_to(project_root)}")
        found_files = []
        for ext in SQLITE_EXTENSIONS:
            found_files.extend(scan_dir.rglob(f"*{ext}"))

        if not found_files:
            print("  No SQLite files found.")
            continue

        for file_path in found_files:
            if is_db_empty(file_path):
                print(f"  - Deleting empty database: {file_path.relative_to(project_root)}")
                try:
                    file_path.unlink()
                    deleted_count += 1
                except OSError as e:
                    print(f"    Error deleting file: {e}")

    print(f"\nScan complete. Deleted {deleted_count} empty database(s).")


# --- Build Master DB ---
def import_questions_for_master(files: list[Path], conn: sqlite3.Connection):
    """Loads all questions from a list of YAML file paths and adds them to the database."""
    print(f"Importing from {len(files)} found YAML files...")

    question_count = 0
    for file_path in files:
        print(f"  - Processing '{file_path.name}'...")
        with open(file_path, 'r', encoding='utf-8') as f:
            questions_data = yaml.load(f, Loader=yaml.FullLoader)
            if not questions_data:
                continue

            questions_list = questions_data
            if isinstance(questions_data, dict):
                questions_list = questions_data.get('questions', [questions_data])

            if not isinstance(questions_list, list):
                continue

            for q_dict in questions_list:
                if not isinstance(q_dict, dict):
                    continue
                if 'metadata' in q_dict and isinstance(q_dict['metadata'], dict):
                    metadata = q_dict.pop('metadata')
                    metadata.pop('links', None)
                    for k, v in metadata.items():
                        if k not in q_dict:
                            q_dict[k] = v

                if 'category' in q_dict:
                    q_dict['subject_matter'] = q_dict.pop('category')

                q_type = q_dict.get('type', 'command')
                if q_type in ('yaml_edit', 'yaml_author', 'live_k8s_edit'):
                    schema_cat = 'manifest'
                elif q_type == 'socratic':
                    schema_cat = 'basic'
                else:  # command, etc.
                    schema_cat = 'command'
                q_dict['schema_category'] = schema_cat
                q_dict['category'] = schema_cat

                if 'type' in q_dict:
                    q_dict['question_type'] = q_dict.pop('type')
                else:
                    q_dict['question_type'] = q_type
                if 'answer' in q_dict:
                    q_dict['response'] = q_dict.pop('answer')

                q_dict['source_file'] = file_path.name
                links = q_dict.pop('links', None)
                if links:
                    metadata = q_dict.get('metadata')
                    if not isinstance(metadata, dict):
                        metadata = {}
                    metadata['links'] = links
                    q_dict['metadata'] = metadata
                add_question(conn=conn, **q_dict)
                question_count += 1
    print(f"\nImport complete. Added/updated {question_count} questions.")
    return question_count

def backup_live_to_master(source_db_path: str):
    """Backs up the given database to create the master copies."""
    live_db_path = Path(source_db_path)
    backup_master_path = Path(MASTER_DATABASE_FILE)
    backup_secondary_path = Path(SECONDARY_MASTER_DATABASE_FILE)

    if not live_db_path.exists():
        print(f"Error: Database not found at '{live_db_path}'. Cannot create backup.")
        return

    print(f"\nBacking up database from '{live_db_path}'...")
    backup_master_path.parent.mkdir(exist_ok=True)
    shutil.copy(live_db_path, backup_master_path)
    print(f"  - Created primary master backup: '{backup_master_path}'")
    shutil.copy(live_db_path, backup_secondary_path)
    print(f"  - Created secondary master backup: '{backup_secondary_path}'")
    print("\nBackup complete.")

def do_build_master(args):
    """Builds the Kubelingo master question database from consolidated YAML files."""
    print("--- Building Kubelingo Master Question Database ---")

    print(f"\nScanning for YAML files in: '{QUESTION_DIRS}'")
    if not any(os.path.isdir(d) for d in QUESTION_DIRS):
        print(f"\nError: None of the configured question directories were found: {QUESTION_DIRS}")
        sys.exit(1)

    all_yaml_files = find_yaml_files(QUESTION_DIRS)
    if not all_yaml_files:
        print(f"\nError: No question YAML files found in '{QUESTION_DIRS}'.")
        sys.exit(1)

    print(f"Found {len(all_yaml_files)} YAML file(s) to process.")

    db_path = args.db_path or DATABASE_FILE
    print(f"\nStep 1: Preparing live database at '{db_path}'...")
    init_db(db_path=db_path, clear=True)
    print("  - Cleared and initialized database for build.")

    print(f"\nStep 2: Importing questions from all found YAML files...")
    questions_imported = 0
    conn = get_db_connection(db_path=db_path)
    try:
        questions_imported = import_questions_for_master(all_yaml_files, conn)
    finally:
        conn.close()

    if questions_imported > 0:
        print(f"\nStep 3: Creating master database backups...")
        backup_live_to_master(db_path)
    else:
        print("\nNo questions were imported. Skipping database backup.")

    print("\n--- Build process finished. ---")


# --- Update Schema Category ---
def do_update_schema_category(args):
    """DEPRECATED: schema_category is now derived automatically."""
    print("This command is deprecated and no longer has any effect.")
    print("The 'schema_category' is now automatically derived from the question 'type'.")


# --- Indexing ---
def get_file_metadata(path: Path) -> dict:
    """Gathers metadata for a given file."""
    stat = path.stat()
    return {
        "path": str(path.relative_to(project_root)),
        "size_bytes": stat.st_size,
        "last_modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }


def do_index_sqlite(args):
    """Finds all SQLite files and creates an index file with their metadata."""
    index_file_path = project_root / "backups" / "sqlite_index.yaml"

    default_backup = project_root / ".kubelingo" / "backups"
    if args.dirs:
        scan_dirs = args.dirs
        print(f"{Fore.CYAN}--- Indexing SQLite files in specified directories ---{Style.RESET_ALL}")
    elif SQLITE_BACKUP_DIRS:
        scan_dirs = SQLITE_BACKUP_DIRS
        print(f"{Fore.CYAN}--- Indexing SQLite files in configured backup directories ---{Style.RESET_ALL}")
    else:
        scan_dirs = None
        print(f"{Fore.CYAN}--- Indexing all SQLite files in repository ---{Style.RESET_ALL}")

    if scan_dirs:
        sqlite_files = find_sqlite_files(scan_dirs)
    else:
        sqlite_files = get_all_sqlite_files_in_repo()

    if scan_dirs:
        print("Directories scanned for SQLite files:")
        for d in scan_dirs:
            print(f"  {d}")

    all_files = sorted(list(set(sqlite_files)))

    if not all_files:
        print(f"{Fore.YELLOW}No SQLite files found to index.{Style.RESET_ALL}")
        return

    print(f"Found {len(all_files)} SQLite files to index:")
    for p in all_files:
        print(f"  {p}")

    index_data = {
        "last_updated": datetime.datetime.now().isoformat(),
        "files": [get_file_metadata(p) for p in all_files],
    }

    index_file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(index_file_path, "w") as f:
        yaml.safe_dump(index_data, f, indent=2)

    print(f"{Fore.GREEN}Successfully created SQLite index at: {index_file_path}{Style.RESET_ALL}")


# --- Schema Display ---
def do_schema(args):
    """Display the SQLite database schema."""
    db_path_str = args.db_path or DATABASE_FILE
    
    conn = get_db_connection(db_path=db_path_str)
    cursor = conn.cursor()
    cursor.execute("SELECT type, name, tbl_name, sql FROM sqlite_master WHERE sql NOT NULL ORDER BY type, name")
    rows = cursor.fetchall()
    conn.close()

    statements = [row[3].strip() + ';' for row in rows if row[3]]
    output_text = '\n\n'.join(statements)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(output_text)
        print(f"Schema written to {out_path}")
    else:
        print(output_text)


# --- List Backups ---
def do_list_sqlite(args):
    """Finds and displays all SQLite backup files."""
    backup_dirs = args.directories or SQLITE_BACKUP_DIRS
    if not backup_dirs:
        if not args.path_only:
            print("No SQLite backup directories are configured or provided.", file=sys.stderr)
        sys.exit(1)

    backup_files = find_sqlite_files(backup_dirs)
    if not backup_files:
        if not args.path_only:
            print("No SQLite backup files found.")
        sys.exit(1)

    sorted_files = sorted(backup_files, key=lambda p: p.stat().st_mtime, reverse=True)

    if args.path_only:
        for f in sorted_files:
            print(f)
    else:
        print(f"Searching for SQLite backup files in: {', '.join(backup_dirs)}...")
        print(f"\nFound {len(sorted_files)} backup file(s), sorted by most recent:\n")
        for f in sorted_files:
            mod_time = f.stat().st_mtime
            mod_time_str = datetime.datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
            print(f"  - {f} (Last modified: {mod_time_str})")


# --- Unarchive ---
def _sha256_checksum(file_path: Path, block_size=65536) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(block_size), b""):
            sha256.update(block)
    return sha256.hexdigest()

def do_unarchive(args):
    """Moves SQLite files from archive/ and prunes old databases."""
    ARCHIVE_DIR = project_root / "archive"
    DEST_DIR = project_root / ".kubelingo"
    SQLITE_EXTENSIONS = [".db", ".sqlite3"]
    MAX_DBS_TO_KEEP = 10

    if not ARCHIVE_DIR.is_dir():
        print(f"Error: Archive directory not found at '{ARCHIVE_DIR}'")
        return

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Moving SQLite files to: {DEST_DIR.relative_to(project_root)}")
    existing_hashes = {_sha256_checksum(p) for p in DEST_DIR.iterdir() if p.is_file()}
    found_files = []
    for ext in SQLITE_EXTENSIONS:
        found_files.extend(ARCHIVE_DIR.rglob(f"*{ext}"))
    if not found_files:
        print("No SQLite files found in archive directory.")
    for file_path in found_files:
        dest_path = DEST_DIR / file_path.name
        try:
            file_hash = _sha256_checksum(file_path)
            if file_hash in existing_hashes:
                print(f"Removing duplicate from archive: {file_path.relative_to(project_root)}")
                file_path.unlink()
                continue
            print(f"Moving {file_path.relative_to(project_root)} to {dest_path.relative_to(project_root)}")
            shutil.move(str(file_path), str(dest_path))
            existing_hashes.add(file_hash)
        except Exception as e:
            print(f"Error moving {file_path}: {e}")
    # Prune after moving
    print("\nPruning old SQLite databases...")
    scan_dirs = [str(DEST_DIR), str(ARCHIVE_DIR)]
    all_db_files = find_and_sort_files_by_mtime(scan_dirs, SQLITE_EXTENSIONS)
    if len(all_db_files) > MAX_DBS_TO_KEEP:
        files_to_delete = all_db_files[MAX_DBS_TO_KEEP:]
        print(f"Deleting {len(files_to_delete)} oldest files to keep {MAX_DBS_TO_KEEP} newest.")
        for file_path in files_to_delete:
            try:
                print(f"  - Deleting old database: {file_path}")
                file_path.unlink()
            except OSError as e:
                print(f"    Error deleting file {file_path}: {e}")

# --- Restore ---
def do_restore(args):
    """Restores the live database from a SQLite backup file."""
    selected_backup_path_str = args.backup_db
    if not selected_backup_path_str:
        backup_files = find_and_sort_files_by_mtime(SQLITE_BACKUP_DIRS, [".db", ".sqlite", ".sqlite3"])
        if not backup_files:
            print("No SQLite backup files found to restore from.", file=sys.stderr); sys.exit(1)
        choices = [questionary.Choice(f"{f.name} ({datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')})", value=str(f)) for f in backup_files]
        selected_backup_path_str = questionary.select("Select a backup to restore:", choices=choices).ask()
        if not selected_backup_path_str:
            print("Restore cancelled."); sys.exit(0)

    selected_backup_path = Path(selected_backup_path_str)
    if not selected_backup_path.exists():
        print(f"Error: backup file not found: {selected_backup_path}"); sys.exit(1)

    live_db_path = Path(get_live_db_path())
    print(f"\nThis will OVERWRITE the current live database:\n  {live_db_path}\nwith the contents of backup:\n  {selected_backup_path}")

    if not args.yes and not questionary.confirm("Are you sure you want to proceed?", default=False).ask():
        print("\nRestore aborted by user."); sys.exit(0)
    
    pre_backup_dir_path = 'backups' # from sqlite_manager args default
    if not args.no_pre_backup:
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        pre_backup_dir = Path(pre_backup_dir_path)
        pre_backup_dir.mkdir(parents=True, exist_ok=True)
        pre_dest = pre_backup_dir / f'kubelingo_pre_restore_{timestamp}.db'
        if live_db_path.exists():
            shutil.copy(str(live_db_path), str(pre_dest))
            print(f"Pre-restore backup created: {pre_dest}")

    try:
        live_db_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(selected_backup_path, live_db_path)
        print(f"\nRestore successful. '{live_db_path.name}' has been updated.")
    except Exception as e:
        print(f"\nError during restore: {e}", file=sys.stderr); sys.exit(1)


# --- Create from YAML ---
class QuestionSkipped(Exception):
    def __init__(self, message: str, category: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.category = category

def _normalize_and_prepare_question_for_db(q_data, category_to_source_file, allowed_args):
    q_dict = q_data.copy()

    # Provide defaults for required fields that might be missing in YAML
    q_dict.setdefault('response', '')
    q_dict.setdefault('source', 'YAML import')
    q_dict.setdefault('raw', json.dumps(q_data))

    if "metadata" in q_dict and isinstance(q_dict.get("metadata"), dict):
        metadata = q_dict.pop("metadata")
        q_dict.update({k: v for k, v in metadata.items() if k not in q_dict})
    if "answer" in q_dict: q_dict["correct_yaml"] = q_dict.pop("answer")
    if "starting_yaml" in q_dict: q_dict["initial_files"] = {"manifest.yaml": q_dict.pop("starting_yaml")}
    if "question" in q_dict: q_dict["prompt"] = q_dict.pop("question")
    if q_dict.get("type") in ("yaml_edit", "yaml_author"):
        if "answer" in q_dict and "correct_yaml" not in q_dict: q_dict["correct_yaml"] = q_dict.pop("answer")
        if "starting_yaml" in q_dict and "initial_files" not in q_dict: q_dict["initial_files"] = {"f.yaml": q_dict.pop("starting_yaml")}
    if "type" in q_dict: q_dict["question_type"] = q_dict.pop("type")
    if "subject" in q_dict: q_dict["subject_matter"] = q_dict.pop("subject")
    q_type = q_dict.get("question_type")

    # Map schema category to 'category' column
    if q_type in ("yaml_edit", "yaml_author", "live_k8s_edit", "manifest"):
        q_dict["category"] = "manifest"
    elif q_type in ("command", "kubectl"):
        q_dict["category"] = "command"
    else:
        q_dict["category"] = "basic"

    # Map subject matter from YAML 'category' to 'subject' column
    subject = q_data.get("category")
    if not subject:
        if q_dict.get("question_type") in ("yaml_edit", "yaml_author"):
            subject = "YAML Authoring"
        elif q_dict.get("subject_matter"):
            subject = q_dict["subject_matter"]
        elif q_dict.get("source") == "AI" and q_dict.get("subject_matter"):
            subject = q_dict["subject_matter"].capitalize()

    if subject:
        q_dict['subject'] = subject

    if category_to_source_file.get(subject):
        q_dict["source_file"] = category_to_source_file[subject]
    elif not q_dict.get("source_file"):
        raise QuestionSkipped(f"Unmatched category: {subject}" if subject else "Missing category.", category=subject)

    # Clean up mapped/temporary fields
    for key in ["solution_file", "subject_matter", "type", "category_id", "subject_id"]:
        q_dict.pop(key, None)
        
    return {k: v for k, v in q_dict.items() if k in allowed_args}

def _populate_db_from_yaml(yaml_files, db_path=None):
    if not yaml_files: print("No YAML files found to process."); return
    conn = get_db_connection(db_path=db_path)
    allowed_args = {"id", "prompt", "source_file", "response", "subject", "source", "raw", "validation_steps", "validator", "review", "question_type", "category", "answers", "correct_yaml", "explanation", "initial_files", "pre_shell_cmds", "subject_matter", "metadata"}
    unmatched_categories, skipped_no_category, question_count = set(), 0, 0
    try:
        for file_path in yaml_files:
            print(f"  - Processing '{file_path.name}'...")
            with file_path.open("r", encoding="utf-8") as f:
                questions_data = yaml.load(f, Loader=yaml.FullLoader)
            if not questions_data: continue
            questions_list = questions_data.get("questions") or questions_data.get("entries") if isinstance(questions_data, dict) else questions_data
            if not isinstance(questions_list, list): continue
            for q_data in questions_list:
                try:
                    q_dict_for_db = _normalize_and_prepare_question_for_db(q_data, ENABLED_QUIZZES, allowed_args)
                    add_question(conn=conn, **q_dict_for_db)
                    question_count += 1
                except QuestionSkipped as e:
                    if e.category: unmatched_categories.add(e.category)
                    else: skipped_no_category += 1
        conn.commit()
    except Exception as e:
        conn.rollback(); print(f"Error adding questions to database: {e}", file=sys.stderr); sys.exit(1)
    finally:
        conn.close()
    if unmatched_categories: print("\nWarning: Skipped questions with unmatched categories:", ", ".join(sorted(list(unmatched_categories))))
    if skipped_no_category > 0: print(f"\nWarning: Skipped {skipped_no_category} questions missing a 'category' field.")
    print(f"\nSuccessfully populated database with {question_count} questions.")

def do_create_from_yaml(args):
    """Populate the SQLite database from YAML backup files."""
    if args.yaml_files:
        yaml_files = find_yaml_files_from_paths(args.yaml_files)
    else:
        print("No input paths provided. Locating most recent YAML backup...")
        all_backups = find_and_sort_files_by_mtime(YAML_BACKUP_DIRS, extensions=[".yaml", ".yml"])
        if not all_backups: print(f"{Fore.RED}Error: No YAML backup files found.{Style.RESET_ALL}"); sys.exit(1)
        latest_backup = all_backups[0]
        print(f"Using most recent backup: {Fore.GREEN}{latest_backup}{Style.RESET_ALL}")
        yaml_files = [latest_backup]
    if not yaml_files: print("No YAML files found."); sys.exit(0)
    unique_files = sorted(list(set(yaml_files)))
    print(f"Found {len(unique_files)} YAML file(s) to process:\n" + "\n".join(f"  - {f.name}" for f in unique_files))
    db_path = args.db_path or get_live_db_path()
    init_db(clear=args.clear, db_path=db_path)
    print(f"\nPopulating database at: {db_path}")
    _populate_db_from_yaml(unique_files, db_path=db_path)

# --- Diff ---
def load_db_schema(db_path):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE sql NOT NULL ORDER BY type, name")
    stmts = [row[0].strip() + ';' for row in cursor.fetchall() if row[0]]
    conn.close()
    return stmts

def get_table_row_counts(conn: sqlite3.Connection) -> dict:
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    return {table: cursor.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in tables}

def do_diff_db(args):
    """Compares two SQLite databases."""
    db_a_path, db_b_path = None, None

    if args.db_a and args.db_b:
        db_a_path, db_b_path = Path(args.db_a), Path(args.db_b)
    else:
        # Interactive mode
        backups = find_and_sort_files_by_mtime(SQLITE_BACKUP_DIRS, [".db", ".sqlite", ".sqlite3"])
        if len(backups) < 2:
            print('Need at least two backup databases to diff.')
            return

        choices = [str(p) for p in backups]
        db_a_str = questionary.select('Select first (e.g., newer) DB:', choices).ask()
        db_b_str = questionary.select('Select second (e.g., older) DB:', choices).ask()

        if not db_a_str or not db_b_str:
            print("Diff cancelled.")
            return
        
        db_a_path, db_b_path = Path(db_a_str), Path(db_b_str)

    print(f"\nComparing:\n  (A) {db_a_path}\n  (B) {db_b_path}\n")

    if not args.no_schema:
        print("--- Schema Differences ---")
        schema_a, schema_b = load_db_schema(db_a_path), load_db_schema(db_b_path)
        diff = difflib.unified_diff(schema_a, schema_b, fromfile=str(db_a_path), tofile=str(db_b_path), lineterm='')
        diff_lines = list(diff)
        if diff_lines:
            for line in diff_lines: print(line)
        else:
            print("No schema differences found.")

    if not args.no_counts:
        print("\n--- Row Count Differences ---")
        try:
            conn_a = sqlite3.connect(f"file:{db_a_path}?mode=ro", uri=True)
            conn_b = sqlite3.connect(f"file:{db_b_path}?mode=ro", uri=True)
            counts_a, counts_b = get_table_row_counts(conn_a), get_table_row_counts(conn_b)
            conn_a.close(); conn_b.close()
            all_tables = sorted(list(set(counts_a.keys()) | set(counts_b.keys())))
            diffs = False
            for table in all_tables:
                count_a, count_b = counts_a.get(table, 'N/A'), counts_b.get(table, 'N/A')
                if count_a != count_b:
                    change = (count_a - count_b) if isinstance(count_a, int) and isinstance(count_b, int) else "N/A"
                    change_str = f"{change: d}" if isinstance(change, int) else str(change)
                    print(f"~ {table}: {count_b} -> {count_a} (Change: {change_str})"); diffs = True
            if not diffs: print("No row count differences found.")
        except sqlite3.Error as e:
            print(f"Error comparing row counts: {e}")



def main():
    """Display the question management menu."""
    if len(sys.argv) > 1:
        # Keep arg-based functionality for direct calls
        parser = argparse.ArgumentParser(
            description="A unified tool for managing Kubelingo's questions and YAML files.",
            formatter_class=argparse.RawTextHelpFormatter,
        )
        subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

        # --- Sub-parsers from original question_manager.py ---
        p_build_index = subparsers.add_parser('build-index', help='Builds or updates the question index from YAML files.', description="Scans YAML files in a directory, hashes them, and updates the SQLite question database.")
        p_build_index.add_argument('directory', default='yaml/questions', nargs='?', help='Path to the directory containing YAML question files. Defaults to "yaml/questions".')
        p_build_index.add_argument('--quiet', action='store_true', help="Suppress progress output.")
        p_build_index.set_defaults(func=handle_build_index)

        p_list_triage = subparsers.add_parser('list-triage', help='Lists all questions marked for triage.')
        p_list_triage.set_defaults(func=handle_list_triaged)

        p_triage = subparsers.add_parser('triage', help='Marks a question for triage.')
        p_triage.add_argument('question_id', help='The ID of the question to triage.')
        p_triage.set_defaults(func=handle_set_triage_status, un_triage=False)

        p_untriage = subparsers.add_parser('untriage', help='Removes a question from triage.')
        p_untriage.add_argument('question_id', help='The ID of the question to un-triage.')
        p_untriage.set_defaults(func=handle_set_triage_status, un_triage=True)

        p_remove = subparsers.add_parser('remove', help='Removes a question from the database by ID.')
        p_remove.add_argument('question_id', help='The ID of the question to remove.')
        p_remove.set_defaults(func=handle_remove_question)

        # --- Sub-parsers from original generator.py ---
        p_from_pdf = subparsers.add_parser('from-pdf', help="Generate Kubelingo quiz questions from a PDF.")
        p_from_pdf.add_argument("--pdf-path", required=True, help="Path to the PDF file.")
        p_from_pdf.add_argument("--output-file", required=True, help="Path to save the generated YAML file.")
        p_from_pdf.add_argument("--num-questions-per-chunk", type=int, default=5, help="Number of questions to generate per text chunk.")
        p_from_pdf.set_defaults(func=handle_from_pdf)

        p_ai_quiz = subparsers.add_parser('ai-quiz', help='Generate and validate Kubernetes quizzes via OpenAI')
        p_ai_quiz.add_argument('--num', type=int, default=5, help='Number of questions to generate')
        p_ai_quiz.add_argument('--mock', action='store_true', help='Use mock data for testing validation')
        p_ai_quiz.add_argument('--output', default=None, help='Output JSON file path')
        p_ai_quiz.set_defaults(func=handle_ai_quiz)

        p_ref = subparsers.add_parser('resource-reference', help="Generate a YAML quiz for Kubernetes resource references.")
        p_ref.set_defaults(func=handle_resource_reference)

        p_ops = subparsers.add_parser('kubectl-operations', help="Generate the Kubectl Operations quiz manifest.")
        p_ops.set_defaults(func=handle_kubectl_operations)

        p_ai_q = subparsers.add_parser('ai-questions', help="Generate AI questions and save them to a YAML file.")
        p_ai_q.add_argument("--subject", required=True, help="Subject for the new questions (e.g., 'Kubernetes Service Accounts').")
        p_ai_q.add_argument("--category", choices=['Basic', 'Command', 'Manifest'], default='Command', help="Category of questions to generate.")
        p_ai_q.add_argument("--num-questions", type=int, default=3, help="Number of questions to generate.")
        p_ai_q.add_argument("--example-source-file", help="Path to a YAML file to use as a source of example questions.")
        p_ai_q.add_argument("--output-file", required=True, help="Path to the output YAML file.")
        p_ai_q.set_defaults(func=handle_ai_questions)

        p_val = subparsers.add_parser('validation-steps', help="Generate validation_steps for Kubernetes questions")
        p_val.add_argument('in_path', type=Path, help="JSON file or directory to process")
        p_val.add_argument('--overwrite', action='store_true', help="Overwrite original files")
        p_val.set_defaults(func=handle_validation_steps)

        p_sa = subparsers.add_parser('service-account', help="Generate static Kubernetes ServiceAccount questions.")
        p_sa.add_argument('--to-db', action='store_true', help='Add generated questions to the kubelingo database')
        p_sa.add_argument('-n', '--num', type=int, default=0, help='Number of questions to output (default: all)')
        p_sa.add_argument('-o', '--output', type=str, help='Write generated questions to a JSON file')
        p_sa.set_defaults(func=handle_service_account)

        p_man = subparsers.add_parser('manifests', help="Generates YAML quiz manifests and solution files from question-data JSON.")
        p_man.set_defaults(func=handle_manifests)

        # --- Sub-parsers from original yaml_manager.py ---
        p_consolidate = subparsers.add_parser('consolidate', help="Consolidate unique YAML questions from across the repository into a single file.")
        p_consolidate.add_argument('-o', '--output', type=Path, help=f'Output file path for consolidated questions.')
        p_consolidate.set_defaults(func=do_consolidate)
        
        p_create_quizzes = subparsers.add_parser('create-quizzes', help="Create quizzes from consolidated YAML backup.")
        p_create_quizzes.set_defaults(func=do_create_quizzes)
        
        p_deduplicate = subparsers.add_parser('deduplicate', help="Deduplicate YAML questions in a directory.")
        p_deduplicate.add_argument("directory", type=str, help="Directory containing YAML question files.")
        p_deduplicate.add_argument("-o", "--output-file", type=str, help="Output file for consolidated unique questions.")
        p_deduplicate.add_argument("--dry-run", action="store_true", help="Perform a dry run without writing files.")
        p_deduplicate.set_defaults(func=do_deduplicate)
        
        p_diff = subparsers.add_parser('diff', help="Diff YAML backup files to track changes.")
        p_diff.add_argument('files', nargs='*', help="Two YAML files to compare. If not provided, compares all backups.")
        p_diff.add_argument("--range", help="Number of recent versions to diff (e.g., '5' for last 5). 'all' to diff all.", default="all")
        p_diff.set_defaults(func=do_diff)
        
        p_export = subparsers.add_parser('export', help="Export questions DB to YAML.")
        p_export.add_argument("-o", "--output", help="Output YAML file path.")
        p_export.set_defaults(func=do_export)

        p_import_ai = subparsers.add_parser('import-ai', help="Import from YAML with AI categorization.")
        p_import_ai.add_argument("output_db", help="Path to the new SQLite database file to be created.")
        p_import_ai.add_argument("--search-dir", action='append', help="Directory to search for YAML files. Can be used multiple times.")
        p_import_ai.set_defaults(func=do_import_ai)

        p_index = subparsers.add_parser('index', help="Finds all YAML files and creates an index file with their metadata.")
        p_index.set_defaults(func=do_index)
        
        p_init = subparsers.add_parser('init', help="Initializes the database from consolidated YAML backups.")
        p_init.set_defaults(func=do_init)
        
        p_list_backups = subparsers.add_parser('list-backups', help='Finds and displays all YAML backup files.')
        p_list_backups.add_argument("--path-only", action="store_true", help="Only prints the paths of the files.")
        p_list_backups.set_defaults(func=do_list_backups)
        
        p_backup_stats = subparsers.add_parser('backup-stats', help="Show stats for the latest YAML backup file.")
        p_backup_stats.add_argument('paths', nargs='*', help='Path(s) to YAML file(s) or directories.')
        p_backup_stats.add_argument('-p', '--pattern', help='Regex to filter filenames')
        p_backup_stats.add_argument('--json', action='store_true', help='Output stats in JSON format')
        p_backup_stats.set_defaults(func=do_backup_stats)
        
        p_stats = subparsers.add_parser('stats', help="Get statistics about questions in YAML files.")
        p_stats.add_argument("path", nargs='?', default=None, help="Path to a YAML file or directory.")
        p_stats.set_defaults(func=do_statistics)

        p_group_backups = subparsers.add_parser('group-backups', help="Group legacy YAML backup quizzes into a single module.")
        p_group_backups.set_defaults(func=do_group_backups)

        p_import_bak = subparsers.add_parser('import-bak', help="Import questions from legacy YAML backup directory.")
        p_import_bak.set_defaults(func=do_import_bak)

        p_migrate_all = subparsers.add_parser('migrate-all', help="Migrate all YAML questions from standard directories to DB.")
        p_migrate_all.set_defaults(func=do_migrate_all)

        p_migrate_bak = subparsers.add_parser('migrate-bak', help="Clear DB and migrate from YAML backup directory.")
        p_migrate_bak.set_defaults(func=do_migrate_bak)

        p_verify = subparsers.add_parser('verify', help="Verify YAML question import and loading.")
        p_verify.add_argument("paths", nargs='+', help="Path(s) to YAML file(s) or directories to verify.")
        p_verify.set_defaults(func=do_verify)

        p_organize = subparsers.add_parser('organize-generated', help="Consolidate, import, and clean up AI-generated YAML questions.")
        p_organize.add_argument('--source-dir', default='questions/generated_yaml', help="Directory with generated YAML files.")
        p_organize.add_argument('--output-file', default='questions/ai_generated_consolidated.yaml', help="Consolidated output YAML file.")
        p_organize.add_argument('--db-path', default=None, help="Path to the SQLite database file.")
        p_organize.add_argument('--no-cleanup', action='store_true', help="Do not delete original individual YAML files after consolidation.")
        p_organize.add_argument('--dry-run', action='store_true', help="Show what would be done without making changes.")
        p_organize.set_defaults(func=do_organize_generated)

        p_recategorize_ai = subparsers.add_parser('recategorize-ai', help="Use AI to categorize all questions in the database.")
        p_recategorize_ai.add_argument('--force', action='store_true', help="Force recategorization for all questions, even those already categorized.")
        p_recategorize_ai.set_defaults(func=do_recategorize_ai)

        args = parser.parse_args()
        if hasattr(args, 'func'):
            args.func(args)
        else:
            parser.print_help()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    main()
