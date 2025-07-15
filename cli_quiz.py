#!/usr/bin/env python3
"""
Root CLI wrapper for kubelingo package.
"""
import sys

def main():
    try:
        from kubelingo.cli import main as cli_main
    except ImportError:
        print("Error: kubelingo CLI module not found. Ensure the package is installed correctly.")
        sys.exit(1)
    return cli_main()

if __name__ == '__main__':
    sys.exit(main())