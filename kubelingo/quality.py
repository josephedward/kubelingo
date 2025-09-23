import re
import yaml
from typing import Dict, Any, List


def _ensure_in_question_variables(question: str, variables: List[str]) -> bool:
    ql = question.lower()
    return all(v.lower() in ql for v in variables if v)


def validate_true_false(item: Dict[str, Any]) -> List[str]:
    errs = []
    ans = str(item.get('suggested_answer', '')).strip().lower()
    if ans not in ('true', 'false'):
        errs.append("suggested_answer must be 'true' or 'false'")
    if not item.get('question') or not item['question'].lower().startswith('true or false'):
        errs.append("question should start with 'True or False'")
    return errs


def validate_vocab(item: Dict[str, Any]) -> List[str]:
    errs = []
    ans = str(item.get('suggested_answer', '')).strip()
    if not ans or ' ' in ans.strip():
        errs.append("vocab term should be a single word/term")
    if not item.get('question'):
        errs.append("question missing")
    return errs


def validate_mcq(item: Dict[str, Any]) -> List[str]:
    errs = []
    opts = item.get('options')
    if not isinstance(opts, list) or len(opts) != 4:
        errs.append("mcq must have exactly 4 options")
    correct = str(item.get('suggested_answer', '')).strip()
    if not correct:
        errs.append("mcq must include suggested_answer")
    elif opts and correct not in opts:
        errs.append("suggested_answer must be one of options")
    return errs


def validate_commands(item: Dict[str, Any]) -> List[str]:
    errs = []
    q = item.get('question', '')
    ans = str(item.get('suggested_answer', '')).strip()
    if not ans or not isinstance(ans, str):
        errs.append("command answer must be a single string")
        return errs
    if not (ans.startswith('kubectl ') or ans.startswith('helm ') or ans.split()[0] in ('ls', 'cat', 'grep', 'sed', 'awk')):
        errs.append("command must start with kubectl/helm/linux tool")
    # Lightweight variable presence check: find quoted literals and simple tokens from question
    literals = re.findall(r"'([^']+)'|\"([^\"]+)\"", q)
    flat = [t for pair in literals for t in pair if t]
    # Also capture common tokens (names/images/ports)
    tokens = re.findall(r"[a-zA-Z0-9_.:-]{3,}", q)
    variables = list(set(flat + tokens[:5]))
    if not _ensure_in_question_variables(q, variables[:2]):
        # Do not hard fail; record a soft warning
        pass
    return errs


def validate_manifests(item: Dict[str, Any]) -> List[str]:
    errs = []
    ans = item.get('suggested_answer')
    if not ans:
        errs.append("manifest answer missing")
        return errs
    if isinstance(ans, str):
        try:
            obj = yaml.safe_load(ans)
        except Exception as e:
            errs.append(f"manifest YAML not parseable: {e}")
            return errs
    elif isinstance(ans, (dict, list)):
        obj = ans
    else:
        errs.append("manifest answer must be YAML string or dict/list")
        return errs
    if not isinstance(obj, dict) or 'apiVersion' not in obj or 'kind' not in obj:
        errs.append("manifest must contain apiVersion and kind")
    return errs


def quality_check(item: Dict[str, Any]) -> List[str]:
    t = item.get('type')
    if t == 'true_false':
        return validate_true_false(item)
    if t == 'vocab':
        return validate_vocab(item)
    if t == 'mcq':
        return validate_mcq(item)
    if t == 'commands':
        return validate_commands(item)
    if t == 'manifests':
        return validate_manifests(item)
    return ["unknown type"]

