import os
import json
import subprocess
from kubelingo.modules.base.session import StudySession

class AIProcessor:
    """Class that uses llm-gemini to process and format questions."""
    def __init__(self):
        # Ensure llm-gemini is installed
        try:
            subprocess.run(["llm", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except FileNotFoundError:
            raise RuntimeError("llm-gemini is not installed. Please install it using 'llm install llm-gemini'.")

    def format_questions(self, raw_data):
        """
        Takes raw data from user file and formats it into Kubelingo question format using llm-gemini.
        """
        print("AI Processor: Formatting questions using llm-gemini...")
        questions = []
        for item in raw_data:
            if 'prompt' in item and 'response' in item:
                # Use llm-gemini to process the question
                try:
                    result = subprocess.run(
                        ["llm", "-m", "gemini-2.0-flash", "-o", "json_object", f"Categorize: {item['prompt']}"],
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    gemini_output = json.loads(result.stdout)
                    questions.append({
                        'category': gemini_output.get('exercise_category', 'custom'),
                        'prompt': item['prompt'],
                        'response': item['response'],
                        'explanation': item.get('explanation', ''),
                        'type': 'command',
                        'subject_matter': gemini_output.get('subject_matter', 'Unknown')
                    })
                except Exception as e:
                    print(f"Error processing question with llm-gemini: {e}")
        return questions

class NewSession(StudySession):
    """A study session for custom, user-provided quizzes."""

    def __init__(self, logger):
        super().__init__(logger)
        self.custom_questions_file = None
        self.questions = []
        self.ai_processor = AIProcessor()

    def initialize(self):
        """Initializes the session by getting the path to custom questions."""
        print("Custom module loaded. Please provide the path to your questions file.")
        try:
            file_path = input("Enter file path: ").strip()
            if os.path.exists(file_path):
                self.custom_questions_file = file_path
                return True
            else:
                print(f"Error: File not found at '{file_path}'")
                return False
        except (EOFError, KeyboardInterrupt):
            print("\nInitialization cancelled.")
            return False

    def run_exercises(self, exercises):
        """
        Loads, processes, and runs the custom quiz.
        The 'exercises' param is ignored, as this module loads its own.
        """
        if not self.custom_questions_file:
            print("Cannot run exercises, no questions file provided.")
            return

        try:
            with open(self.custom_questions_file, 'r') as f:
                # Assuming JSON for now. The AI part would handle unstructured text.
                raw_data = json.load(f)
        except Exception as e:
            print(f"Error reading or parsing questions file: {e}")
            return
        
        self.questions = self.ai_processor.format_questions(raw_data)

        if not self.questions:
            print("No valid questions found in the provided file.")
            return

        # For a stub, we'll just print the loaded questions.
        print(f"\nSuccessfully loaded {len(self.questions)} custom questions.")
        for i, q in enumerate(self.questions, 1):
            print(f"  {i}. Q: {q['prompt']} -> A: {q['response']}")

    def cleanup(self):
        """Cleans up any session-related resources."""
        # Nothing to clean up in this stub.
        pass
