"""
Loader for YAML-based question files under question-data/yaml.
"""
import os
try:
    import yaml
except ImportError:
    yaml = None
from typing import List
from kubelingo.modules.base_loader import BaseLoader
from kubelingo.question import Question, ValidationStep
import json
from kubelingo.utils.config import JSON_DIR

class YAMLLoader(BaseLoader):
    """Discovers and parses YAML question modules."""
    DATA_DIR = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', '..', 'question-data', 'yaml')
    )

    def discover(self) -> List[str]:
        if not os.path.isdir(self.DATA_DIR):
            return []
        return [
            os.path.join(self.DATA_DIR, fname)
            for fname in os.listdir(self.DATA_DIR)
            if fname.endswith(('.yaml', '.yml'))
        ]

    def load_file(self, path: str) -> List[Question]:
        # Load and normalize YAML file into Question objects
        if yaml is None:
            # Cannot process YAML files without PyYAML
            # Fallback for Vim quiz: load JSON counterpart if available
            if os.path.basename(path).startswith('vim_quiz'):
                try:
                    from kubelingo.modules.json_loader import JSONLoader
                    json_path = os.path.join(JSON_DIR, 'vim.json')
                    return JSONLoader().load_file(json_path)
                except Exception:
                    pass
            return []
        # Load all YAML documents (skip leading docstring sections)
        with open(path, encoding='utf-8') as f:
            docs = list(yaml.safe_load_all(f))
        raw = docs[0] if docs else {}
        # If first document is not question data (e.g., a docstring), use next
        if not isinstance(raw, (list, dict)) and len(docs) > 1:
            raw = docs[1] or {}
        # Flatten nested metadata blocks: if items have a 'metadata' dict, merge its fields
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict) and 'metadata' in item and isinstance(item['metadata'], dict):
                    nested = item.pop('metadata')
                    for k, v in nested.items():
                        # Do not overwrite existing top-level keys
                        if k not in item:
                            item[k] = v
        module = raw.get('module') if isinstance(raw, dict) else None
        module = module or os.path.splitext(os.path.basename(path))[0]
        questions: List[Question] = []
        # Flat list of question dicts
        if isinstance(raw, list) and raw and isinstance(raw[0], dict):
            # Detect Vim quiz to merge expected responses from JSON
            is_vim = os.path.basename(path).startswith('vim_quiz')
            vim_json = []
            if is_vim:
                try:
                    vim_json = json.load(open(os.path.join(JSON_DIR, 'vim.json'), encoding='utf-8'))
                except Exception:
                    vim_json = []
            for idx, item in enumerate(raw):
                qid = f"{module}::{idx}"
                # Populate new schema, falling back to legacy fields
                steps_data = item.get('validation_steps') or item.get('validations', [])
                validation_steps = [
                    ValidationStep(cmd=v.get('cmd', ''), matcher=v.get('matcher', {}))
                    for v in steps_data
                ]
                # Legacy: Use 'answer' or 'response' as a validation if others don't exist
                if not validation_steps:
                    cmd = item.get('answer') or item.get('response')
                    if cmd:
                        validation_steps.append(ValidationStep(cmd=cmd, matcher={}))
                # For Vim quiz, override from JSON responses
                if is_vim and not validation_steps and idx < len(vim_json):
                    cmd = vim_json[idx].get('response')
                    if cmd:
                        validation_steps = [ValidationStep(cmd=cmd, matcher={})]

                initial_files = item.get('initial_files', {})
                if not initial_files and 'initial_yaml' in item:
                    initial_files['exercise.yaml'] = item['initial_yaml']

                questions.append(Question(
                    id=qid,
                    type=item.get('type') or 'command',
                    prompt=(item.get('prompt') or item.get('question', '')),
                    pre_shell_cmds=item.get('pre_shell_cmds') or item.get('initial_cmds', []),
                    initial_files=initial_files,
                    validation_steps=validation_steps,
                    explanation=item.get('explanation'),
                    categories=item.get('categories', []),
                    difficulty=item.get('difficulty'),
                    metadata={
                        k: v for k, v in item.items()
                        if k not in (
                            'prompt', 'runner', 'initial_cmds', 'initial_yaml',
                            'validations', 'explanation', 'categories', 'difficulty',
                            'pre_shell_cmds', 'initial_files', 'validation_steps',
                            'answer', 'response'
                        )
                    }
                ))
            return questions
        # Fallback to standard 'questions' key in dict
        if isinstance(raw, dict) and 'questions' in raw:
            for idx, item in enumerate(raw.get('questions', [])):
                # Flatten nested metadata for each question
                if isinstance(item, dict) and 'metadata' in item and isinstance(item['metadata'], dict):
                    nested = item.pop('metadata')
                    for k, v in nested.items():
                        if k not in item:
                            item[k] = v
                qid = f"{module}::{idx}"
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
                    prompt=(item.get('prompt') or item.get('question', '')),
                    pre_shell_cmds=item.get('pre_shell_cmds') or item.get('initial_cmds', []),
                    initial_files=initial_files,
                    validation_steps=validation_steps,
                    explanation=item.get('explanation'),
                    categories=item.get('categories', []),
                    difficulty=item.get('difficulty'),
                    metadata={
                        k: v for k, v in item.items()
                        if k not in (
                            'prompt', 'runner', 'initial_cmds', 'initial_yaml',
                            'validations', 'explanation', 'categories', 'difficulty',
                            'pre_shell_cmds', 'initial_files', 'validation_steps'
                        )
                    }
                ))
        return questions
