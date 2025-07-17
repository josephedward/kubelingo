import os
import llm
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

# Integrates with LLM to provide explanations for quiz questions.
class AIHelper:
    def __init__(self, api_key=None):
        # api_key is passed for compatibility, but llm handles its own key management.
        # If passed, we can set it on the model.
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = None
        try:
            self.model = llm.get_model("gpt-3.5-turbo")
            if self.api_key:
                self.model.key = self.api_key
        except llm.UnknownModelError:
            self.model = None

    def get_explanation(self, question_data):
        prompt = question_data.get('prompt', '')
        answer = question_data.get('response', '')

        if not self.model:
            return (
                f"{Fore.YELLOW}Could not get explanation. "
                f"The 'llm-openai' plugin may not be installed. "
                f"Try 'pip install llm-openai'.{Style.RESET_ALL}"
            )

        # Handle empty/missing answers, which can happen for YAML edit questions
        if not answer:
            answer = "(The answer involves editing a YAML file, so no single command is provided.)"

        try:
            system_prompt = (
                "You are a helpful assistant for a Kubernetes quiz. "
                "Explain why the provided answer is correct for the given question. "
                "If the answer is a YAML edit, explain the necessary changes."
            )
            user_prompt = f"Question: {prompt}\nCorrect Answer: {answer}\n\nExplanation:"
            # Use the model's client, which is a compatible OpenAI client
            response = self.model.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=150,
            )
            # Extract content from response
            explanation = response.choices[0].message.content or ''
            return f"{Fore.CYAN}Explanation from AI Assistant:\n{explanation}{Style.RESET_ALL}"
        except llm.NeedsKey:
            return (
                f"{Fore.YELLOW}Could not get explanation. OpenAI API key not found. "
                f"Please set OPENAI_API_KEY environment variable or run 'llm keys set openai'.{Style.RESET_ALL}"
            )
        except Exception as e:
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
