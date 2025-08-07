import logging
import json
import uuid
from typing import List, Set

import openai
import re
from kubelingo.utils.ui import Fore, Style
from kubelingo.modules.ai_evaluator import AIEvaluator
from kubelingo.question import Question, ValidationStep
from kubelingo.utils.validation import validate_kubectl_syntax
from kubelingo.utils.validation import validate_prompt_completeness
from kubelingo.database import add_question

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
        Uses few-shot prompting with examples and validates syntax before returning.
        """
        # Build few-shot prompt
        prompt_lines = ["You are a Kubernetes instructor."]
        if base_questions:
            prompt_lines.append("Here are example questions and answers:")
            for ex in base_questions:
                prompt_lines.append(f"- Prompt: {ex.prompt}")
                prompt_lines.append(f"  Response: {ex.response}")
        prompt_lines.append(f"Create exactly {num_questions} new, distinct quiz questions about '{subject}'.")
        prompt_lines.append("Return ONLY a JSON array of objects with 'prompt' and 'response' keys.")
        ai_prompt = "\n".join(prompt_lines)
        logger.debug("AI few-shot prompt: %s", ai_prompt)

        source_file = "ai_generated"
        if base_questions:
            # If we have base questions, they all come from the same quiz.
            # Use their source file so new questions are associated with that quiz.
            source_file = getattr(base_questions[0], 'source_file', source_file)

        valid_questions: List[Question] = []
        # Attempt generation up to max_attempts
        for attempt in range(1, self.max_attempts + 1):
            print(f"{Fore.CYAN}AI generation attempt {attempt}/{self.max_attempts}...{Style.RESET_ALL}")
            raw = None
            # Try OpenAI client
            try:
                resp = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[{"role": "system", "content": ai_prompt}],
                    temperature=0.7,
                )
                raw = resp.choices[0].message.content
            except Exception as e:
                logger.debug("OpenAI client failed: %s", e)
            # Fallback to llm package
            if raw is None:
                try:
                    import llm as _llm_module
                    llm_model = _llm_module.get_model()
                    llm_resp = llm_model.prompt(ai_prompt)
                    raw = llm_resp.text() if callable(getattr(llm_resp, "text", None)) else getattr(llm_resp, "text", str(llm_resp))
                except Exception as e:
                    logger.error("LLM fallback failed: %s", e)
                    break
            # Parse JSON
            items = []
            try:
                items = json.loads(raw)
            except Exception:
                m = re.search(r"\[.*\]", raw, flags=re.S)
                if m:
                    try:
                        items = json.loads(m.group())
                    except Exception:
                        items = []
            valid_questions.clear()
            for obj in items or []:
                # Support common key names for question/answer
                p = obj.get("prompt") or obj.get("question") or obj.get("q")
                r = obj.get("response") or obj.get("answer") or obj.get("a")
                if not p or not r:
                    continue
                if not validate_kubectl_syntax(r).get("valid"):
                    continue
                if not validate_prompt_completeness(r, p).get("valid"):
                    continue
                qid = f"ai-gen-{uuid.uuid4()}"
                valid_questions.append(Question(
                    id=qid,
                    prompt=p,
                    category=subject,
                    response=r,
                    type="command",
                    validator={"type": "ai", "expected": r},
                ))
                add_question(
                    id=qid,
                    prompt=p,
                    source_file=source_file,
                    response=r,
                    category=subject,
                    validator={"type": "ai", "expected": r},
                    source="ai",
                )
            if len(valid_questions) >= num_questions:
                break
            print(f"{Fore.YELLOW}Only {len(valid_questions)}/{num_questions} valid AI question(s); retrying...{Style.RESET_ALL}")
        if len(valid_questions) < num_questions:
            print(f"{Fore.YELLOW}Warning: Could only generate {len(valid_questions)} AI question(s).{Style.RESET_ALL}")
        return valid_questions[:num_questions]
    
    def generate_question(self, base_question: dict) -> dict:
        """
        Generate a single AI-based question using the AIEvaluator.
        Delegates to the underlying AIEvaluator and returns a question dict.
        """
        try:
            return self.evaluator.generate_question(base_question)
        except Exception:
            return {}
    
