import logging
import json
import random
import uuid
from typing import List, Set

from kubelingo.modules.ai_evaluator import AIEvaluator
from kubelingo.question import Question, ValidationStep
from kubelingo.utils.validation import (
    validate_kubectl_syntax,
    validate_prompt_completeness,
)

logger = logging.getLogger(__name__)


class AIQuestionGenerator:
    """
    Generates questions about Kubernetes subjects using an AI model.
    Wraps AIEvaluator to generate and validate questions about specific
    Kubernetes subjects.
    """

    def __init__(self, max_attempts_per_question: int = 5):
        self.evaluator = AIEvaluator()
        self.max_attempts = max_attempts_per_question

    def generate_questions(
        self,
        subject: str,
        num_questions: int = 1,
        base_questions: List[Question] = None,
    ) -> List[Question]:
        """
        Generates new questions by "cloning" from a list of base questions using an AI model.

        It inspects the format of the base questions (command-based vs. shell-based)
        and asks the AI to generate a new question in the same format.
        Generated questions are validated for correctness and completeness.

        Returns a list of valid, newly generated Question objects.
        """
        if not base_questions:
            logger.warning(
                "AI generation skipped: cannot generate questions without base questions."
            )
            return []

        questions: List[Question] = []
        seen_prompts: Set[str] = {q.prompt for q in base_questions}
        is_command_based = bool(base_questions[0].response)

        if is_command_based:
            system_prompt = (
                "You are an expert Kubernetes administrator and trainer. Your task is to generate a new quiz question "
                "that is a variation of an existing one.\nThe new question should test the same concept but be worded "
                "differently and have a different target resource or parameter.\nYou will be given a base question as a JSON object.\n"
                'Your response MUST be a JSON object containing the new question, with "prompt" and "response" keys. '
                "The 'response' must be a single, valid `kubectl` command.\nThe generated prompt must contain all "
                "necessary information for a user to be able to formulate the response/command. For example, if the "
                "response is 'kubectl get pod my-pod', the prompt must mention 'my-pod'."
            )
            output_keys = ["prompt", "response"]
        else:  # shell-based
            system_prompt = (
                "You are an expert Kubernetes administrator and trainer. Your task is to generate a new quiz question "
                "that is a variation of an existing one.\nThe new question should test the same concept but be worded "
                "differently and have a different target resource or parameter.\nYou will be given a base question as a JSON object.\n"
                'Your response MUST be a JSON object containing the new question, with "prompt" and "validation_steps" keys. '
                "The validation steps must be correct for the new prompt."
            )
            output_keys = ["prompt", "validation_steps"]

        for _ in range(num_questions):
            for attempt in range(self.max_attempts):
                base_q = random.choice(base_questions)
                # We need a simplified dict representation for the prompt
                base_q_dict = {"prompt": base_q.prompt}
                if is_command_based:
                    base_q_dict["response"] = base_q.response
                else:
                    base_q_dict["validation_steps"] = [
                        step.__dict__ for step in (base_q.validation or [])
                    ]

                user_prompt = f"{system_prompt}\n\nHere is the base question to vary:\n{json.dumps(base_q_dict)}"

                try:
                    raw_q = self.evaluator.generate_question({"prompt": user_prompt})

                    if not raw_q or not all(k in raw_q for k in output_keys):
                        logger.debug(
                            f"AI response missing required keys ({output_keys}). Retrying."
                        )
                        continue

                    prompt = raw_q["prompt"].strip()
                    if prompt in seen_prompts:
                        logger.debug(f"Skipping duplicate question: '{prompt}'")
                        continue

                    if is_command_based:
                        response = raw_q["response"].strip()
                        # 1. Validate kubectl command syntax
                        syntax_check = validate_kubectl_syntax(response)
                        if not syntax_check["valid"]:
                            logger.debug(
                                f"Generated command failed syntax check: {syntax_check['errors']}. Retrying."
                            )
                            continue
                        # 2. Validate prompt has enough info for the command
                        completeness_check = validate_prompt_completeness(
                            response, prompt
                        )
                        if not completeness_check["valid"]:
                            logger.debug(
                                f"Generated prompt failed completeness check: {completeness_check['errors']}. Retrying."
                            )
                            continue

                        new_question = Question(
                            id=f"ai-gen-{uuid.uuid4()}",
                            prompt=prompt,
                            response=response,
                            category=base_q.category,
                            # validation will be empty for command-based questions
                        )
                    else:  # shell-based
                        validation_steps_data = raw_q["validation_steps"]
                        if (
                            not validation_steps_data
                            or not isinstance(validation_steps_data, list)
                            or not validation_steps_data[0].get("cmd")
                        ):
                            logger.debug(
                                "Generated question missing valid validation_steps. Retrying."
                            )
                            continue

                        validation_steps = [
                            ValidationStep(**step) for step in validation_steps_data
                        ]
                        response = validation_steps[0].cmd if validation_steps else ""

                        new_question = Question(
                            id=f"ai-gen-{uuid.uuid4()}",
                            prompt=prompt,
                            response=response,
                            validation=validation_steps,
                            category=base_q.category,
                        )

                    seen_prompts.add(prompt)
                    questions.append(new_question)
                    logger.info(
                        f"Successfully generated and validated a new question: {prompt}"
                    )
                    break  # Success, move to next question

                except Exception as e:
                    logger.error(
                        f"Error during AI question generation or validation: {e}"
                    )
            else:  # No break from attempt loop
                logger.warning(
                    f"Could not generate a valid question for subject '{subject}' after {self.max_attempts} attempts."
                )

        if len(questions) < num_questions:
            logger.warning(
                "Failed to generate the requested number of questions. "
                f"Got {len(questions)} out of {num_questions}."
            )

        return questions
