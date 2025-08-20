#!/usr/bin/env python3
"""
Manage bug tickets stored in docs/bug_tickets.yaml.
"""
import os
import sys
try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)
from datetime import datetime

def _get_ticket_file_path():
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'docs', 'bug_tickets.yaml')
    )

def load_tickets():
    path = _get_ticket_file_path()
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, list) else []
    return []

def save_tickets(tickets):
    path = _get_ticket_file_path()
    with open(path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(tickets, f, sort_keys=False)

def main():
    tickets = load_tickets()
    next_id = max((t.get('id', 0) for t in tickets), default=0) + 1
    # Prompt for multiline description via editor if available, else single-line input
    editor = os.environ.get('EDITOR')
    if editor:
        print("Please enter the issue description. Your editor will open; save and close to continue.")
        import tempfile, subprocess
        tmp = tempfile.NamedTemporaryFile(mode='w+', suffix='.md', delete=False)
        tmp_path = tmp.name
        tmp.close()
        subprocess.call([editor, tmp_path])
        with open(tmp_path, 'r', encoding='utf-8') as f:
            desc = f.read().strip()
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
    else:
        desc = input("Short description of the issue? ").strip()
    # Location and category (single-line)
    loc = input("Where did you observe this (script name, line, DB state)? ").strip()
    cat = input("Category / severity? ").strip()
    ticket = {
        'id': next_id,
        'description': desc,
        'location': loc,
        'category': cat,
        'status': 'open',
        'created_at': datetime.utcnow().isoformat() + 'Z'
    }
    tickets.append(ticket)
    save_tickets(tickets)
    print(f"Ticket {next_id} added.")

if __name__ == '__main__':
    main()