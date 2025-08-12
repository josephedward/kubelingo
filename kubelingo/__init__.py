"""Kubelingo package initialization."""
__version__ = '0.1.12'
# This file makes 'kubelingo' a Python package.

def _initialize():
    """Run startup initializers."""
    try:
        from scripts.initialize_from_yaml import initialize_from_yaml
        initialize_from_yaml()
    except Exception as e:
        # Use print here as logging might not be configured yet, and we want this to be visible.
        print(f"WARNING: Could not run database initializer on startup: {e}")

_initialize()
import logging
import os

# Run bootstrap process on startup, unless disabled via environment variable.
if os.environ.get("KUBELINGO_SKIP_BOOTSTRAP") != "1":
    # Configure basic logging in case the app using the package hasn't.
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [Bootstrap] %(message)s'
    )
    try:
        # Local import to avoid circular dependencies and other import-time issues.
        from . import bootstrap
        bootstrap.bootstrap_on_startup()
    except ImportError as e:
        logging.warning(f"Could not import bootstrap module, skipping: {e}")
    except Exception as e:
        logging.error(f"Bootstrap process failed during startup: {e}", exc_info=True)
