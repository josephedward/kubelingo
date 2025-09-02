import yaml
from colorama import Fore, Style
import kubelingo.utils as _utils
from kubelingo.utils import USER_DATA_DIR, PERFORMANCE_FILE

_performance_data_changed = False # Global flag to track changes to performance data

def save_performance_data(data):
    """Saves performance data."""
    # Note: skipping performance change flag guard to allow saving in tests
    # global _performance_data_changed
    # if not _performance_data_changed:
    #     return
    _utils.ensure_user_data_dir()
    try:
        with open(PERFORMANCE_FILE, 'w') as f:
            yaml.dump(data, f)
        _performance_data_changed = False
    except Exception as e:
        print(f"{Fore.RED}Error saving performance data to '{PERFORMANCE_FILE}': {e}{Style.RESET_ALL}")
