import argparse
import os
import sys
from dataclasses import asdict

# Ensure the project root is in the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Use a try-except block for robustness in a script
try:
    from kubelingo.modules.question_generator import AIQuestionGenerator
    from kubelingo.modules.yaml_loader import YAMLLoader
    from kubelingo.utils.ui import yaml
except ImportError as e:
    print(f"Error: Failed to import kubelingo modules. Make sure you have run 'pip install -e .' from the project root. Details: {e}")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Generate AI questions and save them to a YAML file.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--subject", required=True, help="Subject for the new questions (e.g., 'Kubernetes Service Accounts').")
    parser.add_argument("--num-questions", type=int, default=3, help="Number of questions to generate.")
    parser.add_argument("--example-file", help="Path to a YAML file with example questions for context.")
    parser.add_argument(
        "--output-file",
        required=True,
        help="Path to the output YAML file to save the generated questions.\n"
             "After generation, you can add these to the database by running:\n"
             "python scripts/migrate_to_db.py"
    )

    args = parser.parse_args()

    if 'OPENAI_API_KEY' not in os.environ:
        print("Error: OPENAI_API_KEY environment variable not set.")
        sys.exit(1)

    base_questions = []
    if args.example_file:
        if not os.path.exists(args.example_file):
            print(f"Error: Example file not found at '{args.example_file}'")
            sys.exit(1)
        loader = YAMLLoader()
        base_questions = loader.load_file(args.example_file)
        print(f"Using {len(base_questions)} questions from '{args.example_file}' as examples.")

    generator = AIQuestionGenerator()
    
    print(f"Generating {args.num_questions} questions about '{args.subject}'...")
    new_questions = generator.generate_questions(
        subject=args.subject,
        num_questions=args.num_questions,
        base_questions=base_questions
    )

    if not new_questions:
        print("AI failed to generate any questions.")
        return

    print(f"Successfully generated {len(new_questions)} questions.")

    question_dicts = [asdict(q) for q in new_questions]
    
    # Clean up fields that are not part of the YAML schema or are runtime-only
    for q_dict in question_dicts:
        if 'review' in q_dict:
            del q_dict['review']

    if os.path.exists(args.output_file):
        overwrite = input(f"File '{args.output_file}' already exists. Overwrite? (y/N): ").lower()
        if overwrite != 'y':
            print("Operation cancelled.")
            return
            
    with open(args.output_file, 'w', encoding='utf-8') as f:
        yaml.safe_dump(question_dicts, f, default_flow_style=False, sort_keys=False, indent=2)

    print(f"\nSuccessfully saved {len(new_questions)} questions to '{args.output_file}'.")
    print("\nNOTE: The generated questions include an 'explanation' field.")
    print("The database migration script may need to be updated to store this field.")
    print("\nTo add these to the database, you may need to run the migration script:")
    print("  python scripts/migrate_to_db.py")


if __name__ == "__main__":
    main()
