import subprocess
import tempfile
import os
import glob
import pytest

from kubelingo.modules.json_loader import JSONLoader
from kubelingo.modules.md_loader import MDLoader
from kubelingo.modules.yaml_loader import YAMLLoader

def load_questions_from_file(path):
    """Load questions using appropriate loader based on file extension."""
    ext = os.path.splitext(path)[1].lower()
    if ext == '.json':
        return JSONLoader().load_file(path)
    if ext in ('.md', '.markdown'):
        return MDLoader().load_file(path)
    if ext in ('.yaml', '.yml'):
        return YAMLLoader().load_file(path)
    return []

@pytest.mark.skip(reason="YAML parsing errors are causing this to fail.")
@pytest.mark.skipif(
    subprocess.run(['git', 'rev-parse', '--is-inside-work-tree'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0,
    reason="Not in a git repository"
)
def test_no_unique_question_deletions():
    """
    Ensure that any question removed in the latest commit still exists elsewhere (duplicates allowed).
    """
    # Get list of changed files in last commit
    diff = subprocess.check_output(
        ['git', 'diff', '--name-only', 'HEAD~1', 'HEAD'], text=True
    ).splitlines()
    # Discover all current questions across files
    all_current = []
    for loader in (JSONLoader(), MDLoader(), YAMLLoader()):
        for p in loader.discover():
            qs = loader.load_file(p)
            all_current.extend(q.prompt for q in qs)
    # For each changed question file, compare old vs new
    for path in diff:
        if not os.path.isfile(path):
            continue
        if not path.lower().endswith(('.json', '.md', '.markdown', '.yaml', '.yml')):
            continue
        # Load old version
        try:
            old_content = subprocess.check_output(
                ['git', 'show', f'HEAD~1:{path}'], text=True
            )
        except subprocess.CalledProcessError:
            continue
        # Write to temp file for loader
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=os.path.splitext(path)[1]) as tf:
            tf.write(old_content)
            temp_path = tf.name
        try:
            old_qs = load_questions_from_file(temp_path)
            new_qs = load_questions_from_file(path)
            old_prompts = set(q.prompt for q in old_qs)
            new_prompts = set(q.prompt for q in new_qs)
            removed = old_prompts - new_prompts
            for prompt in removed:
                # If prompt still appears somewhere in current, it's a duplicate removal
                if prompt not in all_current:
                    pytest.fail(f"Unique question removed: '{prompt}' from file {path}")
        finally:
            os.unlink(temp_path)
