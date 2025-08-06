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
            "an operation on that resource."
        )

        # Give it enough attempts to generate the desired number of unique questions
        for _ in range(self.max_attempts * num_questions):
            if len(questions) >= num_questions:
                break

            user_prompt = f"{system_prompt}\n\nGenerate 1 distinct question about {subject}."

            try:
                # Based on user's sketch. It defines a system prompt, so we pass it.
                # AIEvaluator.generate_question is assumed to accept a dict.
                raw_q = self.evaluator.generate_question(
                    {"prompt": user_prompt, "validation_steps": []}
                )

                if not raw_q or "prompt" not in raw_q or "validation_steps" not in raw_q:
                    logger.warning("AI generation returned invalid format. Retrying.")
                    continue

                prompt = raw_q["prompt"].strip()
                # 1) No exact duplicates
                if prompt in seen_prompts:
                    logger.warning(f"Skipping duplicate question: '{prompt}'")
                    continue
                # 2) Must mention the subject
                if not re.search(fr"\b{re.escape(subject)}\b", prompt, re.IGNORECASE):
                    logger.warning(f"Generated prompt does not mention subject '{subject}'. Retrying.")
                    continue
                # 3) Must mention “named <something>”
                if not re.search(r"named ['\"][A-Za-z0-9\-\_]+['\"]", prompt):
                    logger.warning("Generated prompt does not include a resource name. Retrying.")
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

            except Exception as e:
                logger.error(f"Error during AI question generation or validation: {e}")

        if len(questions) < num_questions:
            logger.warning(
                "Failed to generate the requested number of questions. "
                f"Got {len(questions)} out of {num_questions}."
            )

        return questions
