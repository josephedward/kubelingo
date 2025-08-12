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
    from kubelingo.database import get_questions_by_source_file
    from kubelingo.modules.question_generator import AIQuestionGenerator
    from kubelingo.question import Question, ValidationStep
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
    parser.add_argument(
        "--category",
        choices=['Basic', 'Command', 'Manifest'],
        default='Command',
        help="Category of questions to generate. 'Basic' for conceptual (socratic), 'Command' for kubectl commands, 'Manifest' for YAML authoring."
    )
    parser.add_argument("--num-questions", type=int, default=3, help="Number of questions to generate.")
    parser.add_argument("--example-source-file", help="Filename of a quiz module (e.g., 'kubectl_service_account_operations.yaml') to use as a source of example questions from the database.")
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
    if args.example_source_file:
        print(f"Loading example questions from source file '{args.example_source_file}' in the database...")
        question_dicts = get_questions_by_source_file(args.example_source_file)

        if not question_dicts:
            print(f"Warning: No example questions found in the database for source file '{args.example_source_file}'.")
        else:
            # Convert question dicts from DB to Question objects for the generator
            for q_dict in question_dicts:
                try:
                    validation_steps = [
                        ValidationStep(**vs) for vs in q_dict.get('validation_steps', []) if vs
                    ]
                    
                    # This logic is from kubernetes/session.py, it's a good fallback
                    if not validation_steps and q_dict.get('type') == 'command' and q_dict.get('response'):
                        validation_steps.append(ValidationStep(cmd=q_dict['response'], matcher={'exit_code': 0}))

                    # Categories might be a list or a single string. The Question object expects a list.
                    categories = q_dict.get('categories')
                    if not categories:
                        category_str = q_dict.get('category')
                        categories = [category_str] if category_str else ['General']

                    base_questions.append(Question(
                        id=q_dict.get('id', ''),
                        prompt=q_dict.get('prompt', ''),
                        response=q_dict.get('response'),
                        type=q_dict.get('type', ''),
                        pre_shell_cmds=q_dict.get('pre_shell_cmds', []),
                        initial_files=q_dict.get('initial_files', {}),
                        validation_steps=validation_steps,
                        explanation=q_dict.get('explanation'),
                        categories=categories,
                        difficulty=q_dict.get('difficulty'),
                        metadata=q_dict.get('metadata', {})
                    ))
                except (TypeError, KeyError) as e:
                    print(f"Warning: Could not convert question dict from DB to Question object: {e}")
            print(f"Using {len(base_questions)} questions from the database as examples.")

    generator = AIQuestionGenerator()
    
    print(f"Generating {args.num_questions} questions about '{args.subject}'...")
    new_questions = generator.generate_questions(
        subject=args.subject,
        num_questions=args.num_questions,
        base_questions=base_questions,
        category=args.category
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

    # Ensure output directory exists
    output_dir = os.path.dirname(args.output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

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
