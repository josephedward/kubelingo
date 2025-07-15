#!/usr/bin/env python3
"""
Root CLI wrapper for kubelingo package.
"""
import sys


# FIXME: This script depends on the `kubelingo` package. Without this
# package installed, the script will fail at runtime with an ImportError.
def main():
    try:
        from kubelingo.cli import main as cli_main
    except ImportError:
        print("Error: kubelingo CLI module not found. Ensure the package is installed correctly.")
        sys.exit(1)
    return cli_main()

if __name__ == '__main__':
    sys.exit(main())
