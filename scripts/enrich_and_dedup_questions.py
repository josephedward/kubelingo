#!/usr/bin/env python3
"""
Enrich and deduplicate question files using AI-generated explanations.

This script loads questions from JSON, YAML, and Markdown files under a source directory,
deduplicates them by prompt (preferring existing explanations), generates missing explanations
via OpenAI, and writes out a unified question set.
"""
import sys
import os
import argparse
import json
import urllib.request
import urllib.error
from pathlib import Path

# Bring project root into PYTHONPATH for loader imports
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

# Initialize OpenAI client availability and dotenv loader
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

# Load environment variables from .env at repo root (if available)
if DOTENV_AVAILABLE:
    dotenv_path = repo_root / '.env'
    if dotenv_path.exists():
        load_dotenv(dotenv_path=str(dotenv_path))

# Load shared context for AI prompts
shared_context_path = repo_root / 'shared_context.md'
if shared_context_path.exists():
    with open(shared_context_path, 'r', encoding='utf-8') as f:
        SHARED_CONTEXT = f.read()
else:
    SHARED_CONTEXT = ""

from dataclasses import asdict
from typing import Any, List, Dict

from kubelingo.question import Question
from kubelingo.modules.json_loader import JSONLoader
from kubelingo.modules.yaml_loader import YAMLLoader
from kubelingo.modules.md_loader import MDLoader

def load_questions_from_dir(source_dir: Path) -> List[Question]:
    """Recursively load all questions from JSON, YAML, and MD under source_dir."""
    questions: List[Question] = []
    json_loader = JSONLoader()
    yaml_loader = YAMLLoader()
    md_loader = MDLoader()
    # JSON
    for path in source_dir.rglob('*.json'):
        if '_archive' in path.parts:
            continue
        try:
            questions.extend(json_loader.load_file(str(path)))
        except Exception:
            continue
    # YAML
    for path in source_dir.rglob('*.yml'):
        if '_archive' in path.parts:
            continue
        try:
            questions.extend(yaml_loader.load_file(str(path)))
        except Exception:
            continue
    for path in source_dir.rglob('*.yaml'):
        if '_archive' in path.parts:
            continue
        try:
            questions.extend(yaml_loader.load_file(str(path)))
        except Exception:
            continue
    # Markdown
    for path in source_dir.rglob('*.md'):
        if '_archive' in path.parts:
            continue
        try:
            questions.extend(md_loader.load_file(str(path)))
        except Exception:
            continue
    return questions

def normalize_prompt(prompt: str) -> str:
    """Normalize prompt text for deduplication."""
    return ' '.join(prompt.strip().lower().split())
def generate_explanation(prompt: str, model: str = 'gpt-3.5-turbo') -> str:
    """Generate a concise explanation for a question prompt via OpenAI chat completion."""
    if not OPENAI_AVAILABLE:
        raise RuntimeError('openai package not installed; install with pip install openai')
    if not openai.api_key:
        raise RuntimeError('OPENAI_API_KEY environment variable is not set')

    # Build chat messages with shared context
    system_message = SHARED_CONTEXT + "\n\nYou are a helpful assistant that writes concise, educational explanations for Kubernetes quiz questions. " \
                     "Provide only the explanation text without any introductory phrases."
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": f'Question: "{prompt}"'}
    ]
    try:
        response = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            max_tokens=256,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"Error generating explanation: {e}")
    
def generate_validation_steps(prompt: str, answer: str, model: str = 'gpt-3.5-turbo') -> List[Dict[str, Any]]:
    """Generate a list of validation_steps (cmd + matcher) via OpenAI."""
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY environment variable is not set')
    url = 'https://api.openai.com/v1/chat/completions'
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    # Special-case simple Vim answers: just echo the keystroke and match it
    if answer.strip().startswith(':'):
        return [{
            'cmd': f"echo '{answer}'",
            'matcher': {'contains': answer.strip()}
        }]
    system_msg = SHARED_CONTEXT + (
        "\n\nYou are a Kubelingo validation helper. "
        "Given a quiz question prompt and the correct answer, propose up to 5 validation steps. "
        "Each step should be a JSON object with 'cmd' (kubectl command) and 'matcher' (e.g., value, contains). "
        "Return ONLY a JSON array of these objects."
    )
    body = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system_msg},
            {'role': 'user', 'content': f'Question: "{prompt}"\nAnswer: "{answer}"'}
        ],
        'max_tokens': 512,
        'temperature': 0.2,
    }
    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            resp_data = resp.read().decode('utf-8')
            resp_json = json.loads(resp_data)
            content = resp_json['choices'][0]['message']['content'].strip()
            return json.loads(content)
    except Exception as e:
        raise RuntimeError(f"Error generating validation steps: {e}")

def enrich_and_dedup(
    source_dir: Path,
    output_file: Path,
    fmt: str,
    dry_run: bool = False,
    generate_validations: bool = False,
    model: str = 'gpt-3.5-turbo',
):
    questions = [q for q in load_questions_from_dir(source_dir) if q.prompt and q.prompt.strip()]
    if not questions:
        print(f"Error: no question files found under {source_dir}")
        return
    # Deduplicate by prompt
    unique: Dict[str, Question] = {}
    for q in questions:
        key = normalize_prompt(q.prompt)
        if key in unique:
            # prefer one with explanation
            existing = unique[key]
            if existing.explanation:
                continue
            if q.explanation:
                unique[key] = q
            continue
        unique[key] = q
    merged = list(unique.values())
    print(f'Loaded {len(questions)} questions, deduplicated to {len(merged)} unique prompts.')
    # Generate missing explanations
    missing = [q for q in merged if not q.explanation]
    print(f'{len(missing)} questions missing explanations.')
    if missing and dry_run:
        for q in missing:
            print(f'Would generate explanation for: {q.prompt}')
    if missing and not dry_run:
        for q in missing:
            try:
                q.explanation = generate_explanation(q.prompt)
                print(f'Generated explanation for: {q.prompt}')
            except Exception as e:
                print(f'Error generating explanation for "{q.prompt}": {e}')
    # Optionally generate missing validation_steps via AI
    if generate_validations:
        # Identify questions lacking any validation_steps
        val_missing = [q for q in merged if not getattr(q, 'validation_steps', [])]
        print(f"{len(val_missing)} questions missing validation_steps.")
        if val_missing and dry_run:
            for q in val_missing:
                print(f"[DRY-RUN] Would generate validation_steps for: {q.prompt}")
        if val_missing and not dry_run:
            for q in val_missing:
                # Attempt to find the expected answer in metadata
                answer = None
                md = getattr(q, 'metadata', {})
                answer = md.get('response') or md.get('answer')
                if not answer:
                    print(f"Skipping validation generation for '{q.prompt}': no response/answer found")
                    continue
                try:
                    steps = generate_validation_steps(q.prompt, answer, model)
                    if isinstance(steps, list) and steps:
                        q.validation_steps = steps
                        print(f"Generated {len(steps)} validation_steps for: {q.prompt}")
                except Exception as e:
                    print(f"Error generating validation_steps for '{q.prompt}': {e}")
    # Serialize
    data = [asdict(q) for q in merged]
    if dry_run:
        print(f'DRY RUN: would write {len(data)} questions to {output_file}')
        return
    output_file.parent.mkdir(parents=True, exist_ok=True)
    if fmt == 'json':
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    else:
        try:
            import yaml
            with open(output_file, 'w', encoding='utf-8') as f:
                yaml.safe_dump(data, f, sort_keys=False)
        except ImportError:
            raise RuntimeError('PyYAML is required for YAML output')
    print(f'Wrote {len(data)} questions to {output_file}')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_dir', type=Path, help='Directory containing question files')
    parser.add_argument('output_file', type=Path, help='Path to write unified questions')
    parser.add_argument('--format', choices=['json', 'yaml'], default='json', help='Output format')
    parser.add_argument('--dry-run', action='store_true', help='Show actions without making changes')
    parser.add_argument('--generate-validations', action='store_true', help='Use AI to generate validation_steps for questions without them')
    parser.add_argument('--model', default='gpt-3.5-turbo', help='OpenAI model to use for explanations and validations')
    args = parser.parse_args()
    # Validate source directory
    if not args.source_dir.exists() or not args.source_dir.is_dir():
        print(f"Error: source directory not found or not a directory: {args.source_dir}")
        sys.exit(1)
    enrich_and_dedup(
        args.source_dir,
        args.output_file,
        args.format,
        args.dry_run,
        args.generate_validations,
        args.model,
    )

if __name__ == '__main__':
    main()