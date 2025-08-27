import os
import yaml
from colorama import Fore, Style
import sys # For print statements
try:
    import google.generativeai as genai
except ImportError:
    genai = None

# Assuming QUESTIONS_DIR is defined elsewhere or passed
# For now, I'll define it here, and then remove it from kubelingo.py
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, os.pardir))
_ROOT_QUESTIONS = os.path.join(_PROJECT_ROOT, "questions")
_PKG_QUESTIONS = os.path.join(_SCRIPT_DIR, "questions")
QUESTIONS_DIR = os.getenv(
    "KUBELINGO_QUESTIONS_DIR",
    _ROOT_QUESTIONS if os.path.isdir(_ROOT_QUESTIONS) else _PKG_QUESTIONS
)

def _get_llm_model(model_name="gemini-pro"):
    """Initializes and returns the generative AI model."""
    if not genai:
        print(f"{Fore.RED}Google Generative AI SDK not found. Please install it with 'pip install google-generativeai'{Style.RESET_ALL}")
        return None
    try:
        # Configure the API key
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        # Create the model
        model = genai.GenerativeModel(model_name)
        return model
    except Exception as e:
        print(f"{Fore.RED}Error initializing the model: {e}{Style.RESET_ALL}")
        # Look for the API key in the environment variables
        if "GEMINI_API_KEY" not in os.environ:
            print(f"{Fore.YELLOW}GEMINI_API_KEY not found in environment variables.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Please set it to your Google AI Studio API key.{Style.RESET_ALL}")
        return None

def get_normalized_question_text(question_dict):
    return question_dict.get('question', '').strip().lower()

def load_questions(topic, Fore, Style, genai): # Added Fore, Style, genai as arguments
    """Loads questions from a YAML file based on the topic."""
    file_path = os.path.join(QUESTIONS_DIR, f"{topic}.yaml")
    if not os.path.exists(file_path):
        print(f"Error: Question file not found at {file_path}")
        available_topics = [f.replace('.yaml', '') for f in os.listdir(QUESTIONS_DIR) if f.endswith('.yaml')]
        if available_topics:
            print("Available topics: " + ", ".join(available_topics))
        return None
    
    with open(file_path, 'r') as file:
        data = yaml.safe_load(file)
    
    if data and 'questions' in data:
        updated = False
        # Import assign_source locally to avoid circular dependency
        from kubelingo.question_generator import assign_source
        for q in data['questions']:
            if assign_source(q, topic, Fore, Style, genai): # Pass Fore, Style, genai
                updated = True
        
        if updated:
            with open(file_path, 'w') as file:
                yaml.dump(data, file, sort_keys=False)
    
    return data

def remove_question_from_corpus(question_to_remove, topic):
    """Removes a question from its source YAML file."""
    file_path = os.path.join(QUESTIONS_DIR, f"{topic}.yaml")
    if not os.path.exists(file_path):
        print(f"{Fore.RED}Error: Source file not found for topic {topic}. Cannot remove question.{Style.RESET_ALL}")
        return

    with open(file_path, 'r') as file:
        data = yaml.safe_load(file)

    if data and 'questions' in data:
        original_num_questions = len(data['questions'])
        normalized_q_to_remove = get_normalized_question_text(question_to_remove)
        
        # Filter out the question to remove
        data['questions'] = [
            q for q in data['questions']
            if get_normalized_question_text(q) != normalized_q_to_remove
        ]

        if len(data['questions']) < original_num_questions:
            with open(file_path, 'w') as file:
                yaml.dump(data, file, sort_keys=False)
            print(f"{Fore.GREEN}Question removed from {topic}.yaml.{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}Question not found in {topic}.yaml. No changes made.{Style.RESET_ALL}")
    else:
        print(f"{Fore.YELLOW}No questions found in {topic}.yaml. No changes made.{Style.RESET_ALL}")