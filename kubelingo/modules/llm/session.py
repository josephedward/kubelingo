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
except ImportError:
    openai = None
try:
    import questionary
except ImportError:
    questionary = None
from kubelingo.modules.base.session import StudySession

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
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        if not self.api_key:
            key = None
            try:
                if questionary:
                    # Use password prompt if available to mask input
                    if hasattr(questionary, 'password'):
                        key = questionary.password("Enter your OpenAI API key:").ask()
                    else:
                        key = questionary.text("Enter your OpenAI API key:").ask()
                else:
                    key = input("Enter your OpenAI API key: ").strip()
            except (EOFError, KeyboardInterrupt):
                key = None
            self.api_key = key

        if not self.api_key:
            print(f"{Fore.YELLOW}OPENAI_API_KEY not set; skipping AI explanations.{Style.RESET_ALL}")
        self.client = None
        # Try Simon Willison's llm client first
        if HAS_LLM:
            try:
                self.client = llm.Client()
                # Some llm clients allow setting key attribute
                if self.api_key and hasattr(self.client, 'key'):
                    self.client.key = self.api_key
            except Exception:
                self.client = None
        # Fallback to OpenAI SDK
        if self.client is None and openai and self.api_key:
            openai.api_key = self.api_key
            try:
                self.client = openai.OpenAI(api_key=self.api_key)
            except Exception:
                self.client = None

    def get_explanation(self, question_data):
        """Return an AI-generated explanation for a quiz question."""
        prompt = question_data.get('prompt', '')
        answer = question_data.get('response', '')
        # No AI client available
        if not self.client:
            return (
                f"{Fore.YELLOW}Could not get explanation. "
                "Install LLM dependencies (pip install -e '.[llm]') and ensure OPENAI_API_KEY is set. "
                f"{Style.RESET_ALL}"
            )
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
