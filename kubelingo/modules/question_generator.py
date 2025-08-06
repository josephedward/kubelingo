import logging
import re
import uuid
from typing import List, Set

from kubelingo.modules.ai_evaluator import AIEvaluator
from kubelingo.question import Question, ValidationStep

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
        self, subject: str, num_questions: int = 1
    ) -> List[Question]:
        """
        Ask the LLM to generate kubectl questions about `subject`, and validate
        that they mention the resource kind, a name, and any needed flags.

        Returns a list of Question objects.
        """
        questions: List[Question] = []
        seen_prompts: Set[str] = set()

        system_prompt = (
            "You are a Kubernetes quiz‐generator. Produce JSON with keys "
            "'prompt' and 'validation_steps' only. The prompt must:"
            f"\n  • mention the resource kind exactly: “{subject}”"
            "\n  • include a resource name, e.g. “named 'foo-sa'”"
            "\n  • specify any namespace or flags required to scope the command"
            "\nGenerate a question that asks the user to run `kubectl` to perform "
            "an operation like 'create' or 'get' on that resource."
        )

        for _ in range(num_questions):
            for attempt in range(self.max_attempts):
                user_prompt = f"{system_prompt}\n\nGenerate 1 distinct question about {subject}."

                try:
                    raw_q = self.evaluator.generate_question(
                        {"prompt": user_prompt, "validation_steps": []}
                    )

                    if not raw_q or "prompt" not in raw_q or "validation_steps" not in raw_q:
                        logger.debug("AI generation returned invalid format. Retrying.")
                        continue

                    prompt = raw_q["prompt"].strip()
                    # 1) No exact duplicates
                    if prompt in seen_prompts:
                        logger.debug(f"Skipping duplicate question: '{prompt}'")
                        continue
                    # 2) Must mention the subject
                    if not re.search(fr"\b{re.escape(subject)}\b", prompt, re.IGNORECASE):
                        logger.debug(f"Generated prompt does not mention subject '{subject}'. Retrying.")
                        continue
                    # 3) Must ask to create or get a named resource
                    if not re.search(r"\b(create|get)\b", prompt, re.IGNORECASE):
                        logger.debug("Generated prompt does not mention 'create' or 'get'. Retrying.")
                        continue
                    if not re.search(r"named ['\"][A-Za-z0-9\-\_]+['\"]", prompt):
                        logger.debug("Generated prompt does not include a resource name. Retrying.")
                        continue

                    seen_prompts.add(prompt)
                    validation_steps = [
                        ValidationStep(**step) for step in raw_q["validation_steps"]
                    ]
                    response = ""
                    if (
                        validation_steps
                        and hasattr(validation_steps[0], "cmd")
                        and validation_steps[0].cmd
                    ):
                        response = validation_steps[0].cmd

                    questions.append(
                        Question(
                            id=f"ai-gen-{uuid.uuid4()}",
                            prompt=prompt,
                            response=response,
                            validation=validation_steps,
                        )
                    )
                    logger.info(f"Successfully generated and validated a new question: {prompt}")
                    # Break from attempt loop and generate next question
                    break

                except Exception as e:
                    logger.error(f"Error during AI question generation or validation: {e}")
            else:  # This else belongs to the inner for loop, executed if it's not broken out of
                logger.warning(f"Could not generate a valid question for {subject} after {self.max_attempts} attempts.")


        if len(questions) < num_questions:
            logger.warning(
                "Failed to generate the requested number of questions. "
                f"Got {len(questions)} out of {num_questions}."
            )

        return questions
