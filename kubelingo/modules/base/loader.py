import os
import importlib
from kubelingo.modules.base.session import StudySession

def discover_modules():
    """Scans for modules in the kubelingo/modules directory."""
    modules = []
    # Path to kubelingo/modules/
    modules_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    for name in os.listdir(modules_dir):
        module_path = os.path.join(modules_dir, name)
        # A module is a directory with a session.py, and not 'base'
        if os.path.isdir(module_path) and name != 'base' and os.path.exists(os.path.join(module_path, 'session.py')):
            modules.append(name)
    return sorted(modules)

def load_session(module_name: str, logger) -> StudySession:
    """Loads a study session module."""
    try:
        module_path = f'kubelingo.modules.{module_name}.session'
        mod = importlib.import_module(module_path)
        # Convention: session class is named NewSession
        session_class = getattr(mod, 'NewSession')
        return session_class(logger=logger)
    except ImportError as e:
        raise ImportError(f"Could not import session module for '{module_name}': {e}")
    except AttributeError:
        raise AttributeError(f"Module '{module_name}'s session.py does not define a 'NewSession' class.")
