#!/usr/bin/env python3
"""
Move and rename all database files into a single directory (APP_DIR),
using each file's creation timestamp for a unified filename, and
deduplicate identical files by content hash.
"""
import sys, hashlib
from pathlib import Path
from datetime import datetime
from kubelingo.utils.config import APP_DIR

def file_hash(path: Path, block_size: int = 65536) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for blk in iter(lambda: f.read(block_size), b''):
            h.update(blk)
    return h.hexdigest()

def main():
    project_root = Path(APP_DIR).parent
    dest_dir = Path(APP_DIR)
    # Ensure target dir exists
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Error creating directory {dest_dir}: {e}", file=sys.stderr)
        sys.exit(1)

    # Collect source DB files
    sources = []
    sources.extend([
        Path(APP_DIR) / 'kubelingo.db',
        project_root / 'backup_questions.db',
        project_root / 'categorized.db',
    ])
    # Include any .sqlite3 under backups/sqlite
    sqlite_dir = project_root / 'backups' / 'sqlite'
    if sqlite_dir.is_dir():
        sources.extend(sqlite_dir.glob('*.sqlite3'))

    # Filter existing files
    sources = [p for p in sources if p.is_file()]
    if not sources:
        print("No database files found to consolidate.")

    # Deduplicate by hash, keeping the file with latest creation time
    by_hash = {}
    for p in sources:
        h = file_hash(p)
        st = p.stat()
        ctime = getattr(st, 'st_birthtime', None) or st.st_mtime
        # For duplicates, keep the one with max ctime
        if h not in by_hash or ctime > by_hash[h][0]:
            by_hash[h] = (ctime, p)

    # Process unique database files
    for ctime, p in sorted(by_hash.values(), reverse=True):
        ts = datetime.fromtimestamp(ctime).strftime('%Y%m%d_%H%M%S')
        new_name = f"kubelingo_db_{ts}.db"
        dst = dest_dir / new_name
        if dst.exists():
            print(f"Skipping existing: {dst}")
            continue
        try:
            p.rename(dst)
            print(f"Moved {p} -> {dst}")
        except Exception as e:
            print(f"Failed to move {p} -> {dst}: {e}", file=sys.stderr)

    # Delete empty YAML files (with only 'entries: []' in last document)
    try:
        import yaml
    except ImportError:
        print("PyYAML not available; skipping empty YAML cleanup.", file=sys.stderr)
    else:
        from kubelingo.utils.path_utils import get_all_question_dirs, find_yaml_files
        yaml_dirs = get_all_question_dirs()
        yaml_files = find_yaml_files(yaml_dirs)
        removed = 0
        for yf in yaml_files:
            try:
                docs = list(yaml.safe_load_all(yf.read_text(encoding='utf-8')))
            except Exception:
                continue
            if docs and isinstance(docs[-1], dict) and list(docs[-1].keys()) == ['entries'] and docs[-1].get('entries') == []:
                try:
                    yf.unlink()
                    print(f"Deleted empty YAML: {yf}")
                    removed += 1
                except Exception as e:
                    print(f"Failed to delete {yf}: {e}", file=sys.stderr)
        if removed:
            print(f"Removed {removed} empty YAML file(s).")

    # Prune old backups: keep only the 10 most recent database files
    pattern = "kubelingo_db_*.db"
    all_backups = list(dest_dir.glob(pattern))
    if len(all_backups) > 10:
        # sort by modification time, newest first
        sorted_backups = sorted(all_backups, key=lambda p: p.stat().st_mtime, reverse=True)
        to_remove = sorted_backups[10:]
        for old in to_remove:
            try:
                old.unlink()
                print(f"Removed old backup: {old}")
            except Exception as e:
                print(f"Failed to remove {old}: {e}", file=sys.stderr)

if __name__ == '__main__':
    main()