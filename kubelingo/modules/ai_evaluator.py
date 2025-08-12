import json
import os
import re
import logging
from kubelingo.integrations.llm import get_llm_client


class AIEvaluator:
    """Uses an AI model to evaluate a user's exercise transcript."""
    def __init__(self):
        """
        Initializes the AIEvaluator. It will use the configured LLM client.
        """
        self.client = None
        try:
            # Use the globally configured provider, defaulting to gemini
            provider = os.environ.get("AI_PROVIDER", "gemini").lower()
            self.client = get_llm_client(provider)
        except Exception as e:
            logging.error(f"Failed to initialize LLM client for AIEvaluator: {e}")

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
        if not self.client:
            return {"correct": False, "reasoning": "AI evaluation client not available."}

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
        # Provide extra guidance for API group/version questions
        if 'API' in prompt or 'version' in prompt:
            system_prompt += (
                "\nWhen the question involves Kubernetes API groups or versions, "
                "your reasoning must include an explanation of the API group and why the resource belongs to that group. "
                "For example, for TokenReview, explain that it is part of the 'authentication.k8s.io' API group "
                "because it is used to validate tokens as part of Kubernetes' authentication API."
            )


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
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ]
            response_text = self.client.chat_completion(
                messages=messages
            )
            return json.loads(response_text) if response_text else None
        except Exception as e:
            return {"correct": False, "reasoning": f"AI evaluation failed: {e}"}

    def find_source_for_question(self, question_prompt: str):
        """
        Finds a documentation source URL for a given question prompt using an AI model.
        """
        if not self.client:
            logging.error("Cannot find source, AI client not available.")
            return None

        system_prompt = (
            "You are a Kubernetes documentation expert. Your task is to find the most relevant "
            "official Kubernetes documentation URL for the user's question. The URL should be as specific as possible, "
            "pointing to the exact page or anchor if possible. Respond ONLY with the URL, and nothing else."
        )
        user_content = f"Question: \"{question_prompt}\""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        response_text = self.client.chat_completion(
            messages=messages
        )

        if response_text:
             url_match = re.search(r'(https?://[^\s]+)', response_text.strip())
             if url_match:
                 return url_match.group(1)
        return None

    def generate_question(self, base_question: dict):
        """
        Generates a new question similar to a base question using an AI model.
        The generated question's commands are validated for syntax.
        """
        if not self.client:
            logging.error("Cannot generate question, AI client not available.")
            return None

        from kubelingo.utils.validation import validate_kubectl_syntax

        prompt_text = (
            f"Generate a new Kubernetes quiz question similar to this one, but not identical. "
            f"Original question prompt: \"{base_question.get('prompt')}\".\n"
            f"The original question's validation steps are: {base_question.get('validation_steps')}\n\n"
            "Your task is to create a new, distinct question that tests a similar concept. "
            "For example, if the original asks to create a pod, you could ask to create a different pod with a different name or image. "
            "If it asks to get logs, ask for logs from a different resource.\n"
            "The `validation_steps` you provide must contain syntactically valid `kubectl` commands.\n"
            "Respond ONLY with a valid JSON object containing 'prompt' and 'validation_steps' keys. The 'validation_steps' must be a list of objects, each with a 'cmd' key."
        )
        system_prompt = "You are an expert Kubernetes instructor creating quiz questions. You generate valid JSON."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_text},
        ]
        response_text = self.client.chat_completion(
            messages=messages,
            temperature=0.7,
            json_mode=True
        )

        if not response_text:
            return None

        try:
            new_q = json.loads(response_text)
        except json.JSONDecodeError:
            return None
        # Validate the generated question structure
        if not isinstance(new_q, dict) or 'prompt' not in new_q or 'validation_steps' not in new_q:
            return None
        # Validate each step's syntax
        # Validate generated commands with kubectl syntax checker
        for step in new_q.get('validation_steps', []):
            cmd = step.get('cmd')
            if cmd:
                validation_result = validate_kubectl_syntax(cmd)
                if not validation_result.get('valid'):
                    # Discard if syntax invalid
                    return None
        return new_q


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
You are a Vim expert. The user is answering a question about a Vim command. Be precise about Vim's modes (Normal mode vs. Command-line mode).
- Normal mode commands (e.g., `dd`, `yy`, `p`) are run from Vim's default mode and do not need a colon.
- Command-line mode commands (e.g., `:w`, `:q!`) start with a colon to bring up the command line.

If a user incorrectly adds a colon to a Normal mode command (e.g., entering `:dd` when `dd` is expected), you MUST mark it as correct if their intent is clear. However, your reasoning should gently explain that the command runs in Normal mode and doesn't require a colon.

Also, consider these equivalent commands:
- For saving: `:w` and `:write` are equivalent.
- For saving and quitting: `:wq` and `:x` are equivalent Command-line mode commands. `ZZ` is an equivalent Normal mode command.
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
        if not self.client:
            return {"correct": False, "reasoning": "AI evaluation client not available."}

        # Load question prompt and category (ensure category is a string before lowercasing)
        prompt = question_data.get('prompt', '')
        # Protect against None and non-string category values
        raw_cat = question_data.get('category')
        category = raw_cat.lower() if isinstance(raw_cat, str) else ''
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
        
        # Normalize command based on quiz type for robust evaluation
        cmd_input = (user_command or '').strip()
        if quiz_type == 'k8s':
            if cmd_input == 'k':
                user_command = 'kubectl'
            elif cmd_input.startswith('k '):
                user_command = 'kubectl' + cmd_input[1:]
            else:
                # For k8s questions, if command doesn't start with 'kubectl' or 'k',
                # and it matches a known kubectl command, prepend 'kubectl'.
                known_kubectl_commands = {
                    "alpha", "annotate", "api-resources", "api-versions", "apply", "attach", "auth",
                    "autoscale", "certificate", "cluster-info", "completion", "config", "convert",
                    "cordon", "cp", "create", "delete", "describe", "diff", "drain", "edit", "events",
                    "exec", "explain", "expose", "get", "kustomize", "label", "logs", "options",
                    "patch", "plugin", "port-forward", "proxy", "replace", "rollout", "run", "scale",
                    "set", "taint", "top", "uncordon", "version", "wait"
                }
                first_word = cmd_input.split(' ')[0] if cmd_input else ''
                if first_word in known_kubectl_commands and not cmd_input.startswith('kubectl '):
                    user_command = 'kubectl ' + cmd_input
        
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
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ]
            response_text = self.client.chat_completion(
                messages=messages
            )
            return json.loads(response_text) if response_text else None
        except Exception as e:
            return {"correct": False, "reasoning": f"AI evaluation failed: {e}"}
