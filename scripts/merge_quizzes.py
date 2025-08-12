import argparse
import os
import sys
import yaml

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def main():
    parser = argparse.ArgumentParser(description="Merge questions from a source YAML file into a destination YAML file.")
    parser.add_argument("--source", required=True, help="Path to the source YAML file to merge from.")
    parser.add_argument("--destination", required=True, help="Path to the destination YAML file to merge into.")
    parser.add_argument("--delete-source", action="store_true", help="Delete the source file after a successful merge.")
    
    args = parser.parse_args()

    if not os.path.exists(args.source):
        print(f"Error: Source file not found at '{args.source}'")
        sys.exit(1)
        
    dest_dir = os.path.dirname(args.destination)
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)

    try:
        with open(args.source, 'r', encoding='utf-8') as f:
            source_questions = yaml.safe_load(f) or []

        if os.path.exists(args.destination):
            with open(args.destination, 'r', encoding='utf-8') as f:
                dest_questions = yaml.safe_load(f) or []
        else:
            print(f"Warning: Destination file '{args.destination}' not found. It will be created.")
            dest_questions = []

        if not isinstance(source_questions, list) or not isinstance(dest_questions, list):
            print("Error: Both source and destination files must contain a YAML list of questions.")
            sys.exit(1)

        print(f"Found {len(source_questions)} questions in source file.")
        print(f"Found {len(dest_questions)} questions in destination file.")

        # De-duplicate questions based on 'id'
        seen_ids = {q.get('id') for q in dest_questions if q.get('id')}
        
        new_questions_added = 0
        for q in source_questions:
            q_id = q.get('id')
            if q_id and q_id not in seen_ids:
                dest_questions.append(q)
                seen_ids.add(q_id)
                new_questions_added += 1
            elif not q_id:
                # Append questions without an ID, assuming they are new.
                dest_questions.append(q)
                new_questions_added += 1

        if new_questions_added > 0:
            print(f"Adding {new_questions_added} new unique questions to destination file.")
            with open(args.destination, 'w', encoding='utf-8') as f:
                yaml.safe_dump(dest_questions, f, default_flow_style=False, sort_keys=False, indent=2)
            print(f"Successfully merged questions into '{args.destination}'.")
        else:
            print("No new unique questions to merge.")

        if args.delete_source and new_questions_added > 0:
            os.remove(args.source)
            print(f"Successfully deleted source file '{args.source}'.")

    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
