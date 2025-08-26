import os
import shutil

def backup_performance_yaml():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    source_path = os.path.join(project_root, 'user_data', 'performance.yaml')
    destination_dir = os.path.join(project_root, 'misc')
    destination_path = os.path.join(destination_dir, 'performance.yaml')

    if not os.path.exists(source_path):
        print(f"Error: Source file not found at {source_path}")
        return

    os.makedirs(destination_dir, exist_ok=True)

    try:
        shutil.copyfile(source_path, destination_path)
        print(f"Successfully backed up {source_path} to {destination_path}")
    except Exception as e:
        print(f"Error backing up file: {e}")

if __name__ == "__main__":
    backup_performance_yaml()
