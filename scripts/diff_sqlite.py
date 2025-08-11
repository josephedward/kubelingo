#!/usr/bin/env python3
"""
Diff schema and data between two SQLite database files.
"""
import argparse
import sqlite3
import sys

def load_objects(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT type, name, sql FROM sqlite_master WHERE type IN ('table','index','view','trigger')")
    objs = { (row['type'], row['name']): row['sql'] for row in cur.fetchall() }
    conn.close()
    return objs

def main():
    parser = argparse.ArgumentParser(description='Diff two SQLite databases')
    parser.add_argument('old_db', help='Path to the old SQLite database')
    parser.add_argument('new_db', help='Path to the new SQLite database')
    args = parser.parse_args()

    old_objs = load_objects(args.old_db)
    new_objs = load_objects(args.new_db)

    old_keys = set(old_objs.keys())
    new_keys = set(new_objs.keys())

    for obj in sorted(old_keys - new_keys):
        print(f"Removed: {obj[0]} {obj[1]}")
    for obj in sorted(new_keys - old_keys):
        print(f"Added: {obj[0]} {obj[1]}")
    for obj in sorted(old_keys & new_keys):
        old_sql = (old_objs.get(obj) or '').strip()
        new_sql = (new_objs.get(obj) or '').strip()
        if old_sql != new_sql:
            print(f"Modified: {obj[0]} {obj[1]}")
            print("-", old_sql)
            print("+", new_sql)

if __name__ == '__main__':
    main()