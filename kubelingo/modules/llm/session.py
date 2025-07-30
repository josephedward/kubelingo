# Standard library imports
import os
try:
    import llm
    HAS_LLM = True
except ImportError:
    llm = None
    HAS_LLM = False
try:
    import openai
    HAS_OPENAI = True
except ImportError:
    openai = None
    HAS_OPENAI = False
try:
    import questionary
except ImportError:
    questionary = None
from kubelingo.modules.base.session import StudySession

# Global flag: AI explanations enabled only if API key present and backend installed
AI_ENABLED = bool(
    os.environ.get('OPENAI_API_KEY') and (HAS_LLM or HAS_OPENAI)
)
# Flag for command-based AI evaluation (distinct from transcript-based --ai-eval)
AI_EVALUATOR_ENABLED = AI_ENABLED and os.environ.get('KUBELINGO_AI_EVALUATOR', '').lower() in ('1', 'true', 'yes')

# Style settings copied from other modules for consistency
class _AnsiFore:
    CYAN = '\033[36m'
    YELLOW = '\033[33m'
    RED = '\033[31m'

class _AnsiStyle:
    RESET_ALL = '\033[0m'

Fore = _AnsiFore()
Style = _AnsiStyle()

class AIHelper:
    """Helper to generate explanations using llm or OpenAI SDK."""
    # Whether AI explanations are globally enabled (API key and backend present)
    enabled = AI_ENABLED
    def __init__(self, api_key=None):
        # Initialize API key and LLM client if enabled
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        self.client = None
        if not AI_ENABLED:
            return
        # Try Simon Willison's llm client first
        if HAS_LLM and self.api_key:
            try:
                self.client = llm.Client()
                if hasattr(self.client, 'key'):
                    self.client.key = self.api_key
            except Exception:
                self.client = None
        # Fallback to OpenAI SDK
        if self.client is None and HAS_OPENAI and self.api_key:
            try:
                openai.api_key = self.api_key
                self.client = openai.OpenAI(api_key=self.api_key)
            except Exception:
                self.client = None

    def get_explanation(self, question_data):
        """Return an AI-generated explanation for a quiz question."""
        prompt = question_data.get('prompt', '')
        answer = question_data.get('response', '')
        # No AI client available
        if not self.client:
            return ''
        # Default message for YAML exercises
        if not answer:
            answer = "(The answer involves editing a YAML file; see exercise instructions.)"
        # Prepare system and user prompts
        system_prompt = (
            "You are a helpful assistant for a Kubernetes quiz. "
            "Explain why the provided answer is correct. "
            "If it's a YAML edit, describe the necessary changes."
        )
        user_prompt = f"Question: {prompt}\nCorrect Answer: {answer}\n\nExplanation:"
        try:
            # Unified chat completion call
            resp = self.client.chat.completions.create(
                model='gpt-3.5-turbo',
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                temperature=0.2,
                max_tokens=150,
            )
            # Extract content
            if hasattr(resp, 'choices'):
                content = resp.choices[0].message.content
            else:
                content = resp.get('choices', [])[0].get('message', {}).get('content', '')
            return f"{Fore.CYAN}Explanation from AI Assistant:\n{content}{Style.RESET_ALL}"
        except Exception as e:
            # Handle missing API key from llm library
            if e.__class__.__name__ == 'NeedsKey':
                return (
                    f"{Fore.YELLOW}Could not get explanation. OpenAI API key not found. "
                    "Please set OPENAI_API_KEY or run 'llm keys set openai'. "
                    f"{Style.RESET_ALL}"
                )
            return f"{Fore.RED}An error occurred while contacting the AI assistant: {e}{Style.RESET_ALL}"

    def evaluate_answer(self, question_data, user_answer):
        """Return an AI-based evaluation of a user's command-line answer."""
        if not self.client:
            return False, "AI client not available."

        prompt = question_data.get('prompt', '')
        expected_answer = question_data.get('response', '')

        system_prompt = (
            "You are a Kubernetes certification exam evaluator. "
            "Your task is to determine if the user's answer is a valid way to accomplish the task described in the question. "
            "The user might use aliases (e.g., 'k' for 'kubectl') or different flag orders. "
            "Your response must be a JSON object with two keys: 'correct' (a boolean) and 'reasoning' (a brief, one-sentence explanation)."
        )
        user_prompt = f"Question: {prompt}\nExpected Answer: {expected_answer}\nUser's Answer: {user_answer}"

        try:
            resp = self.client.chat.completions.create(
                model='gpt-4o-mini',
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=150,
            )

            content = resp.choices[0].message.content.strip()
            result = json.loads(content)
            return result.get('correct', False), result.get('reasoning', 'No reasoning provided.')
        except Exception as e:
            return False, f"An error occurred during AI evaluation: {e}"

class NewSession(StudySession):
    """A session to get LLM-based help for a quiz question."""

    def __init__(self, logger):
        super().__init__(logger)
        self.ai_helper = AIHelper()

    def initialize(self):
        # No complex initialization needed for this simple case.
        return True

    def run_exercises(self, exercises):
        """
        'exercises' for this session is expected to be a single question dict.
        """
        if not isinstance(exercises, dict):
            print(f"{Fore.RED}LLM Helper: Invalid question data provided.{Style.RESET_ALL}")
            return

        explanation = self.ai_helper.get_explanation(exercises)
        print(explanation)

    def cleanup(self):
        # No cleanup needed.
        pass
