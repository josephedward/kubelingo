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
        source_url = question_data.get('source') or question_data.get('citation')

        system_prompt = """
You are an expert Kubernetes administrator and trainer. Your task is to evaluate a user's attempt to solve a problem in a sandboxed terminal environment.
Based on the provided question, the expected validation steps, the terminal transcript, and any associated logs (like vim commands), determine if the user successfully completed the task.
Your response MUST be a JSON object with two keys:
1. "correct": a boolean value (true if the user's solution is correct, false otherwise).
2. "reasoning": a string providing a concise explanation for your decision. If the user's solution is correct, briefly affirm it. If incorrect, explain what went wrong and suggest the correct approach or command(s). This will be shown to the user.
"""
        if source_url:
            system_prompt += "\nA source URL is provided. You MUST include it in your reasoning."


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
        
        if source_url:
            user_content += f"Source URL: {source_url}\n\n"
        
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
You will be given the question, the user's submitted answer, and a list of one or more "expected" or "correct" answers.
Your primary goal is to determine if the user's answer is functionally equivalent to any of the provided expected answers.

If the user's answer is equivalent to an expected answer, you MUST evaluate it as correct.
Do not overthink the question or seek alternative solutions. The provided expected answers are the ground truth for the quiz, even if they contain potential errors.
Be lenient with minor typos (e.g., 'whomai' for 'whoami') if the user's intent is obvious. The goal is to test knowledge, not just typing accuracy.

Your response MUST be a JSON object with two keys:
1. "correct": a boolean value (true if the user's answer is valid and correct, false otherwise).
2. "reasoning": a string providing a concise explanation for your decision. If the answer is correct, briefly affirm it. If incorrect, explain the mistake and provide one or more correct answers with context. This will be shown to the user.
"""
        if quiz_type == 'k8s':
            return base_prompt + """
You are a Kubernetes expert. The user is answering a question about `kubectl`.
Users may use common aliases. You MUST treat `k` as a perfect alias for `kubectl`.
Similarly, if the user provides a command without `kubectl` or `k` (e.g., `get pods`), treat it as if `kubectl` was prepended.
Evaluate valid aliases and shorthands as correct without commenting on their use.
Also consider resource shorthands (e.g., `po` for `pods`) and equivalent flags.
If a question is general (e.g., "list all daemon sets"), and the user provides a command that is more specific but still correct (e.g., `kubectl get ds -A` to list across all namespaces), you MUST evaluate it as correct. The user's answer should only be marked incorrect if it fails to accomplish the core task of the question.
For `kubectl exec`, a common mistake is omitting the space after `--`. For example, `kubectl exec my-pod --date` instead of `kubectl exec my-pod -- date`. If the user makes this mistake but their intent is clear, mark it as correct but gently explain the proper syntax in your reasoning.
"""
        elif quiz_type == 'vim':
            return base_prompt + """
You are a Vim expert. The user is answering a question about a Vim command.
Consider variations and equivalent commands. For example, if the answer is `:w`, `:write` should also be correct.
For normal mode commands (like `dd`, `yy`), users might incorrectly add a colon (`:`). If the user's intent is clear, you MUST mark it as correct, but you can gently clarify the proper syntax in your reasoning.
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

        # Normalize common kubectl alias 'k' to full command for evaluation
        cmd_input = (user_command or '').strip()
        if cmd_input == 'k':
            user_command = 'kubectl'
        elif cmd_input.startswith('k '):
            # Replace leading 'k' alias with 'kubectl'
            user_command = 'kubectl' + cmd_input[1:]
        # Load question prompt and category
        prompt = question_data.get('prompt', '')
        category = question_data.get('category', '').lower()
        # Citation or source URL for LLM context
        source_url = question_data.get('source') or question_data.get('citation')

        # Get expected answers
        expected_answers = []
        resp = question_data.get('response')
        if resp:
            expected_answers.append(resp)

        validator = question_data.get('validator', {})
        if isinstance(validator, dict) and validator.get('expected'):
            expected_answers.append(validator['expected'])

        for step in question_data.get('validation_steps', []):
            cmd = step.get('cmd') if isinstance(step, dict) else getattr(step, 'cmd', None)
            if cmd:
                expected_answers.append(cmd)

        # Determine quiz type for system prompt.
        # This is important for providing the correct context to the AI (e.g., for kubectl aliases).
        is_k8s = (
            any(k in category for k in ['kubectl', 'kubernetes', 'resource types']) or
            'kubectl' in prompt.lower() or 'kubernetes' in prompt.lower() or
            any('kubectl' in ans.lower() for ans in expected_answers)
        )

        if 'vim' in category:
            quiz_type = 'vim'
        elif is_k8s:
            quiz_type = 'k8s'
        else:
            quiz_type = 'general'
        
        system_prompt = self._get_system_prompt_for_command_eval(quiz_type)
        if source_url:
            system_prompt += "\nA source URL is provided. You MUST include it in your reasoning."

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
