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
