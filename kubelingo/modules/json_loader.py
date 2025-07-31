"""
Loader for JSON-based question files under question-data/json.
"""
import os
import json
from typing import List
from kubelingo.modules.base_loader import BaseLoader
from kubelingo.question import Question, ValidationStep

class JSONLoader(BaseLoader):
    """Discovers and parses JSON question modules."""
    DATA_DIR = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', '..', 'question-data', 'json')
    )

    def discover(self) -> List[str]:
        if not os.path.isdir(self.DATA_DIR):
            return []
        return [
            os.path.join(self.DATA_DIR, fname)
            for fname in os.listdir(self.DATA_DIR)
            if fname.endswith('.json')
        ]

    def load_file(self, path: str) -> List[Question]:
        # Load and normalize JSON file into Question objects
        # Load JSON content; if top-level is a list, wrap it under a 'questions' key
        with open(path, encoding='utf-8') as f:
            raw = json.load(f)
        if isinstance(raw, list):
            raw = {'questions': raw}
        module = raw.get('module') or os.path.splitext(os.path.basename(path))[0]
        questions: List[Question] = []
        for idx, item in enumerate(raw.get('questions', [])):
            qid = f"{module}::{idx}"
            # Populate new schema, falling back to legacy fields
            steps_data = item.get('validation_steps') or item.get('validations', [])
            validation_steps = [
                ValidationStep(cmd=v.get('cmd', ''), matcher=v.get('matcher', {}))
                for v in steps_data
            ]
            # Fallback: if no validation steps, use 'response' or 'answer' as default
            if not validation_steps:
                resp = item.get('response') or item.get('answer')
                if resp:
                    validation_steps.append(ValidationStep(cmd=resp, matcher={'exit_code': 0}))
            initial_files = item.get('initial_files', {})
            if not initial_files and 'initial_yaml' in item:
                initial_files['exercise.yaml'] = item['initial_yaml']

            # Build Question
            questions.append(Question(
                id=qid,
                type=item.get('type') or item.get('runner') or 'command',
                prompt=item.get('prompt', ''),
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
