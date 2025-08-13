#!/usr/bin/env python3
"""
Builds the Kubelingo question database from a specified YAML source file.

This script provides a reliable, out-of-band mechanism for initializing or
updating the application's database. It creates a new database from a YAML
source of truth, populates it with question metadata, and then safely
replaces the live database file.

This approach avoids the issues with on-startup bootstrapping and ensures
that the database is always a consistent reflection of the YAML question bank.

Usage:
    python scripts/build_database.py <path_to_yaml_file>
"""
import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Adjust sys.path to import local helper modules
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from kubelingo.database import init_db, index_yaml_files, get_db_connection
from kubelingo.utils.config import DATABASE_FILE, APP_DIR


def build_database_from_yaml(yaml_file_path: str, verbose: bool = True):
    """
    Initializes and populates the database from a single YAML file.
    """
    yaml_path = Path(yaml_file_path)
    if not yaml_path.is_file():
        if verbose:
            print(f"Error: Source YAML file not found at '{yaml_file_path}'", file=sys.stderr)
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Create temp DB in .kubelingo to ensure it's on the same filesystem for atomic move.
    os.makedirs(APP_DIR, exist_ok=True)
    temp_db_path = os.path.join(APP_DIR, f"kubelingo_build_{timestamp}.db")

    if verbose:
        print(f"Building new database from '{yaml_path.name}'...")
        print(f"Temporary database will be created at: {temp_db_path}")

    conn = None
    try:
        # 1. Initialize a new database with the correct schema
        conn = get_db_connection(db_path=temp_db_path)
        init_db(conn=conn, clear=True)

        # 2. Index questions from the specified YAML file
        if verbose:
            print("Indexing questions...")
        index_yaml_files([yaml_path], conn=conn, verbose=verbose)

    except Exception as e:
        if verbose:
            print(f"\nAn error occurred during database build: {e}", file=sys.stderr)
        # Clean up temp file on failure
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)
        sys.exit(1)
    finally:
        if conn:
            conn.close()

    # 3. Safely replace the live database
    try:
        if verbose:
            print(f"\nReplacing live database at '{DATABASE_FILE}'...")
        # shutil.move is atomic on most POSIX systems if src/dst are on the same filesystem
        shutil.move(temp_db_path, DATABASE_FILE)
        if verbose:
            print("Database build successful.")
            print(f"Live database is now located at: {DATABASE_FILE}")
    except Exception as e:
        if verbose:
            print(f"\nError replacing live database: {e}", file=sys.stderr)
            print(f"The new database is available at '{temp_db_path}'")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Build Kubelingo question database from a YAML source file.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "yaml_file",
        type=str,
        help="Path to the source YAML file containing questions."
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress verbose output."
    )
    args = parser.parse_args()

    build_database_from_yaml(args.yaml_file, verbose=not args.quiet)


if __name__ == "__main__":
    main()
