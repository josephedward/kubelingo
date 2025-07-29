"""
Loader for Markdown-based question files under question-data/md.
"""
import os
try:
    import yaml
except ImportError:
    yaml = None
from typing import List
from kubelingo.modules.base_loader import BaseLoader
from kubelingo.question import Question, ValidationStep

class MDLoader(BaseLoader):
    """Discovers and parses Markdown question modules with YAML front-matter."""
    DATA_DIR = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', '..', 'question-data', 'md')
    )

    def discover(self) -> List[str]:
        if not os.path.isdir(self.DATA_DIR):
            return []
        return [
            os.path.join(self.DATA_DIR, fname)
            for fname in os.listdir(self.DATA_DIR)
            if fname.endswith('.md')
        ]

    def load_file(self, path: str) -> List[Question]:
        # Read file and split front-matter
        text = open(path, encoding='utf-8').read()
        fm_data = {}
        body = text
        if text.startswith('---'):
            parts = text.split('---', 2)
            if len(parts) >= 3:
                _, fm_text, body = parts
                try:
                    fm_data = yaml.safe_load(fm_text) or {}
                except Exception:
                    fm_data = {}
        module = fm_data.get('module') or os.path.splitext(os.path.basename(path))[0]
        questions: List[Question] = []
        # First, try front-matter defined questions
        for idx, item in enumerate(fm_data.get('questions', [])):
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
        if questions:
            return questions
        # Fallback: parse headings and code fences from body
        lines = body.splitlines()
        # Identify question headings (level 3 '### ')
        headings = [i for i, l in enumerate(lines) if l.startswith('### ')]
        for qidx, start in enumerate(headings):
            end = headings[qidx + 1] if qidx + 1 < len(headings) else len(lines)
            prompt = lines[start][4:].strip()
            # Extract the first fenced code block in the section
            code_lines: List[str] = []
            in_code = False
            for l in lines[start + 1:end]:
                if l.strip().startswith('```'):
                    if not in_code:
                        in_code = True
                        continue
                    else:
                        break
                if in_code:
                    code_lines.append(l)
            cmd = '\n'.join(code_lines).strip()
            vals = [ValidationStep(cmd=cmd, matcher={})] if cmd else []
            questions.append(Question(
                id=f"{module}::{qidx}",
                prompt=prompt,
                runner='shell',
                initial_cmds=[],
                initial_yaml=None,
                validations=vals,
                explanation=None,
                categories=[],
                difficulty=None,
                metadata={}
            ))
        return questions