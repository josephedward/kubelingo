import os
import random
import time
import yaml
import argparse
import google.generativeai as genai
from thefuzz import fuzz
import tempfile
import subprocess

USER_DATA_DIR = "user_data"
MISSED_QUESTIONS_FILE = os.path.join(USER_DATA_DIR, "missed_questions.yaml")
FLAGGED_QUESTIONS_FILE = os.path.join(USER_DATA_DIR, "flagged_questions.yaml")

def ensure_user_data_dir():
    """Ensures the user_data directory exists."""
    if not os.path.exists(USER_DATA_DIR):
        os.makedirs(USER_DATA_DIR)

def save_question_to_list(list_file, question, topic):
    """Saves a question to a specified list file."""
    ensure_user_data_dir()
    questions = []
    if os.path.exists(list_file):
        with open(list_file, 'r') as f:
            try:
                questions = yaml.safe_load(f) or []
            except yaml.YAMLError:
                questions = []

    # Avoid duplicates
    if not any(q.get('question') == question.get('question') for q in questions):
        question_to_save = question.copy()
        question_to_save['original_topic'] = topic
        questions.append(question_to_save)
        with open(list_file, 'w') as f:
            yaml.dump(questions, f)

def load_questions_from_list(list_file):
    """Loads questions from a specified list file."""
    if not os.path.exists(list_file):
        return []
    with open(list_file, 'r') as file:
        return yaml.safe_load(file) or []

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

def validate_manifest_with_llm(question_dict, user_manifest):
    """Validates a user-submitted manifest using the LLM."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {'correct': False, 'feedback': "INFO: Set GEMINI_API_KEY for AI-powered manifest validation."}

    solution_manifest = question_dict['solution']

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"""
        You are a Kubernetes expert grading a student's YAML manifest for a CKAD exam practice question.
        The student was asked:
        ---
        Question: {question_dict['question']}
        ---
        The student provided this manifest:
        ---
        Student's Manifest:\n{user_manifest}
        ---
        The canonical solution is:
        ---
        Solution Manifest:\n{solution_manifest}
        ---
        Your task is to determine if the student's manifest is functionally correct. The manifests do not need to be textually identical. Check for correct apiVersion, kind, metadata, and spec details.
        First, on a line by itself, write "CORRECT" or "INCORRECT".
        Then, on a new line, provide a brief, one or two-sentence explanation for your decision.
        """
        response = model.generate_content(prompt)
        lines = response.text.strip().split('\n')
        is_correct = lines[0].strip().upper() == "CORRECT"
        feedback = "\n".join(lines[1:]).strip()
        
        return {'correct': is_correct, 'feedback': feedback}
    except Exception as e:
        return {'correct': False, 'feedback': f"Error validating manifest with LLM: {e}"}

def handle_vim_edit(question):
    """Handles the user editing a manifest in Vim."""
    if 'solution' not in question:
        print("This question does not have a solution to validate against for vim edit.")
        return None, None, False

    question_comment = '\n'.join([f'# {line}' for line in question['question'].split('\n')])
    starter_content = question.get('starter_manifest', '')
    
    header = f"{question_comment}\n\n# --- Start your YAML manifest below --- \n"
    full_content = header + starter_content

    with tempfile.NamedTemporaryFile(mode='w+', suffix=".yaml", delete=False) as tmp:
        tmp.write(full_content)
        tmp.flush()
        tmp_path = tmp.name
    
    try:
        subprocess.run(['vim', tmp_path], check=True)
    except FileNotFoundError:
        print("\nError: 'vim' command not found. Please install it to use this feature.")
        os.unlink(tmp_path)
        return None, None, True # Indicates a system error, not a wrong answer
    except Exception as e:
        print(f"\nAn error occurred with vim: {e}")
        os.unlink(tmp_path)
        return None, None, True

    with open(tmp_path, 'r') as f:
        user_manifest = f.read()
    os.unlink(tmp_path)

    if not user_manifest.strip():
        print("Manifest is empty. Marking as incorrect.")
        return user_manifest, {'correct': False, 'feedback': 'The submitted manifest was empty.'}, False

    print("\nValidating manifest with AI...")
    result = validate_manifest_with_llm(question, user_manifest)
    return user_manifest, result, False

def generate_more_questions(topic, existing_question):
    """Generates more questions based on an existing one."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("\nINFO: Set the GEMINI_API_KEY environment variable to generate new questions.")
        return None

    print("\nGenerating a new question... this might take a moment.")
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        question_type = random.choice(['command', 'manifest'])
        prompt = f"""
        You are a Kubernetes expert creating questions for a CKAD study guide.
        Based on the following example question about '{topic}', please generate one new, distinct but related question.

        Example Question:
        ---
        {yaml.dump({'questions': [existing_question]})}
        ---

        Your new question should be a {question_type}-based question.
        - If it's a 'command' question, the solution should be a single or multi-line shell command (e.g., kubectl).
        - If it's a 'manifest' question, the solution should be a complete YAML manifest and the question should be phrased to ask for a manifest.

        The new question should be in the same topic area but test a slightly different aspect or use different parameters.
        Provide the output in valid YAML format, as a single item in a 'questions' list.
        The solution must be correct and working.

        Example for a manifest question:
        questions:
          - question: "Create a manifest for a Pod named 'new-pod'..."
            solution: |
              apiVersion: v1
              kind: Pod
              ...

        Example for a command question:
        questions:
          - question: "Create a pod named 'new-pod' imperatively..."
            solution: "kubectl run new-pod --image=nginx"
        """
        response = model.generate_content(prompt)
        # Clean the response to only get the YAML part
        cleaned_response = response.text.strip()
        if cleaned_response.startswith('```yaml'):
            cleaned_response = cleaned_response[7:]
        if cleaned_response.endswith('```'):
            cleaned_response = cleaned_response[:-3]

        new_question_data = yaml.safe_load(cleaned_response)
        
        if new_question_data and 'questions' in new_question_data and new_question_data['questions']:
            new_q = new_question_data['questions'][0]
            print("\nNew question generated!")
            
            topic_file = f"questions/{topic}.yaml"
            if os.path.exists(topic_file):
                with open(topic_file, 'r+') as f:
                    data = yaml.safe_load(f) or {'questions': []}
                    data['questions'].append(new_q)
                    f.seek(0)
                    yaml.dump(data, f)
                    f.truncate()
                print(f"Added new question to '{topic}.yaml'.")
            return new_q
        else:
            print("\nAI failed to generate a valid question. Please try again.")
            return None
    except Exception as e:
        print(f"\nError generating question: {e}")
        return None

def list_and_select_topic():
    """Lists available topics and prompts the user to select one."""
    ensure_user_data_dir()
    available_topics = sorted([f.replace('.yaml', '') for f in os.listdir('questions') if f.endswith('.yaml')])
    
    has_missed = os.path.exists(MISSED_QUESTIONS_FILE) and os.path.getsize(MISSED_QUESTIONS_FILE) > 0

    if not available_topics and not has_missed:
        print("No question topics found and no missed questions to review.")
        return None

    print("\nPlease select a topic to study:")
    for i, topic_name in enumerate(available_topics):
        print(f"  {i+1}. {topic_name.replace('_', ' ').title()}")
    
    if has_missed:
        print("\nOr, select a special action:")
        print(f"  m. Review Missed Questions")
    
    while True:
        try:
            prompt = f"\nEnter a number (1-{len(available_topics)})"
            if has_missed:
                prompt += " or letter 'm'"
            prompt += ": "
            choice = input(prompt).lower()

            if choice == 'm' and has_missed:
                return '_missed'

            choice_index = int(choice) - 1
            if 0 <= choice_index < len(available_topics):
                return available_topics[choice_index]
            else:
                print("Invalid selection. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number or letter.")
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

    questions = []
    session_topic_name = topic
    if topic == '_missed':
        questions = load_questions_from_list(MISSED_QUESTIONS_FILE)
        session_topic_name = "Missed Questions Review"
        if not questions:
            print("No missed questions to review. Well done!")
            return
    else:
        data = load_questions(topic)
        if not data or 'questions' not in data:
            print("No questions found in the specified topic file.")
            return
        questions = data['questions']

    random.shuffle(questions)

    try:
        question_index = 0
        while question_index < len(questions):
            q = questions[question_index]
            is_correct = False
            
            # For saving to lists, use original topic if reviewing, otherwise current topic
            question_topic_context = q.get('original_topic', topic)

            clear_screen()
            print(f"Question {question_index + 1}/{len(questions)} (Topic: {question_topic_context})")
            print("-" * 40)
            print(q['question'])
            print("-" * 40)
            print("Enter command(s). Type 'done' to check. Special commands: 'solution', 'flag', 'generate', 'vim'.")

            user_commands = []
            special_action = None
            while True:
                try:
                    cmd = input("> ")
                except EOFError:
                    special_action = 'skip'
                    break
                
                cmd_lower = cmd.strip().lower()

                if cmd_lower == 'done':
                    break
                elif cmd_lower in ['solution', 'flag', 'generate', 'skip', 'vim']:
                    special_action = cmd_lower
                    break
                elif cmd.strip():
                    user_commands.append(cmd.strip())

            # --- Process special actions that skip normal grading ---
            if special_action == 'skip':
                pass # Just moves to the next question
            elif special_action == 'solution':
                print("\nSolution:\n")
                solution_text = q.get('solutions', [q.get('solution', 'N/A')])[0]
                print(solution_text)
            elif special_action == 'flag':
                save_question_to_list(FLAGGED_QUESTIONS_FILE, q, question_topic_context)
                print("\nQuestion flagged for review.")
            elif special_action == 'generate':
                new_q = generate_more_questions(question_topic_context, q)
                if new_q:
                    questions.insert(question_index + 1, new_q)
                    print("A new question has been added to this session.")
            elif special_action == 'vim':
                user_manifest, result, sys_error = handle_vim_edit(q)
                if not sys_error:
                    print("\n--- AI Feedback ---")
                    print(result['feedback'])
                    print("-------------------")
                    is_correct = result['correct']
                    if not is_correct:
                        print("\nThat wasn't quite right. Here is the solution:\n")
                        print(q['solution'])
            # --- Process user answer ---
            elif user_commands:
                user_answer = "\n".join(user_commands)
                # Exact match check for 'solutions' (e.g., vim commands)
                if 'solutions' in q:
                    solution_list = [str(s).strip() for s in q['solutions']]
                    user_answer_processed = ' '.join(user_answer.split()).strip()
                    if user_answer_processed in solution_list:
                        is_correct = True
                        print("\nCorrect! Well done.")
                    else:
                        solution_text = solution_list[0]
                # Fuzzy match for single 'solution' (e.g., kubectl commands)
                elif 'solution' in q:
                    solution_text = q['solution'].strip()
                    user_answer_processed = ' '.join(user_answer.split())
                    words = user_answer_processed.split(' ')
                    if words and words[0] == 'k': words[0] = 'kubectl'
                    normalized_user_answer = ' '.join(words)
                    
                    solution_lines = [line.strip() for line in solution_text.split('\n') if not line.strip().startswith('#')]
                    normalized_solution = ' '.join("\n".join(solution_lines).split())
                    
                    if fuzz.ratio(normalized_user_answer, normalized_solution) > 95:
                        is_correct = True
                        print("\nCorrect! Well done.")
                    else:
                        solution_text = q['solution'].strip()
                
                if not is_correct:
                    print("\nNot quite. Here's one possible solution:\n")
                    print(solution_text)
                    print("\n--- AI Feedback ---")
                    feedback = get_llm_feedback(q['question'], user_answer, solution_text)
                    print(feedback)
            
            # --- Post-grading actions ---
            if not is_correct and not special_action:
                save_question_to_list(MISSED_QUESTIONS_FILE, q, question_topic_context)

            question_index += 1
            if question_index < len(questions):
                print("-" * 40)
                input("Press Enter for the next question...")

        clear_screen()
        print("Great job! You've completed all questions for this topic.")
    except KeyboardInterrupt:
        print("\n\nStudy session ended. Goodbye!")

if __name__ == "__main__":
    main()
