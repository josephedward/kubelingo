import sys
import os

# Make sure the project root (one level up) is on the Python path so that
# the 'kubelingo' package can be imported by test modules.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)