import os
import re

from kubelingo.utils.config import LOGS_DIR

# Directory to store per-question transcripts
TRANSCRIPTS_DIR = os.path.join(LOGS_DIR, 'transcripts')

def _ensure_dir():
    """Ensure base transcripts directory (with optional session subdir) exists."""
    session_id = os.getenv('KUBELINGO_SESSION_ID') or ''
    base = TRANSCRIPTS_DIR
    if session_id:
        base = os.path.join(TRANSCRIPTS_DIR, session_id)
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:
        pass
    return base

def _sanitize_qid(qid: str) -> str:
    # Replace characters unsafe for filenames
    name = qid.replace('::', '__')
    # Remove any remaining non-alphanumeric or underscore
    return re.sub(r'[^A-Za-z0-9_\-\.]+', '_', name)

def save_transcript(qid: str, content: str) -> str:
    """
    Save the full transcript for a question to persistent storage.
    """
    """
    Save the full transcript for a question and return its file path.
    Transcripts are stored under logs/transcripts/<session_id>/<qid>.log
    """
    base = _ensure_dir()
    fname = _sanitize_qid(qid) + '.log'
    path = os.path.join(base, fname)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return path
    except Exception:
        return ''

def load_transcript(qid: str) -> str:
    """
    Load transcript content for a given question id, or return empty string if not found.
    """
    fname = _sanitize_qid(qid) + '.log'
    path = os.path.join(TRANSCRIPTS_DIR, fname)
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return ''
    return ''

def evaluate_transcript(transcript_path: str, validation_steps) -> (bool, list):
    """
    Evaluate a transcript file against a list of validation steps.
    Each step can be a dict or ValidationStep with cmd and matcher.
    Returns (all_pass, details_list).
    """
    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            transcript = f.read()
    except Exception:
        return False, [f"Unable to read transcript: {transcript_path}"]
    all_pass = True
    details = []
    for vs in validation_steps:
        if hasattr(vs, 'cmd') and hasattr(vs, 'matcher'):
            cmd, matcher = vs.cmd, vs.matcher
        else:
            cmd, matcher = vs.get('cmd', ''), vs.get('matcher', {})
        passed = False
        reason = ''
        if 'contains' in matcher:
            if matcher['contains'] in transcript:
                passed = True
            else:
                reason = f"Missing text: {matcher['contains']}"
        elif 'regex' in matcher:
            try:
                if re.search(matcher['regex'], transcript, re.MULTILINE):
                    passed = True
                else:
                    reason = f"Regex not matched: {matcher['regex']}"
            except re.error:
                reason = f"Invalid regex: {matcher.get('regex')}"
        else:
            if cmd and cmd in transcript:
                passed = True
            else:
                reason = f"Missing command: {cmd}"
        details.append((cmd, passed, reason))
        if not passed:
            all_pass = False
    return all_pass, details

def check_answer(q: dict) -> (bool, list):
    """
    Check a question's answer by inspecting its saved transcript.
    Returns (is_correct, details) where details is a list of strings.
    """
    transcript = load_transcript(q.get('id', ''))
    if not transcript:
        return False, ['No transcript found. Please start the exercise to generate a transcript.']
    # Build validation steps
    steps = []
    # Legacy: q may have 'validations' or 'validation_steps'
    raw_steps = q.get('validation_steps') or q.get('validations') or []
    # For command-type questions lacking explicit validations, match the expected response
    if not raw_steps and q.get('type') == 'command' and q.get('response'):
        raw_steps = [{'cmd': q.get('response', ''), 'matcher': {'contains': q.get('response', '')}}]
    for item in raw_steps:
        # item could be ValidationStep or dict
        if hasattr(item, 'cmd') and hasattr(item, 'matcher'):
            cmd = item.cmd
            matcher = item.matcher
        else:
            cmd = item.get('cmd', '')
            matcher = item.get('matcher', {})
        steps.append((cmd, matcher))
    # Evaluate each step
    all_pass = True
    details = []
    for cmd, matcher in steps:
        passed = False
        reason = ''
        # Default: substring match of cmd
        if 'contains' in matcher:
            if matcher['contains'] in transcript:
                passed = True
            else:
                reason = f"Transcript does not contain expected text: {matcher['contains']}"
        elif 'regex' in matcher:
            try:
                if re.search(matcher['regex'], transcript, re.MULTILINE):
                    passed = True
                else:
                    reason = f"Transcript does not match regex: {matcher['regex']}"
            except re.error:
                reason = f"Invalid regex in matcher: {matcher.get('regex')}"
        else:
            # Fallback to looking for the command line
            if cmd and cmd in transcript:
                passed = True
            else:
                reason = f"Transcript does not include command: {cmd}"
        if passed:
            details.append(f"PASS: {cmd}")
        else:
            details.append(f"FAIL: {cmd} -> {reason}")
            all_pass = False
    return all_pass, detailsimport os
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any

from kubelingo.question import ValidationStep
from kubelingo.utils.config import LOGS_DIR


def save_transcript(question_id: str, content: str) -> Optional[Path]:
    """
    Saves a session transcript to a structured directory.
    logs/transcripts/<session_id>/<question_id>.log
    """
    session_id = os.environ.get('KUBELINGO_SESSION_ID')
    if not session_id:
        return None  # Cannot save without a session ID

    # Sanitize question_id to be a valid filename
    safe_question_id = "".join(c for c in question_id if c.isalnum() or c in ('-', '_')).rstrip()
    if not safe_question_id:
        safe_question_id = "unidentified_question"

    filename = f"{safe_question_id}.log"

    transcript_dir = Path(LOGS_DIR) / "transcripts" / session_id
    transcript_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = transcript_dir / filename

    try:
        transcript_path.write_text(content, encoding='utf-8')
        return transcript_path
    except IOError:
        # Consider logging this error
        return None


def evaluate_transcript(validation_steps: List[ValidationStep]) -> List[Dict[str, Any]]:
    """
    Runs deterministic validation steps and returns results as dicts.

    NOTE: This function currently executes the validation commands in the current
    working directory. It does NOT parse a transcript file. The name is
    set for future compatibility with a true transcript-parsing evaluator.
    """
    step_results_dicts: List[Dict[str, Any]] = []
    if not validation_steps:
        return []

    for step in validation_steps:
        proc = subprocess.run(step.cmd, shell=True, check=False, capture_output=True, text=True)
        expected_code = step.matcher.get('exit_code', 0)
        success = (proc.returncode == expected_code)
        step_results_dicts.append({
            "step": step,
            "success": success,
            "stdout": proc.stdout or '',
            "stderr": proc.stderr or ''
        })

    return step_results_dicts
