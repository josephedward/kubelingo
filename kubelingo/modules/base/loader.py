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
    # Load the module's session.py
    module_path = f'kubelingo.modules.{module_name}.session'
    try:
        mod = importlib.import_module(module_path)
    except ImportError as e:
        raise ImportError(f"Could not import session module for '{module_name}': {e}")
    # Session class can be named NewSession or <ModuleName>Session
    session_class = None
    if hasattr(mod, 'NewSession'):
        session_class = getattr(mod, 'NewSession')
    else:
        fallback = f"{module_name.capitalize()}Session"
        if hasattr(mod, fallback):
            session_class = getattr(mod, fallback)
    if not session_class:
        names = [n for n in ('NewSession', fallback) if hasattr(mod, n)]
        raise AttributeError(
            f"Module '{module_name}'s session.py does not define a session class (tried 'NewSession' and '{fallback}')."
        )
    return session_class(logger=logger)
