import logging
import json
import uuid
from typing import List, Set

import openai
from kubelingo.modules.ai_evaluator import AIEvaluator
from kubelingo.question import Question, ValidationStep
from kubelingo.utils.validation import validate_kubectl_syntax
from kubelingo.utils.validation import validate_prompt_completeness

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
        Generate up to `num_questions` kubectl command questions about the given `subject`.
        Uses the OpenAI API to create a JSON list of question/response pairs, then
        validates syntax and prompt completeness.
        """
        questions: List[Question] = []
        # Build AI prompt
        ai_prompt = (
            f"You are a Kubernetes instructor.\n"
            f"Create exactly {num_questions} distinct quiz questions about '{subject}' in JSON format.\n"
            "Each question object must have two keys: 'prompt' and 'response'.\n"
            "- 'prompt': a clear instruction, e.g. 'Create a Service Account named \'foo-sa\''.\n"
            "- 'response': the exact kubectl command to solve it, e.g. 'kubectl create sa foo-sa'.\n"
            "Return only a JSON array of such objects, no extra text."
        )
        logger.debug("AI generation prompt: %s", ai_prompt)
        try:
            resp_obj = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": ai_prompt},
                ],
                temperature=0.7,
            )
            raw = resp_obj.choices[0].message.content
            logger.debug("AI raw response: %s", raw)
            items = json.loads(raw)
        except Exception as e:
            logger.error("AI question generation failed: %s", e)
            return questions
        # Validate and convert
        for obj in items:
            prompt_text = obj.get('prompt')
            resp_cmd = obj.get('response')
            if not prompt_text or not resp_cmd:
                continue
            # Syntax check
            syntax = validate_kubectl_syntax(resp_cmd)
            if not syntax.get('valid'):
                logger.debug("Dropping invalid command: %s", resp_cmd)
                continue
            # Prompt completeness
            completeness = validate_prompt_completeness(resp_cmd, prompt_text)
            if not completeness.get('valid'):
                logger.debug("Dropping incomplete prompt: %s", completeness.get('errors'))
                continue
            qid = f"ai-gen-{uuid.uuid4()}"
            questions.append(
                Question(
                    id=qid,
                    prompt=prompt_text,
                    category=subject,
                    response=resp_cmd,
                    type="command",
                    validator={"type": "ai", "expected": resp_cmd},
                )
            )
        if len(questions) < num_questions:
            logger.warning("Only generated %d/%d AI questions", len(questions), num_questions)
        return questions
        # As a last resort, if we have at least one valid question, duplicate to meet the count
        if questions and len(questions) < num_questions:
            needed = num_questions - len(questions)
            base = questions[0]
            for _ in range(needed):
                clone = Question(
                    id=f"ai-fallback-{uuid.uuid4()}",
                    prompt=base.prompt,
                    response=base.response,
                    validation=base.validation,
                )
                questions.append(clone)
        return questions
