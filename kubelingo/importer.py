import os
import json
import yaml
from typing import List, Dict, Any
from .schema import normalize_question_dict, write_question_file
from .utils import QUESTIONS_STORED_DIR

SUPPORTED_FILE_TYPES = {'.yaml', '.yml', '.json'}


def _collect_from_yaml_obj(obj: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if isinstance(obj, dict):
        if 'questions' in obj and isinstance(obj['questions'], list):
            for q in obj['questions']:
                if isinstance(q, dict):
                    out.append(normalize_question_dict(q, q.get('topic')))
        else:
            out.append(normalize_question_dict(obj, obj.get('topic')))
    elif isinstance(obj, list):
        for q in obj:
            if isinstance(q, dict):
                out.append(normalize_question_dict(q, q.get('topic')))
    return out


def _load_file(path: str) -> List[Dict[str, Any]]:
    ext = os.path.splitext(path)[1].lower()
    if ext in ('.yaml', '.yml'):
        with open(path, 'r') as f:
            obj = yaml.safe_load(f)
        return _collect_from_yaml_obj(obj)
    if ext == '.json':
        with open(path, 'r') as f:
            obj = json.load(f)
        return _collect_from_yaml_obj(obj)
    return []


def import_from_path(path: str) -> int:
    """Import questions from a file or directory. Returns number imported."""
    count = 0
    if os.path.isdir(path):
        for root, _, files in os.walk(path):
            for name in files:
                ext = os.path.splitext(name)[1].lower()
                if ext not in SUPPORTED_FILE_TYPES:
                    continue
                fpath = os.path.join(root, name)
                try:
                    qs = _load_file(fpath)
                except Exception:
                    qs = []
                for q in qs:
                    try:
                        write_question_file(q, QUESTIONS_STORED_DIR)
                        count += 1
                    except Exception:
                        pass
        return count
    else:
        ext = os.path.splitext(path)[1].lower()
        if ext not in SUPPORTED_FILE_TYPES:
            return 0
        try:
            qs = _load_file(path)
        except Exception:
            qs = []
        for q in qs:
            try:
                write_question_file(q, QUESTIONS_STORED_DIR)
                count += 1
            except Exception:
                pass
        return count


def import_from_url(url: str) -> int:
    """Placeholder for URL import. Returns number imported (0 for now)."""
    # TODO: Implement requests/BeautifulSoup-based import
    return 0

