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

    try:
        for i, q in enumerate(questions):
            clear_screen()
            print(f"Question {i+1}/{len(questions)} (Topic: {args.topic})")
            print("-" * 40)
            print(q['question'])
            print("-" * 40)
            print("Enter command(s). Type 'done' to check, or 'solution' to see the answer.")

            user_commands = []
            while True:
                try:
                    cmd = input("> ")
                except EOFError:
                    print()  # for a newline
                    user_commands = None  # Treat as giving up
                    break

                if cmd.strip().lower() == 'done':
                    break
                if cmd.strip().lower() == 'solution':
                    user_commands = None  # Flag to show solution
                    break
                if cmd.strip():
                    user_commands.append(cmd.strip())

            if user_commands is None:
                print("\nSolution:\n")
                print(q['solution'])
            else:
                solution_commands = [cmd.strip() for cmd in q['solution'].strip().split('\n') if cmd.strip()]
                if user_commands == solution_commands:
                    print("\nCorrect! Well done.")
                else:
                    print("\nNot quite. Here's the expected solution:\n")
                    print(q['solution'])

            print("-" * 40)
            if i < len(questions) - 1:
                input("Press Enter for the next question...")

        clear_screen()
        print("Great job! You've completed all questions for this topic.")
    except KeyboardInterrupt:
        print("\n\nStudy session ended. Goodbye!")

if __name__ == "__main__":
    main()
