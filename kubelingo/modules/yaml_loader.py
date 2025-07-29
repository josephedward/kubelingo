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
        with open(path, encoding='utf-8') as f:
            raw = yaml.safe_load(f) or {}
        module = raw.get('module') or os.path.splitext(os.path.basename(path))[0]
        questions: List[Question] = []
        for idx, item in enumerate(raw.get('questions', [])):
            qid = f"{module}::{idx}"
            vals: List[ValidationStep] = []
            for v in item.get('validations', []):
                vals.append(ValidationStep(cmd=v.get('cmd', ''), matcher=v.get('matcher', {})))
            questions.append(Question(
                id=qid,
                prompt=item.get('prompt', ''),
                runner=item.get('runner', 'shell'),
                initial_cmds=item.get('initial_cmds', []),
                initial_yaml=item.get('initial_yaml'),
                validations=vals,
                explanation=item.get('explanation'),
                categories=item.get('categories', []),
                difficulty=item.get('difficulty'),
                metadata={k: v for k, v in item.items()
                          if k not in ('prompt', 'runner', 'initial_cmds',
                                       'initial_yaml', 'validations',
                                       'explanation', 'categories', 'difficulty')}
            ))
        return questions