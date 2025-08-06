import logging
import json
import uuid
from typing import List, Set

import openai
from kubelingo.modules.ai_evaluator import AIEvaluator
from kubelingo.question import Question, ValidationStep
from kubelingo.utils.validation import validate_kubectl_syntax

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
        Ask the LLM to generate kubectl questions about `subject`, and validate
        their syntax.

        Returns a list of Question objects.
        """
        questions: List[Question] = []

        system_prompt = (
            "You are a Kubernetes quiz‐generator. Produce JSON with keys "
            "'prompt' and 'validation_steps' only. The prompt must:"
            f"\n  • mention the resource kind exactly: “{subject}”"
            "\n  • include a resource name, e.g. “named 'foo-sa'”"
            "\n  • specify any namespace or flags required to scope the command"
            "\nGenerate a question that asks the user to run `kubectl` to perform "
            "an operation like 'create' or 'get' on that resource."
        )

        # Bulk-generate if requesting multiple questions in one shot
        if num_questions > 1:
            user_prompt = (
                f"{system_prompt}\n\n"
                f"Generate exactly {num_questions} distinct Kubernetes quiz questions about '{subject}'. "
                "Respond only with a JSON array of objects, each with keys 'prompt' and 'validation_steps', where 'validation_steps' is a list of {'cmd':<kubectl command>} objects."
            )
            logger.debug("Bulk generation prompt: %s", user_prompt)
            try:
                resp_obj = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.7,
                )
                resp = resp_obj.choices[0].message.content
                logger.debug("Bulk generation response: %s", resp)
                raw_list = json.loads(resp)
            except Exception as e:
                logger.error(f"Bulk AI question generation error: {e}")
                return questions
            # Validate and convert each question
            for raw_q in raw_list or []:
                if not isinstance(raw_q, dict) or "prompt" not in raw_q or "validation_steps" not in raw_q:
                    continue
                # Build validation steps
                steps = []
                valid = True
                for step in raw_q.get("validation_steps", []):
                    cmd = step.get("cmd")
                    if not cmd or not validate_kubectl_syntax(cmd).get("valid"):
                        valid = False
                        break
                    steps.append(ValidationStep(cmd=cmd, matcher={}))
                if not valid:
                    continue
                qid = f"ai-gen-{uuid.uuid4()}"
                resp_cmd = steps[0].cmd if steps else ""
                questions.append(
                    Question(
                        id=qid,
                        prompt=raw_q["prompt"].strip(),
                        response=resp_cmd,
                        validation=steps,
                    )
                )
            return questions
        # Fallback: generate one question at a time (legacy flow)
        for _ in range(num_questions):
            for attempt in range(self.max_attempts):
                user_prompt = f"{system_prompt}\n\nGenerate 1 distinct question about {subject}."
                try:
                    raw_q = self.evaluator.generate_question(
                        {"prompt": user_prompt, "validation_steps": []}
                    )
                except Exception as e:
                    logger.error(f"Error during AI question generation: {e}")
                    continue
                if not raw_q or not isinstance(raw_q, dict):
                    continue
                # Convert and validate syntax only
                prompt = raw_q.get("prompt", "").strip()
                steps = []
                valid = True
                for step in raw_q.get("validation_steps", []):
                    cmd = step.get("cmd")
                    if not cmd or not validate_kubectl_syntax(cmd).get("valid"):
                        valid = False
                        break
                    steps.append(ValidationStep(cmd=cmd, matcher={}))
                if not valid:
                    continue
                qid = f"ai-gen-{uuid.uuid4()}"
                resp_cmd = steps[0].cmd if steps else ""
                questions.append(
                    Question(id=qid, prompt=prompt, response=resp_cmd, validation=steps)
                )
                logger.info(f"Generated AI question: {prompt}")
                break
        return questions
