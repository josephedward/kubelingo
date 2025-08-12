import json
import logging
import os
import re
import uuid
import yaml
from typing import List, Optional, Set

from kubelingo.database import add_question
from kubelingo.integrations.llm import get_llm_client
from kubelingo.modules.ai_evaluator import AIEvaluator
from kubelingo.question import Question
from kubelingo.utils.config import YAML_QUIZ_DIR
from kubelingo.utils.ui import Fore, Style
from kubelingo.utils.validation import (
    validate_kubectl_syntax,
    validate_prompt_completeness,
    validate_yaml_structure,
)

logger = logging.getLogger(__name__)


class AIQuestionGenerator:
    """
    Generates questions about Kubernetes subjects using an AI model.
    Wraps AIEvaluator to generate and validate questions about specific
    Kubernetes subjects.
    """

    def __init__(self, llm_client, max_attempts_per_question: int = 5):
        self.evaluator = AIEvaluator(llm_client=llm_client)
        self.max_attempts = max_attempts_per_question
        self.llm_client = llm_client

    def _save_question_to_yaml(self, question: Question):
        """Appends a generated question to a YAML file, grouped by subject."""
        try:
            subject = question.subject or "general"
            category = question.category or "uncategorized"
            # Sanitize subject to create a valid filename
            filename_subject = subject.lower().replace(" ", "_").replace("/", "_").replace("(", "").replace(")", "")
            filename_subject = ''.join(c for c in filename_subject if c.isalnum() or c == '_')
            filepath = os.path.join(YAML_QUIZ_DIR, f"ai_generated_{filename_subject}.yaml")

            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            existing_questions = []
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    try:
                        docs = list(yaml.safe_load_all(f))
                        for doc in docs:
                            if isinstance(doc, list):
                                existing_questions.extend(doc)
                    except yaml.YAMLError:
                        pass  # Overwrite if malformed

            # Avoid duplicates by ID
            if any(q.get('id') == question.id for q in existing_questions):
                return

            q_dict = {
                "id": question.id,
                "prompt": question.prompt,
                "response": question.response,
                "category": category,
                "subject": subject,
                "type": question.type,
                "source": "ai_generated",
                "validator": question.validator,
            }
            existing_questions.append(q_dict)

            with open(filepath, 'w', encoding='utf-8') as f:
                yaml.dump(existing_questions, f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            logger.warning(f"Failed to save AI-generated question '{question.id}' to YAML: {e}")

    def generate_questions(
        self,
        subject: str,
        num_questions: int = 1,
        base_questions: List[Question] = None,
        category: str = "Command",
        exclude_terms: Optional[List[str]] = None,
    ) -> List[Question]:
        """
        Generate up to `num_questions` kubectl command questions about the given `subject`.
        Uses few-shot prompting with examples and validates syntax before returning.
        """
        if base_questions is None:
            base_questions = []

        # Build few-shot prompt
        prompt_lines = ["You are a Kubernetes instructor."]
        q_type = "command"
        response_description = "the kubectl command"

        if category == "Manifest":
            q_type = "yaml_author"
            prompt_lines.append("Your task is to create questions that require writing a full Kubernetes YAML manifest.")
            if base_questions:
                prompt_lines.append("Here are example questions and answers:")
                for ex in base_questions:
                    prompt_lines.append(f"- Prompt: {ex.prompt}")
                    prompt_lines.append(f"  Response: {ex.response}")
            response_description = "the full, correct YAML manifest"
        elif category == "Basic":
            q_type = "basic"
            prompt_lines.append("Your task is to create 'definition-to-term' questions about Kubernetes. Provide a definition and ask the user for the specific Kubernetes term.")
            prompt_lines.append("Here are some examples of the format:")
            prompt_lines.append("- Prompt: What Kubernetes object provides a way to expose an application running on a set of Pods as a network service?")
            prompt_lines.append("  Response: Service")
            prompt_lines.append("- Prompt: Which component on a Kubernetes node is responsible for maintaining running containers and managing their lifecycle?")
            prompt_lines.append("  Response: kubelet")
            if base_questions:
                prompt_lines.append("Here are more examples of existing questions to avoid duplicating:")
                for ex in base_questions:
                    prompt_lines.append(f"- Prompt: {ex.prompt}")
                    prompt_lines.append(f"  Response: {ex.response}")
            if exclude_terms:
                exclusion_list = ", ".join(f'"{term}"' for term in exclude_terms)
                prompt_lines.append(f"- **CRITICAL**: Do NOT use any of the following terms: {exclusion_list}.")
            response_description = "the correct, single-word or hyphenated-word Kubernetes term"
        else:  # Command
            q_type = "command"
            response_description = "the kubectl command"
            if base_questions:
                prompt_lines.append("Here are example questions and answers:")
                for ex in base_questions:
                    prompt_lines.append(f"- Prompt: {ex.prompt}")
                    prompt_lines.append(f"  Response: {ex.response}")


        prompt_lines.append(f"Create exactly {num_questions} new, distinct quiz questions about '{subject}'.")
        prompt_lines.append(f"Return ONLY a JSON array of objects with 'prompt' and 'response' keys. The 'response' should contain {response_description}.")
        ai_prompt = "\n".join(prompt_lines)
        logger.debug("AI few-shot prompt: %s", ai_prompt)

        source_file = "ai_generated"
        if base_questions:
            # If we have base questions, they all come from the same quiz.
            # Use their source file so new questions are associated with that quiz.
            source_file = getattr(base_questions[0], 'source_file', source_file)

        valid_questions: List[Question] = []
        if not self.llm_client:
            logger.error("LLM client not available, cannot generate questions.")
            return valid_questions

        # Attempt generation up to max_attempts
        for attempt in range(1, self.max_attempts + 1):
            print(f"{Fore.CYAN}AI generation attempt {attempt}/{self.max_attempts}...{Style.RESET_ALL}")
            raw = None
            try:
                if not self.llm_client:
                    logger.error("LLM client not available, skipping generation attempt.")
                    continue
                # Use the configured LLM client
                user_prompt = "Please generate questions based on the instructions."
                raw = self.llm_client.chat_completion(
                    messages=[
                        {"role": "system", "content": ai_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.7,
                    json_mode=True
                )
            except Exception as e:
                logger.error(f"LLM client failed on attempt {attempt}: {e}", exc_info=True)
                continue

            if not raw:
                logger.warning("LLM client returned no content on attempt %d.", attempt)
                continue

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

                if q_type == "command":
                    if not validate_kubectl_syntax(r).get("valid"):
                        continue
                    if not validate_prompt_completeness(r, p).get("valid"):
                        continue
                elif q_type == "yaml_author":
                    if not validate_yaml_structure(r).get("valid"):
                        logger.warning(f"Skipping AI-generated YAML question with invalid syntax: {p}")
                        continue

                validator_dict = {"type": "ai", "expected": r}
                if q_type == "yaml_author":
                    validator_dict = {"type": "yaml_subset", "expected": r}

                qid = f"ai-gen-{uuid.uuid4()}"
                # Create question object
                question = Question(
                    id=qid,
                    prompt=p,
                    response=r,
                    type=q_type,
                    validator=validator_dict,
                    category=category,
                    subject=subject,
                    source='ai_generated',
                    source_file=source_file,
                )
                
                # Persist the generated question to the database
                try:
                    add_question(
                        id=qid,
                        prompt=p,
                        source_file=source_file,
                        response=r,
                        category=category,
                        subject=subject,
                        source='ai_generated',
                        validator=validator_dict,
                    )
                    # Also save to YAML file upon successful DB insertion
                    self._save_question_to_yaml(question)
                    valid_questions.append(question)
                except Exception as e:
                    logger.warning(f"Failed to add AI-generated question '{qid}' to DB: {e}")
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
    
