import os
import yaml
import re
import sys
import textwrap
import argparse
import openai
import webbrowser
from thefuzz import fuzz

from kubelingo.kubelingo import _get_llm_model, get_normalized_question_text, validate_manifest
import scripts.format_questions as fq
import scripts.manage_questions as mq
from kubelingo.utils import USER_DATA_DIR, ISSUES_FILE, MISSED_QUESTIONS_FILE, ensure_user_data_dir

def load_questions_from_list(list_file):
    if not os.path.exists(list_file):
        return []
    with open(list_file, 'r') as file:
        try:
            return yaml.safe_load(file) or []
        except yaml.YAMLError:
            return []

def save_questions_to_list(list_file, questions):
    ensure_user_data_dir()
    with open(list_file, 'w') as f:
        yaml.dump(questions, f)

def move_issues_from_missed():
    print("Loading issues from issues.yaml...")
    issues = load_questions_from_list(ISSUES_FILE)
    print(f"Found {len(issues)} issues.")

    print("Loading missed questions from missed_questions.yaml...")
    missed_questions = load_questions_from_list(MISSED_QUESTIONS_FILE)
    print(f"Found {len(missed_questions)} missed questions.")

    initial_missed_count = len(missed_questions)
    questions_removed_count = 0
    updated_missed_questions = []

    issue_question_texts = {get_normalized_question_text(issue) for issue in issues}

    for mq in missed_questions:
        if get_normalized_question_text(mq) in issue_question_texts:
            print(f"Removing missed question (flagged as issue): {mq.get('question')[:50]}...")
            questions_removed_count += 1
        else:
            updated_missed_questions.append(mq)

    if questions_removed_count > 0:
        print(f"Removed {questions_removed_count} questions from missed_questions.yaml.")
        save_questions_to_list(MISSED_QUESTIONS_FILE, updated_missed_questions)
        print("Updated missed_questions.yaml saved.")
    else:
        print("No questions flagged as issues found in missed questions. No changes made to missed_questions.yaml.")

    print("Process complete.")



# --- Functions for formatting questions ---

def format_solution_yaml(data):
    # Recursively convert solution strings containing YAML into native mappings/lists
    if isinstance(data, dict):
        for key, value in list(data.items()):
            # Handle single solution entries
            # Convert multi-line YAML solution string into native mapping or list
            if key == 'solution' and isinstance(value, str) and '\n' in value:
                normalized = textwrap.dedent(value).strip()
                try:
                    parsed = yaml.safe_load(normalized)
                    # Replace only if parsed YAML is a mapping or sequence
                    if isinstance(parsed, (dict, list)):
                        data[key] = parsed
                    # otherwise keep the original string
                except yaml.YAMLError as e:
                    print(f"Warning: Could not parse YAML in 'solution'. Keeping original. Error: {e}", file=sys.stderr)
            # Handle multiple solutions entries
            # Handle lists of solutions, converting multi-line YAML strings
            elif key == 'suggestion' and isinstance(value, list):
                new_list = []
                for item in value:
                    if isinstance(item, str) and '\n' in item:
                        normalized = textwrap.dedent(item).strip()
                        try:
                            parsed = yaml.safe_load(normalized)
                            if isinstance(parsed, (dict, list)):
                                new_list.append(parsed)
                                continue
                        except yaml.YAMLError:
                            pass
                    new_list.append(item)
                data[key] = new_list
                for item in data[key]:
                    format_solution_yaml(item)
            else:
                format_solution_yaml(value)
    elif isinstance(data, list):
        for item in data:
            format_solution_yaml(item)
    return data

def format_yaml_solution_main(base_path):
    paths = []
    if os.path.isdir(base_path):
        for root, dirs, files in os.walk(base_path):
            for fname in files:
                if fname.endswith(('.yaml', '.yml')):
                    paths.append(os.path.join(root, fname))
    else:
        if not os.path.exists(base_path):
            print(f"Error: Path not found: {base_path}", file=sys.stderr)
            sys.exit(1)
        paths = [base_path]
    exit_code = 0
    for file_path in paths:
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            data = yaml.safe_load(content)
            updated = format_solution_yaml(data)
            updated_content = yaml.safe_dump(updated, indent=2, default_flow_style=False, sort_keys=False)
            with open(file_path, 'w') as f:
                f.write(updated_content)
            print(f"Formatted YAML solutions in {file_path}")
        except Exception as e:
            print(f"Error processing {file_path}: {e}", file=sys.stderr)
            exit_code = 1
    return exit_code

def convert_text(text):
    # Match single-quoted multi-line manifest solutions
    # Pattern: indent, - 'apiVersion... until closing quote
    pattern = re.compile(
        r"(?P<indent>^[ ]*)- '(?P<content>[\s\S]*?)'", re.MULTILINE
    )
    def repl(m):
        indent = m.group('indent')
        content = m.group('content')
        # Split into lines and remove leading/trailing whitespace
        lines = content.splitlines()
        trimmed = [line.strip() for line in lines if line.strip()]
        # Build block literal
        block = f"{indent}- |-\n"
        for line in trimmed:
            block += f"{indent}  {line}\n"
        return block.rstrip("\n")
    return re.sub(pattern, repl, text)

def process_file_manifest(path):
    try:
        text = open(path, 'r', encoding='utf-8').read()
    except Exception:
        return
    new_text = convert_text(text)
    if new_text != text:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_text)
        print(f"Formatted manifest solutions in {path}")

def format_manifest_solutions_main(targets):
    for target in targets:
        for root, _, files in os.walk(target):
            for fname in files:
                if fname.endswith(('.yaml', '.yml')):
                    process_file_manifest(os.path.join(root, fname))

# --- Functions from manage_questions.py ---

try:
    from googlesearch import search
except ImportError:
    search = None

# openai.api_key = os.getenv("OPENAI_API_KEY") # This line might cause issues if not handled carefully

def enhance_question_with_ai(question_text, solution_text):
    if not openai.api_key:
        raise RuntimeError("OpenAI API key not set. Please set the OPENAI_API_KEY environment variable")
    prompt = f"""You are a helpful assistant that rewrites user questions to include any details present in the solution but missing from the question.

Original question:
```
{question_text}
```

Solution:
```
{solution_text}
```

Return only the rewritten question text. If no changes are needed, return the original question unchanged."""
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Rewrite questions to include missing solution details."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    return response.choices[0].message.content.strip()

# Patterns mapping solution features to required question phrasing
PATTERNS = [
    {
        'pattern': re.compile(r'--dry-run\b'),
        'checks': [re.compile(r'without creating', re.IGNORECASE), re.compile(r'dry-run', re.IGNORECASE)],
        'append': ' without creating the resource'
    },
    {
        'pattern': re.compile(r'-o\s+yaml'),
        'checks': [re.compile(r'\bYAML\b', re.IGNORECASE)],
        'append': ' and output in YAML format'
    },
    {
        'pattern': re.compile(r'>\s*(?P<file>\S+)'),
        'checks': [re.compile(r'\bsave\b', re.IGNORECASE), re.compile(r'\bfile\b', re.IGNORECASE)],
        'append_template': ' and save it to a file named "{file}"'
    },
    {
        'pattern': re.compile(r'--replicas(?:=|

)(?P<num>\d+)'),
        'checks': [re.compile(r'\breplicas\b', re.IGNORECASE)],
        'append_template': ' with {num} replicas'
    },
]

def find_missing_details(question_text, solution_text):
    """Return list of phrases that should be appended to question_text."""
    missing = []
    for pat in PATTERNS:
        m = pat['pattern'].search(solution_text)
        if not m:
            continue
        # if any check phrase already in question, skip
        if any(ch.search(question_text) for ch in pat.get('checks', [])):
            continue
        # prepare append text
        if 'append' in pat:
            missing.append(pat['append'])
        elif 'append_template' in pat:
            gd = m.groupdict()
            try:
                missing.append(pat['append_template'].format(**gd))
            except Exception:
                missing.append(pat['append_template'])
    # Handle namespace in YAML suggestions
    if '\n' in solution_text and 'apiVersion' in solution_text:
        try:
            manifest = yaml.safe_load(solution_text)
            ns = manifest.get('metadata', {}).get('namespace')
            if ns and not re.search(r'\bnamespace\b', question_text, re.IGNORECASE):
                missing.append(f' in the "{ns}" namespace')
        except Exception:
            pass
    return missing

def process_file_for_enhancement(path, write=False):
    with open(path) as f:
        data = yaml.safe_load(f)
    if not data or 'questions' not in data:
        return
    updated = False
    for q in data['questions']:
        q_text = q.get('question', '') or ''
        sol = q.get('solution', '') or ''
        try:
            new_q = enhance_question_with_ai(q_text, sol)
            if new_q and new_q != q_text:
                q['question'] = new_q
                updated = True
        except Exception as e:
            print(f"Error enhancing {path}: {e}")
    if updated:
        if write:
            with open(path, 'w') as f:
                yaml.safe_dump(data, f, sort_keys=False)
            print(f'Updated {path}')
        else:
            print(f'{path} requires enhancements')

def get_source_from_consolidated(item):
    metadata = item.get('metadata', {}) or {}
    for key in ('links', 'source', 'citation'):
        if key in metadata and metadata[key]:
            val = metadata[key]
            # links may be a list
            return val[0] if isinstance(val, list) else val
    return None

def add_sources(consolidated_file, questions_dir):
    print(f"Loading consolidated questions from '{consolidated_file}'...")
    data = yaml.safe_load(open(consolidated_file)) or {}
    mapping = {}
    for item in data.get('questions', []):
        prompt = item.get('prompt') or item.get('question')
        src = get_source_from_consolidated(item)
        if prompt and src:
            mapping[prompt.strip()] = src
    print(f"Found {len(mapping)} source mappings.")
    # Update each question file
    for fname in os.listdir(questions_dir):
        if not fname.endswith('.yaml'):
            continue
        path = os.path.join(questions_dir, fname)
        topic = yaml.safe_load(open(path)) or {}
        qs = topic.get('questions') or []
        updated = 0
        for q in qs:
            if 'source' in q and q['source']:
                continue
            text = q.get('question','').strip()
            best, score = None, 0
            for prompt, src in mapping.items():
                r = fuzz.ratio(text, prompt)
                if r > score:
                    best, score = src, r
            if score > 95:
                q['source'] = best
                updated += 1
                print(f"  + Added source to '{text[:50]}...' -> {best}")
        if updated:
            yaml.dump(topic, open(path,'w'), sort_keys=False)
            print(f"Updated {updated} entries in {fname}.")
    print("Done adding sources.")

def check_sources(questions_dir):
    missing = 0
    for fname in os.listdir(questions_dir):
        if not fname.endswith('.yaml'):
            continue
        path = os.path.join(questions_dir, fname)
        data = yaml.safe_load(open(path)) or {}
        for i, q in enumerate(data.get('questions', []), start=1):
            if not q.get('source'):
                print(f"{fname}: question {i} missing 'source': {q.get('question','')[:80]}")
                missing += 1
    if missing == 0:
        print("All questions have a source.")
    else:
        print(f"{missing} questions missing sources.")

def interactive(questions_dir, auto_approve=False):
    for fname in os.listdir(questions_dir):
        if not fname.endswith('.yaml'):
            continue
        path = os.path.join(questions_dir, fname)
        data = yaml.safe_load(open(path)) or {}
        qs = data.get('questions', [])
        modified = False
        for idx, q in enumerate(qs, start=1):
            if q.get('source'):
                continue
            text = q.get('question','').strip()
            print(f"\nFile: {fname} | Question {idx}: {text}")
            if auto_approve:
                if not search:
                    print("  googlesearch not available.")
                    continue
                try:
                    results = list(search(f"kubernetes {text}", num_results=1))
                except Exception as e:
                    print(f"  Search error: {e}")
                    continue
                if results:
                    q['source'] = results[0]
                    print(f"  Auto-set source: {results[0]}")
                    modified = True
                continue
            # manual interactive search
            print("  Searching online for sources...")
            if not search:
                print("  Install googlesearch-python to enable search.")
                return
            try:
                results = list(search(f"kubernetes {text}", num_results=5))
            except Exception as e:
                print(f"  Search error: {e}")
                continue
            if not results:
                print("  No results found.")
                continue
            for i, url in enumerate(results, start=1):
                print(f"    {i}. {url}")
            choice = input("  Choose default [1] or enter number, [o]pen all, [s]kip: ").strip().lower()
            if choice == 'o':
                for url in results:
                    webbrowser.open(url)
                choice = '1'
            if choice.isdigit() and 1 <= int(choice) <= len(results):
                sel = results[int(choice)-1]
                q['source'] = sel
                print(f"  Selected source: {sel}")
                modified = True
        if modified:
            yaml.dump(data, open(path,'w'), sort_keys=False)
            print(f"Saved updates to {fname}.")
    print("Interactive session complete.")

def main():
    parser = argparse.ArgumentParser(
        description='Manage Kubernetes questions: enhance with AI or manage sources.'
    )
    parser.add_argument(
        '--dir', default='questions', help='Directory of question YAML files'
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Subparser for enhancement
    enhance_parser = subparsers.add_parser(
        'enhance', help='Enhance questions with AI'
    )
    enhance_parser.add_argument(
        '--write', action='store_true', help='Write updates back to files'
    )

    # Subparser for source management
    source_parser = subparsers.add_parser(
        'source', help='Manage question sources'
    )
    source_parser.add_argument(
        '--consolidated', help='Consolidated YAML with sources for add mode.'
    )
    source_group = source_parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        '--add', action='store_true', help='Add missing sources from consolidated file.'
    )
    source_group.add_argument(
        '--check', action='store_true', help='Check for missing sources.'
    )
    source_group.add_argument(
        '--interactive', action='store_true', help='Interactively find and assign sources.'
    )
    source_parser.add_argument(
        '--auto-approve', action='store_true',
        help='In interactive mode, auto-assign first search result.'
    )

    args = parser.parse_args()
    qdir = args.dir

    if args.command == 'enhance':
        for fn in sorted(os.listdir(qdir)):
            if fn.endswith('.yaml'):
                process_file_for_enhancement(os.path.join(qdir, fn), write=args.write)
    elif args.command == 'source':
        if args.add:
            if not args.consolidated:
                print("Error: --consolidated PATH is required for --add.")
                sys.exit(1)
            add_sources(args.consolidated, qdir)
        elif args.check:
            check_sources(qdir)
        elif args.interactive:
            interactive(qdir, args.auto_approve)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == '__main__':
    main()


# """
# Question generation module (qgen).
# Defines steps to generate a new Kubernetes question for a given section,
# using few-shot examples, LLM generation, duplication checks, field matching,
# source assignment, YAML/manifest formatting, and validation.
# """

class GenerationError(Exception):
    """General exception for generation failures."""
    pass

class DuplicateQuestionError(GenerationError):
    """Raised when the generated question duplicates an existing one."""
    pass

class MissingFieldsError(GenerationError):
    """Raised when required fields are missing in the generated question."""
    pass

def load_examples(path):
    """Load few-shot examples from a YAML file."""
    if not os.path.isfile(path):
        raise GenerationError(f"Examples file not found: {path}")
    data = yaml.safe_load(open(path, 'r'))
    return data.get('questions', [])

def load_section_questions(path):
    """Load existing questions for the section from a YAML file."""
    if not os.path.isfile(path):
        raise GenerationError(f"Section file not found: {path}")
    data = yaml.safe_load(open(path, 'r'))
    return data.get('questions', [])

def is_duplicate(new_q, existing_qs):
    """Check if new_q duplicates any in existing_qs by normalized question text."""
    new_norm = new_q.get('question', '').strip().lower()
    for q in existing_qs:
        if get_normalized_question_text(q) == new_norm:
            return True
    return False

def match_required_fields(new_q, required=None):
    """Ensure new_q contains all required fields."""
    if required is None:
        required = ['question', 'suggestion', 'source']
    missing = [f for f in required if f not in new_q or not new_q.get(f)]
    if missing:
        raise MissingFieldsError(f"Missing required fields: {missing}")
    return True

def format_solution(new_q):
    """Format YAML solutions or manifests in-place using format_questions logic."""
    wrapper = {'questions': [new_q.copy()]}
    fq.format_solution_yaml(wrapper)
    formatted = wrapper['questions'][0]
    new_q.clear()
    new_q.update(formatted)
    return new_q

def append_missing_details(new_q):
    """Append missing prompt details based on suggestion content."""
    q_text = new_q.get('question', '')
    sol_text = ''
    if 'suggestion' in new_q:
        items = new_q['suggestion']
        sol_text = '\n'.join(items) if isinstance(items, list) else str(items)
    details = mq.find_missing_details(q_text, sol_text)
    if details:
        new_q['question'] = q_text.strip() + ''.join(details)
    return new_q

def assign_source(new_q, consolidated_path):
    """Assign a source to new_q using a consolidated sources YAML file."""
    if not os.path.isfile(consolidated_path):
        raise GenerationError(f"Consolidated sources file not found: {consolidated_path}")
    data = yaml.safe_load(open(consolidated_path, 'r')) or {}
    mapping = {}
    for item in data.get('questions', []):
        prompt = (item.get('prompt') or item.get('question') or '').strip()
        src = mq.get_source_from_consolidated(item)
        if prompt and src:
            mapping[prompt] = src
    from thefuzz import fuzz
    text = new_q.get('question','').strip()
    best, score = None, 0
    for prompt, src in mapping.items():
        r = fuzz.ratio(text, prompt)
        if r > score:
            best, score = src, r
    if best and score >= 80:
        new_q['source'] = best
    return new_q

def validate_yaml_and_manifest(new_q):
    """Validate YAML syntax and Kubernetes manifest correctness for suggestions."""
    for item in new_q.get('suggestion', []):
        if isinstance(item, str) and '\n' in item and 'apiVersion' in item:
            ok, summary, details = validate_manifest(item)
            if not ok:
                raise GenerationError(f"Manifest validation failed: {summary}\n{details}")
    return True

def call_llm(prompt):
    """Call LLM to generate new question YAML text and parse into dict."""
    llm_type, model = _get_llm_model()
    if not model:
        raise GenerationError("No LLM model available for generation.")
    if llm_type in ('openai', 'openrouter'):
        resp = model.chat.completions.create(
            model='gpt-3.5-turbo',
            messages=[{'role':'system','content':'You are a Kubernetes CKAD expert.'},
                      {'role':'user','content':prompt}]
        )
        text = resp.choices[0].message.content.strip()
    elif llm_type == 'gemini':
        text = model.generate_content(prompt)
    else:
        raise GenerationError(f"Unsupported LLM type: {llm_type}")
    if text.startswith('```'):
        text = text.split('```',2)[-1].strip()
    try:
        data = yaml.safe_load(text)
        if not data or 'questions' not in data or not data['questions']:
            raise GenerationError('LLM returned no questions')
        return data['questions'][0]
    except yaml.YAMLError as e:
        raise GenerationError(f"Failed to parse LLM output as YAML: {e}")

def build_prompt(examples, existing, topic):
    """Construct the LLM prompt using few-shot examples and existing section content."""
    parts = []
    if examples:
        parts.append('Here are some examples:')
        parts.append(yaml.safe_dump({'questions': examples}, sort_keys=False))
    parts.append(f"Existing questions in '{topic}' section (avoid duplicates):")
    parts.append(yaml.safe_dump({'questions':[{'question':q.get('question')} for q in existing]}, sort_keys=False))
    parts.append(
        "Generate one new, unique Kubernetes CKAD-style question for the above section."
        " Return output as valid YAML with exactly one item under 'questions', each having fields:"
        " question, suggestion (list or scalar), source."
    )
    return '\n'.join(parts)

def generate_section_question(section_file, examples_file, consolidated_file):
    """Orchestrate full generation flow for a section file."""
    examples = load_examples(examples_file)
    existing = load_section_questions(section_file)
    prompt = build_prompt(examples, existing, os.path.splitext(os.path.basename(section_file))[0])
    new_q = call_llm(prompt)
    if is_duplicate(new_q, existing):
        raise DuplicateQuestionError('Generated question is a duplicate')
    match_required_fields(new_q)
    format_solution(new_q)
    append_missing_details(new_q)
    assign_source(new_q, consolidated_file)
    validate_yaml_and_manifest(new_q)
    return new_q