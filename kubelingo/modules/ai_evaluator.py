import json
# Avoid importing llm at top-level to prevent segmentation faults when llm is installed but improperly configured.
llm = None


class AIEvaluator:
    """Uses an AI model to evaluate a user's exercise transcript."""
    def __init__(self):
        """
        Initializes the AIEvaluator.
        It relies on the `llm` package to be configured with an API key
        (e.g., via `llm keys set openai`).
        """
        pass

    def evaluate(self, question_data, transcript, vim_log=None):
        """
        Evaluates a user's performance based on a question and their session transcript.

        Args:
            question_data (dict): The question, including the 'prompt'.
            transcript (str): The full transcript of the user's terminal session.
            vim_log (str, optional): A log of commands executed within Vim.

        Returns:
            dict: A dictionary with 'correct' (bool) and 'reasoning' (str).
        """
        global llm
        if llm is None:
            try:
                import llm as llm_module
                llm = llm_module
            except ImportError:
                return {"correct": False, "reasoning": "AI evaluation failed: `llm` package not installed."}

        prompt = question_data.get('prompt', '')
        validation_steps = question_data.get('validation_steps', [])

        system_prompt = """
You are an expert Kubernetes administrator and trainer. Your task is to evaluate a user's attempt to solve a problem in a sandboxed terminal environment.
Based on the provided question, the expected validation steps, the terminal transcript, and any associated logs (like vim commands), determine if the user successfully completed the task.
Your response MUST be a JSON object with two keys:
1. "correct": a boolean value (true if the user's solution is correct, false otherwise).
2. "reasoning": a string providing a concise explanation for your decision. This will be shown to the user.
"""

        user_content = f"Question: {prompt}\n\n"

        if validation_steps:
            user_content += "A correct solution is expected to pass these validation checks:\n"
            for i, step in enumerate(validation_steps):
                cmd = step.get('cmd', 'No command specified')
                user_content += f"- Step {i+1}: `{cmd}`\n"
            user_content += "\n"

        user_content += f"Terminal Transcript:\n---\n{transcript}\n---\n"
        if vim_log and vim_log.strip():
            user_content += f"Vim Command Log:\n---\n{vim_log}\n---\n"
        
        user_content += "\nBased on the above, please evaluate the user's solution and respond only with the required JSON object."

        try:
            model = llm.get_model("gpt-4-turbo-preview")
            response = model.prompt(
                user_content,
                system=system_prompt
            ).text()
            return json.loads(response)
        except Exception as e:
            return {"correct": False, "reasoning": f"AI evaluation failed: {e}"}


    def _get_system_prompt_for_command_eval(self, quiz_type: str) -> str:
        """Returns a tailored system prompt based on the quiz type."""
        base_prompt = """
You are an expert instructor. Your task is to evaluate a user's attempt to answer a question.
You will be given the question, the user's submitted answer, and a list of expected correct answers.
Your response MUST be a JSON object with two keys:
1. "correct": a boolean value (true if the user's answer is valid and correct, false otherwise).
2. "reasoning": a string providing a concise explanation for your decision. This will be shown to the user.
"""
        if quiz_type == 'k8s':
            return base_prompt + """
You are a Kubernetes expert. The user is answering a question about `kubectl`.
Consider variations, like short resource names (`po` for `pods`) and equivalent flags.
A very common alias for `kubectl` is `k`. Please treat `k` as equivalent to `kubectl`.
It is also common to omit `kubectl` or `k` entirely. If the user provides just a subcommand like `get pods` or `alpha`, you should treat it as if `kubectl` was prepended.
"""
        elif quiz_type == 'vim':
            return base_prompt + """
You are a Vim expert. The user is answering a question about a Vim command.
Consider variations and equivalent commands. For example, if the answer is `:w`, `:write` should also be correct.
"""
        else: # general
            return base_prompt + """
Be lenient with whitespace and case unless the question implies sensitivity.
"""

    def evaluate_command(self, question_data, user_command):
        """
        Evaluates a user's text-based command/answer against a question using an AI model.
        This is a unified method for all text-based quizzes (k8s, vim, general).
        """
        global llm
        if llm is None:
            try:
                import llm as llm_module
                llm = llm_module
            except ImportError:
                return {"correct": False, "reasoning": "AI evaluation failed: `llm` package not installed."}

        prompt = question_data.get('prompt', '')
        category = question_data.get('category', '').lower()
        source_url = question_data.get('source')

        # Determine quiz type for system prompt
        if 'vim' in category:
            quiz_type = 'vim'
        elif any(k in category for k in ['kubectl', 'kubernetes', 'resource types']):
            quiz_type = 'k8s'
        else:
            quiz_type = 'general'

        # Get expected answers
        expected_answers = []
        if question_data.get('response'):
            expected_answers.append(question_data['response'])
        for step in question_data.get('validation_steps', []):
            cmd = step.get('cmd') if isinstance(step, dict) else getattr(step, 'cmd', None)
            if cmd:
                expected_answers.append(cmd)
        
        system_prompt = self._get_system_prompt_for_command_eval(quiz_type)
        if source_url:
            system_prompt += f"\nIf a source URL is provided, please cite it in your reasoning."

        user_content = f"Question: {prompt}\n\n"
        user_content += f"User's answer: `{user_command}`\n\n"
        if expected_answers:
            user_content += "Expected answer(s) (for reference):\n"
            for ans in expected_answers:
                user_content += f"- `{ans}`\n"
            user_content += "\n"
        
        if source_url:
            user_content += f"Source URL: {source_url}\n\n"

        user_content += "\nBased on the above, please evaluate the user's answer and respond only with the required JSON object."

        try:
            model = llm.get_model("gpt-4-turbo-preview")
            response = model.prompt(
                user_content,
                system=system_prompt
            ).text()
            return json.loads(response)
        except Exception as e:
            return {"correct": False, "reasoning": f"AI evaluation failed: {e}"}
