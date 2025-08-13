import os
from pathlib import Path
from kubelingo.utils.path_utils import load_yaml_files
from kubelingo.utils.validation import find_duplicate_answers

def remove_duplicate_yaml_files(directory: str):
    """
    Removes duplicate YAML files in the specified directory based on the "answer" field.

    Args:
        directory: Path to the directory containing YAML files.
    """
    # Find all YAML files in the directory
    yaml_files = [str(p) for p in Path(directory).glob("*.yaml")]

    # Load YAML content
    yaml_data = load_yaml_files(yaml_files)

    # Find duplicates
    duplicates = find_duplicate_answers(yaml_data)

    # Remove duplicates, keeping one file per set
    for duplicate_set in duplicates:
        # Keep the first file, delete the rest
        for file_to_delete in duplicate_set[1:]:
            try:
                os.remove(file_to_delete)
                print(f"Deleted duplicate file: {file_to_delete}")
            except Exception as e:
                print(f"Error deleting file {file_to_delete}: {e}")

if __name__ == "__main__":
    # Directory containing the YAML files
    directory = "questions/ai-generated"
    remove_duplicate_yaml_files(directory)
