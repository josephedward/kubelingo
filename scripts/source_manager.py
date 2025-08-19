import os
import yaml
from thefuzz import fuzz
import sys
import webbrowser
import argparse

try:
    from googlesearch import search
except ImportError:
    search = None # Handle gracefully if not installed

# --- Configuration ---
CONSOLIDATED_FILE = '/Users/user/Documents/GitHub/kubelingo/questions/consolidated_20250811_144940.yaml'
QUESTIONS_DIR = '/Users/user/Documents/GitHub/kubelingo/questions/'

# --- Logic from add_sources.py ---
def get_source_from_consolidated(item):
    """Extracts source URL from a consolidated question item."""
    metadata = item.get('metadata', {})
    if not metadata:
        return None
    
    if 'links' in metadata and metadata['links']:
        return metadata['links'][0]
    if 'source' in metadata and metadata['source']:
        return metadata['source']
    if 'citation' in metadata and metadata['citation']:
        return metadata['citation']
    return None

def add_sources_to_questions():
    """
    Updates existing question files with source URLs 
    from a consolidated question file.
    """
    print("Running add_sources logic...")
    print("Loading consolidated questions...")
    with open(CONSOLIDATED_FILE, 'r') as f:
        consolidated_data = yaml.safe_load(f)

    # Create a mapping from prompt to source
    prompt_to_source = {}
    if consolidated_data and 'questions' in consolidated_data:
        for item in consolidated_data['questions']:
            prompt = item.get('prompt')
            source = get_source_from_consolidated(item)
            if prompt and source:
                prompt_to_source[prompt.strip()] = source

    print(f"Found {len(prompt_to_source)} questions with sources in consolidated file.")

    # Iterate through question files in the directory
    for filename in os.listdir(QUESTIONS_DIR):
        if filename.endswith('.yaml') and filename != os.path.basename(CONSOLIDATED_FILE):
            filepath = os.path.join(QUESTIONS_DIR, filename)
            print(f"Processing {filepath}...")
            
            with open(filepath, 'r') as f:
                try:
                    topic_data = yaml.safe_load(f)
                    if not topic_data or 'questions' not in topic_data:
                        continue
                except yaml.YAMLError as e:
                    print(f"  Error loading YAML: {e}")
                    continue

            questions = topic_data.get('questions', [])
            updated_count = 0
            
            for question in questions:
                if 'source' in question: # Skip if source already exists
                    continue

                question_text = question.get('question', '').strip()
                
                # Find the best match from the consolidated file
                best_match_prompt = None
                highest_ratio = 0
                for prompt in prompt_to_source.keys():
                    ratio = fuzz.ratio(question_text, prompt)
                    if ratio > highest_ratio: # Add a minimum threshold if needed
                        highest_ratio = ratio
                        best_match_prompt = prompt
                
                if highest_ratio > 95: # Use a high threshold for matching
                    source_url = prompt_to_source[best_match_prompt]
                    question['source'] = source_url
                    updated_count += 1
                    print(f"  Added source to question: '{question_text[:50]}...'")

            if updated_count > 0:
                print(f"  Saving {updated_count} updates to {filepath}")
                with open(filepath, 'w') as f:
                    yaml.dump(topic_data, f, sort_keys=False)
            else:
                print("  No new sources to add.")
    print("add_sources logic complete.\n")

# --- Logic from check_sources.py ---
def check_for_missing_sources():
    """
    Checks all question files to ensure every question has a 'source' field.
    Reports questions missing a source.
    """
    print("Running check_sources logic...")
    print("Checking all question files for missing sources...")
    
    missing_sources_found = False
    
    for filename in os.listdir(QUESTIONS_DIR):
        if filename.endswith('.yaml') and filename != os.path.basename(CONSOLIDATED_FILE):
            filepath = os.path.join(QUESTIONS_DIR, filename)
            print(f"Processing {filepath}...")
            
            with open(filepath, 'r') as f:
                try:
                    topic_data = yaml.safe_load(f)
                    if not topic_data or 'questions' not in topic_data:
                        print(f"  No questions found in {filename} or invalid format.")
                        continue
                except yaml.YAMLError as e:
                    print(f"  Error loading YAML from {filename}: {e}")
                    continue

            questions = topic_data.get('questions', [])
            
            for i, question in enumerate(questions):
                if 'source' not in question or not question['source']:
                    print(f"  WARNING: Question {i+1} in {filename} is missing a source:")
                    print(f"    Question: {question.get('question', 'N/A')[:100]}...")
                    missing_sources_found = True
    
    if not missing_sources_found:
        print("\nAll questions have a source. Great job!")
    else:
        print("\nSome questions are missing sources. Please use 'find_source.py' to help locate sources and manually update the respective YAML files.")
    print("check_sources logic complete.\n")

def interactive_source_manager(auto_approve=False):
    """
    Interactively helps the user add sources to questions that are missing them.
    If auto_approve is True, it automatically selects the first search result.
    """
    print("\nStarting interactive source management...")
    
    for filename in os.listdir(QUESTIONS_DIR):
        if filename.endswith('.yaml') and filename != os.path.basename(CONSOLIDATED_FILE):
            filepath = os.path.join(QUESTIONS_DIR, filename)
            
            with open(filepath, 'r') as f:
                try:
                    topic_data = yaml.safe_load(f)
                    if not topic_data or 'questions' not in topic_data:
                        continue
                except yaml.YAMLError as e:
                    print(f"  Error loading YAML from {filename}: {e}")
                    continue

            questions = topic_data.get('questions', [])
            file_modified = False
            
            for i, question in enumerate(questions):
                if 'source' not in question or not question['source']:
                    print(f"\n  --- Missing source for Question {i+1} in {filename} ---")
                    print(f"    Question: {question.get('question', 'N/A')}")
                    
                    if auto_approve:
                        print("    Auto-approving first search result...")
                        if search is None:
                            print("    'googlesearch-python' is not installed. Cannot auto-approve search results.")
                            continue # Skip this question
                        
                        search_results = []
                        try:
                            search_results = [url for url in search(f"kubernetes {question.get('question', '')}", num_results=1)] # Only need 1 result
                        except Exception as e:
                            print(f"    Error during search: {e}")

                        if search_results:
                            question['source'] = search_results[0]
                            print(f"    Source added: {question['source']}")
                            file_modified = True
                        else:
                            print("    No search results found for auto-approval. Skipping question.")
                        continue # Move to next question
                    
                    # --- Original interactive logic starts here ---
                    while True:
                        action = input("    Options: [s]earch, [m]anual, [sk]ip, [q]quit: ").strip().lower()
                        
                        if action == 's':
                            if search is None:
                                print("    'googlesearch-python' is not installed. Please run 'pip install googlesearch-python'.")
                                continue
                            
                            print("    Searching for sources...")
                            search_results = []
                            try:
                                search_results = [url for url in search(f"kubernetes {question.get('question', '')}", num_results=5)]
                            except Exception as e:
                                print(f"    Error during search: {e}")

                            if search_results:
                                print("    Search results:")
                                for j, url in enumerate(search_results):
                                    print(f"      {j+1}. {url}")
                                    
                                while True:
                                    select_action = input("      Select a number to use, [o]pen in browser (first result), [s]earch again, [sk]ip, [q]quit: ").strip().lower()
                                    if select_action == 'o':
                                        try:
                                            webbrowser.open(search_results[0]) # Open first result
                                        except Exception as e:
                                            print(f"      Could not open browser: {e}")
                                        continue
                                    elif select_action == 's':
                                        break # Break inner loop to search again
                                    elif select_action == 'sk':
                                        break # Break inner loop to skip this question
                                    elif select_action == 'q':
                                        sys.exit("User quit.") # Exit script
                                    try:
                                        selected_index = int(select_action) - 1
                                        if 0 <= selected_index < len(search_results):
                                            question['source'] = search_results[selected_index]
                                            print(f"    Source added: {question['source']}")
                                            file_modified = True
                                            break # Break inner loop, source found
                                        else:
                                            print("      Invalid selection.")
                                    except ValueError:
                                        print("      Invalid input.")
                            else:
                                print("    No search results found.")
                                continue # Go back to main options for this question
                        
                        elif action == 'm':
                            manual_source = input("    Enter source URL manually: ").strip()
                            if manual_source:
                                question['source'] = manual_source
                                print(f"    Source added: {question['source']}")
                                file_modified = True
                            break # Source added or skipped
                        
                        elif action == 'sk':
                            print("    Skipping this question.")
                            break # Skip this question
                        
                        elif action == 'q':
                            sys.exit("User quit.") # Exit script
                        
                        else:
                            print("    Invalid option.")
            
            if file_modified:
                print(f"  Saving updates to {filepath}")
                with open(filepath, 'w') as f:
                    yaml.dump(topic_data, f, sort_keys=False)
                file_modified = False # Reset for next file
    
    print("\nInteractive source management complete.")

# --- Main execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage and check sources for Kubernetes questions.")
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--add", action="store_true", help="Run logic to add sources to questions from consolidated file.")
    group.add_argument("--check", action="store_true", help="Check all question files for missing sources.")
    group.add_argument("--interactive", action="store_true", help="Start interactive source management.")
    
    parser.add_argument("--auto-approve", action="store_true", 
                        help="Automatically approve the first search result as source for missing questions (only with --interactive).")
    
    args = parser.parse_args()

    if args.add:
        add_sources_to_questions()
    elif args.check:
        check_for_missing_sources()
    elif args.interactive:
        interactive_source_manager(args.auto_approve)
    else:
        parser.print_help()
        print("\nNo action specified. Please use --add, --check, or --interactive.")
