#!/usr/bin/env python3
"""
Print schema information for the live database.
"""
import sqlite3
from kubelingo.database import get_db_connection

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    print('Tables:')
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    for (name,) in cur.fetchall():
        print('-', name)
        cur.execute(f"PRAGMA table_info('{name}')")
        for col in cur.fetchall():
            print('   ', col)
    print('\nIndexes:')
    cur.execute("SELECT name, tbl_name FROM sqlite_master WHERE type='index'")
    for name, tbl in cur.fetchall():
        print('-', name, 'on', tbl)
    conn.close()

if __name__ == '__main__':
    main()