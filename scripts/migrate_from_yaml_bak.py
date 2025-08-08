import os
import sys
import shutil

# Add project root to path to allow importing kubelingo
try:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from kubelingo.modules.yaml_loader import YAMLLoader
    from kubelingo.database import init_db, add_question
    from kubelingo.utils.config import YAML_QUIZ_BACKUP_DIR, DATABASE_FILE, BACKUP_DATABASE_FILE
except ImportError as e:
    print(f"Error: Could not import kubelingo modules. Make sure you are running this script from the project root.")
    print(f"Import error: {e}")
    sys.exit(1)


def main():
    """
    Clears the database, loads all questions from YAML files in the backup
    directory, saves them to the database, and then creates a new pristine
    backup of the populated database.
    """
    print("Starting migration of questions from 'yaml-bak' directory to database...")

    # 1. Clear the existing database
    print("Clearing the database to ensure a fresh import...")
    init_db(clear=True)

    # 2. Load questions from yaml-bak
    print(f"Searching for YAML files in: {YAML_QUIZ_BACKUP_DIR}")
    if not os.path.isdir(YAML_QUIZ_BACKUP_DIR):
        print(f"Error: Backup directory not found at '{YAML_QUIZ_BACKUP_DIR}'")
        sys.exit(1)

    yaml_loader = YAMLLoader()
    total_questions_added = 0

    for filename in sorted(os.listdir(YAML_QUIZ_BACKUP_DIR)):
        if not filename.endswith(('.yaml', '.yml')):
            continue
        
        file_path = os.path.join(YAML_QUIZ_BACKUP_DIR, filename)
        print(f"  -> Processing file: {filename}")
        try:
            questions = yaml_loader.load_file(file_path)
            if not questions:
                print(f"     No questions found in {filename}.")
                continue
            
            # The lookup key for quizzes is the path in the main `yaml` directory.
            # We must store paths as if they came from there, not `yaml-bak`.
            intended_source_file = file_path.replace(os.sep + 'yaml-bak' + os.sep, os.sep + 'yaml' + os.sep)
            
            for q in questions:
                add_question(
                    id=q.id,
                    prompt=q.prompt,
                    source_file=intended_source_file,
                    response=q.response,
                    category=q.category,
                    source=q.source,
                    validation_steps=q.validation_steps,
                    validator=q.validator,
                    explanation=q.explanation
                )
            total_questions_added += len(questions)
            print(f"     Added {len(questions)} questions from {filename}.")

        except Exception as e:
            print(f"     Error processing {filename}: {e}")

    print(f"\nTotal questions added to the database: {total_questions_added}")
    
    if total_questions_added == 0:
        print("\nNo questions were added. Aborting backup.")
        return

    # 3. Back up the newly populated database to the pristine location
    print(f"\nBacking up new database to '{BACKUP_DATABASE_FILE}'...")
    try:
        # Ensure backup directory exists
        backup_dir = os.path.dirname(BACKUP_DATABASE_FILE)
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            
        shutil.copyfile(DATABASE_FILE, BACKUP_DATABASE_FILE)
        print("Backup successful.")
        print(f"Pristine database at '{BACKUP_DATABASE_FILE}' has been updated.")
    except Exception as e:
        print(f"Error creating backup: {e}")

if __name__ == "__main__":
    main()
