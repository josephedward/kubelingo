import os
import random
import time
import yaml
import argparse
import google.generativeai as genai
from thefuzz import fuzz

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

def get_llm_feedback(question, user_answer, correct_solution):
    """Gets feedback from Gemini on the user's answer."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        # Return a helpful message if the key is not set.
        return "INFO: Set the GEMINI_API_KEY environment variable to get AI-powered feedback."

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"""
        You are a Kubernetes expert helping a student study for the CKAD exam.
        The student was asked the following question:
        ---
        Question: {question}
        ---
        The student provided this answer:
        ---
        Answer: {user_answer}
        ---
        The correct solution is:
        ---
        Solution: {correct_solution}
        ---
        The student's answer was marked as incorrect.
        Briefly explain why the student's answer is wrong and what they should do to fix it.
        Focus on the differences between the student's answer and the correct solution.
        Be concise and encouraging. Do not just repeat the solution. Your feedback should be 2-3 sentences.
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error getting feedback from LLM: {e}"

def list_and_select_topic():
    """Lists available topics and prompts the user to select one."""
    available_topics = sorted([f.replace('.yaml', '') for f in os.listdir('questions') if f.endswith('.yaml')])
    if not available_topics:
        print("No question topics found in the 'questions' directory.")
        return None

    print("\nPlease select a topic to study:")
    for i, topic_name in enumerate(available_topics):
        print(f"  {i+1}. {topic_name.replace('_', ' ').title()}")

    while True:
        try:
            choice = input(f"\nEnter a number (1-{len(available_topics)}): ")
            choice_index = int(choice) - 1
            if 0 <= choice_index < len(available_topics):
                return available_topics[choice_index]
            else:
                print("Invalid number. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number.")
        except (KeyboardInterrupt, EOFError):
            print("\n\nStudy session ended. Goodbye!")
            return None

def main():
    """Main function to run the study app."""
    if not os.path.exists('questions'):
        os.makedirs('questions')

    parser = argparse.ArgumentParser(description="A CLI tool to help study for the CKAD exam.")
    parser.add_argument("topic", nargs='?', default=None, help="The topic to study. If not provided, a menu will be shown.")
    args = parser.parse_args()

    topic = args.topic
    if not topic:
        topic = list_and_select_topic()
        if not topic:
            return

    data = load_questions(topic)
    if not data or 'questions' not in data:
        print("No questions found in the specified topic file.")
        return

    questions = data['questions']
    random.shuffle(questions)

    try:
        for i, q in enumerate(questions):
            clear_screen()
            print(f"Question {i+1}/{len(questions)} (Topic: {topic})")
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
                # Handle both 'solution' and 'solutions' keys for display
                if 'solutions' in q:
                    print(q['solutions'][0]) # Show the first solution
                elif 'solution' in q:
                    print(q['solution'])
            else:
                user_answer = "\n".join(user_commands)

                # Check for multiple correct solutions first (exact match)
                if 'solutions' in q:
                    solution_list = [str(s).strip() for s in q['solutions']]
                    # Normalize user input slightly for comparison
                    user_answer_processed = ' '.join(user_answer.split()).strip()
                    if user_answer_processed in solution_list:
                        print("\nCorrect! Well done.")
                    else:
                        # Use the first solution as the reference for feedback
                        solution_text = solution_list[0]
                        print("\nNot quite. Here's one possible solution:\n")
                        print(solution_text)
                        print("\n--- AI Feedback ---")
                        feedback = get_llm_feedback(q['question'], user_answer, solution_text)
                        print(feedback)

                # Fallback to fuzzy matching for single solutions (kubectl commands)
                elif 'solution' in q:
                    solution_text = q['solution'].strip()

                    # --- Normalization for fuzzy matching ---
                    # 1. Normalize user answer by consolidating whitespace and handling 'k' alias.
                    user_answer_processed = ' '.join(user_answer.split())
                    words = user_answer_processed.split(' ')
                    if words and words[0] == 'k':
                        words[0] = 'kubectl'
                    normalized_user_answer = ' '.join(words)

                    # 2. Normalize solution by removing comments and consolidating whitespace.
                    solution_lines = [line.strip() for line in solution_text.split('\n') if not line.strip().startswith('#')]
                    normalized_solution = ' '.join("\n".join(solution_lines).split())

                    # Use fuzzy matching to allow for small typos but not significant omissions.
                    similarity = fuzz.ratio(normalized_user_answer, normalized_solution)

                    if similarity > 95:
                        print("\nCorrect! Well done.")
                    else:
                        print("\nNot quite. Here's the expected solution:\n")
                        print(solution_text)
                        print("\n--- AI Feedback ---")
                        feedback = get_llm_feedback(q['question'], user_answer, solution_text)
                        print(feedback)

            print("-" * 40)
            if i < len(questions) - 1:
                input("Press Enter for the next question...")

        clear_screen()
        print("Great job! You've completed all questions for this topic.")
    except KeyboardInterrupt:
        print("\n\nStudy session ended. Goodbye!")

if __name__ == "__main__":
    main()
