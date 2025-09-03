import os
import yaml
from kubelingo.kubelingo import load_performance_data, USER_DATA_DIR, PERFORMANCE_FILE

def test_load_performance_data_sanitizes_duplicates():
    """Ensures that load_performance_data removes duplicate entries from correct_questions."""
    ensure_user_data_dir_exists()
    # Create a dummy performance.yaml file with duplicate entries
    dummy_data = {
        'commands_args_env': {
            'correct_questions': [
                'question_1',
                'question_2',
                'question_1'  # Duplicate entry
            ]
        }
    }
    with open(PERFORMANCE_FILE, 'w') as f:
        yaml.dump(dummy_data, f)

    # Load the performance data
    loaded_data, _ = load_performance_data()
    # Assert that the duplicates have been removed
    correct_questions = loaded_data.get('commands_args_env', {}).get('correct_questions', [])
    assert len(correct_questions) == 2
    assert sorted(correct_questions) == ['question_1', 'question_2']

    # Clean up the dummy file
    os.remove(PERFORMANCE_FILE)

def ensure_user_data_dir_exists():
    os.makedirs(USER_DATA_DIR, exist_ok=True)
