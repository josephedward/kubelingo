import os
import random
import time
import yaml
import argparse

def clear_screen():
    """Clears the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def load_questions(topic):
    """Loads questions from a YAML file based on the topic."""
    file_path = f"questions/{topic}.yaml"
    if not os.path.exists(file_path):
        print(f"Error: Question file not found at {file_path}")
        available_topics = [f.replace('.yaml', '') for f in os.listdir('questions') if f.endswith('.yaml')]
        if available_topics:
            print("Available topics: " + ", ".join(available_topics))
        return None
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

def main():
    """Main function to run the study app."""
    if not os.path.exists('questions'):
        os.makedirs('questions')

    parser = argparse.ArgumentParser(description="A CLI tool to help study for the CKAD exam.")
    parser.add_argument("topic", help="The topic to study (e.g., core_concepts).")
    args = parser.parse_args()

    data = load_questions(args.topic)
    if not data or 'questions' not in data:
        print("No questions found in the specified topic file.")
        return

    questions = data['questions']
    random.shuffle(questions)

    for i, q in enumerate(questions):
        clear_screen()
        print(f"Question {i+1}/{len(questions)} (Topic: {args.topic})")
        print("-" * 40)
        print(q['question'])
        print("-" * 40)
        input("Press Enter to reveal the solution...")
        print("\nSolution:\n")
        print(q['solution'])
        print("-" * 40)
        if i < len(questions) - 1:
            input("Press Enter for the next question...")

    clear_screen()
    print("Great job! You've completed all questions for this topic.")

if __name__ == "__main__":
    main()
