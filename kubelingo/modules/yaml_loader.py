"""
Loader for YAML-based question files.
"""
import os
try:
    import yaml
except ImportError:
    yaml = None
from typing import List
from kubelingo.modules.base.loader import BaseLoader
from kubelingo.question import Question, ValidationStep, QuestionCategory
from kubelingo.utils.config import QUESTION_DIRS


class YAMLLoader(BaseLoader):
    """Discovers and parses YAML question modules."""

    def discover(self) -> List[str]:
        """Discovers YAML files in all configured question directories."""
        paths: List[str] = []
        for directory in QUESTION_DIRS:
            if not directory or not os.path.isdir(directory):
                continue

            for fname in os.listdir(directory):
                if fname.endswith(('.yaml', '.yml')):
                    paths.append(os.path.join(directory, fname))
        return sorted(paths)

    def load_file(self, path: str) -> List[Question]:
        # Load and normalize YAML file into Question objects
        if yaml is None:
            # PyYAML is required to load YAML quiz files
            return []
        # Load file content, strip any leading non-YAML docstrings before '---'
        with open(path, encoding='utf-8') as f:
            content = f.read()
        # If Python-style docstring or other preamble exists, skip to first '---'
        if '---' in content:
            lines = content.splitlines()
            for idx, line in enumerate(lines):
                if line.strip() == '---':
                    content = '\n'.join(lines[idx:])
                    break
        # Parse all YAML documents
        docs = list(yaml.safe_load_all(content))
        raw = docs[0] if docs else {}
        # If first document is not question data (e.g., a docstring), use second
        if not isinstance(raw, (list, dict)) and len(docs) > 1:
            raw = docs[1] or {}
        # Flatten nested 'prompts' sections into top-level question entries
        if isinstance(raw, list):
            flattened = []
            for section in raw:
                if isinstance(section, dict) and 'prompts' in section and isinstance(section['prompts'], list):
                    for prompt in section['prompts']:
                        # Copy all data from prompt to preserve all fields
                        entry = prompt.copy()

                        # Map legacy keys
                        if 'question_type' in entry:
                            entry['type'] = entry.pop('question_type')
                        if 'starting_yaml' in entry:
                            entry['initial_yaml'] = entry.pop('starting_yaml')

                        # Inherit category from section, overriding any on the prompt
                        if 'category' in section:
                            entry['category'] = section.get('category')
                        flattened.append(entry)
                else:
                    flattened.append(section)
            raw = flattened
        # Normalize legacy 'question' key to 'prompt' and flatten nested metadata
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    if 'question' in item:
                        item['prompt'] = item.pop('question')
                    if 'metadata' in item and isinstance(item['metadata'], dict):
                        nested = item.pop('metadata')
                        for k, v in nested.items():
                            if k not in item:
                                item[k] = v
        module = raw.get('module') if isinstance(raw, dict) else None
        module = module or os.path.splitext(os.path.basename(path))[0]
        questions: List[Question] = []
        # Flat list of question dicts
        # Flat list of question dicts: allow explicit 'id' in item or fallback to module::index
        if isinstance(raw, list) and raw and isinstance(raw[0], dict):
            for idx, item in enumerate(raw):
                # Use explicit id if provided, else default to module::index
                qid = item.get('id') or f"{module}::{idx}"
                # Determine validation steps: explicit validations, then legacy 'answer'/'response', then 'answers' list
                steps_data = item.get('validation_steps', []) or item.get('validations', [])
                validation_steps = [
                    ValidationStep(cmd=v.get('cmd', ''), matcher=v.get('matcher', {}))
                    for v in steps_data
                ]
                # Legacy fallback: use 'answer' or 'response'
                if not validation_steps:
                    cmd = item.get('answer') or item.get('response')
                    if cmd:
                        validation_steps.append(ValidationStep(cmd=cmd, matcher={}))
                # Fallback: use 'answers' list entries as individual validation steps
                if not validation_steps and 'answers' in item and isinstance(item.get('answers'), list):
                    for ans in item.get('answers'):
                        if isinstance(ans, str) and ans:
                            validation_steps.append(ValidationStep(cmd=ans, matcher={}))

                initial_files = item.get('initial_files', {})
                if not initial_files and 'initial_yaml' in item:
                    initial_files['exercise.yaml'] = item['initial_yaml']

                questions.append(Question(
                    id=qid,
                    type=item.get('type') or 'command',
                    schema_category=item.get('schema_category'),
                    subject_matter=item.get('subject_matter'),
                    # Include any provided correct YAML for edit questions
                    correct_yaml=item.get('correct_yaml'),
                    prompt=item.get('prompt', ''),
                    pre_shell_cmds=item.get('pre_shell_cmds') or item.get('initial_cmds', []),
                    initial_files=initial_files,
                    validation_steps=validation_steps,
                    explanation=item.get('explanation'),
                    categories=item.get('categories', []),
                    difficulty=item.get('difficulty'),
                    review=item.get('review', False),
                    metadata={
                        k: v for k, v in item.items()
                        if k not in (
                            'id', 'type', 'schema_category', 'subject_matter', 'correct_yaml',
                            'prompt', 'runner', 'initial_cmds', 'initial_yaml',
                            'validations', 'explanation', 'categories', 'difficulty',
                            'pre_shell_cmds', 'initial_files', 'validation_steps',
                            'answer', 'response', 'review', 'solution_file'
                        )
                    }
                ))
            return questions
        # Fallback to standard 'questions' key in dict
        # Fallback to standard 'questions' key in dict: support explicit 'id'
        if isinstance(raw, dict) and 'questions' in raw:
            for idx, item in enumerate(raw.get('questions', [])):
                if isinstance(item, dict):
                    # Support legacy 'question' as 'prompt'
                    if 'question' in item:
                        item['prompt'] = item.pop('question')
                    # Flatten nested metadata blocks
                    if 'metadata' in item and isinstance(item['metadata'], dict):
                        nested = item.pop('metadata')
                        for k, v in nested.items():
                            if k not in item:
                                item[k] = v
                # Use explicit id if provided, else default to module::index
                qid = item.get('id') or f"{module}::{idx}"
                # Populate new schema, falling back to legacy fields
                steps_data = item.get('validation_steps') or item.get('validations', [])
                validation_steps = [
                    ValidationStep(cmd=v.get('cmd', ''), matcher=v.get('matcher', {}))
                    for v in steps_data
                ]
                initial_files = item.get('initial_files', {})
                if not initial_files and 'initial_yaml' in item:
                    initial_files['exercise.yaml'] = item['initial_yaml']

                questions.append(Question(
                    id=qid,
                    type=item.get('type') or 'command',
                    schema_category=item.get('schema_category'),
                    subject_matter=item.get('subject_matter'),
                    # Include any provided correct YAML
                    correct_yaml=item.get('correct_yaml'),
                    prompt=(item.get('prompt') or item.get('question', '')),
                    pre_shell_cmds=item.get('pre_shell_cmds') or item.get('initial_cmds', []),
                    initial_files=initial_files,
                    validation_steps=validation_steps,
                    explanation=item.get('explanation'),
                    categories=item.get('categories', []),
                    difficulty=item.get('difficulty'),
                    review=item.get('review', False),
                    metadata={
                        k: v for k, v in item.items()
                        if k not in (
                            'id', 'type', 'schema_category', 'subject_matter', 'correct_yaml',
                            'prompt', 'question', 'runner', 'initial_cmds', 'initial_yaml',
                            'validations', 'explanation', 'categories', 'difficulty',
                            'pre_shell_cmds', 'initial_files', 'validation_steps',
                            'review', 'solution_file'
                        )
                    }
                ))
        return questions
