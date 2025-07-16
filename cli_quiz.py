#!/usr/bin/env python3
"""Entry-point wrapper for the Kubelingo CLI"""
import sys
from kubelingo.cli import main

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)