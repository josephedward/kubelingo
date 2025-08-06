import random
import logging
import json
from typing import List, Dict, Any

try:
    import llm
except ImportError:
    llm = None

from kubelingo.utils.validation import validate_kubectl_syntax

logger = logging.getLogger(__name__)


class AIQuestionGenerator:
    """
    Uses an AI model to generate new questions based on existing ones.
    """

    def __init__(self):
        self.model = None
        if not llm:
            logger.warning("`llm` library not found. AI question generation is disabled.")
            return
        try:
            self.model = llm.get_model()
        except Exception as e:
            logger.error(f"Failed to initialize LLM for question generation: {e}")

    def _generate_variation_prompt(self, question: Dict[str, Any]) -> str:
        prompt = question.get('prompt', '')
        response = question.get('response', '')
        category = question.get('category', '')

        return (
            "You are an expert Kubernetes instructor creating quiz questions for a tool called 'kubelingo'.\n"
            "Based on the following example question, create one new, unique, but similar variation.\n"
            "The new question must be different but test a similar concept.\n"
            "For example, if the original question uses 'nginx', you could use 'httpd' or 'redis'. If it refers to a namespace 'dev', you could use 'prod'.\n"
            "Crucially, the 'response' (the correct command) must be a syntactically valid `kubectl` command.\n"
            "Do not just copy the example. Provide a fresh take on the same topic.\n\n"
            "Example Question:\n"
            f"- Prompt: \"{prompt}\"\n"
            f"- Response: \"{response}\"\n"
            f"- Category: \"{category}\"\n\n"
            "Your Output Format (strict JSON):\n"
            "{\n"
            "  \"prompt\": \"<new_question_prompt>\",\n"
            "  \"response\": \"<new_kubectl_command>\",\n"
            "  \"category\": \"<same_category>\"\n"
            "}"
        )

    def generate_questions(self, base_questions: List[Dict[str, Any]], num_to_generate: int) -> List[Dict[str, Any]]:
        if not self.model:
            logger.warning("LLM not available. Cannot generate new questions.")
            return []

        if not base_questions:
            logger.warning("No base questions provided to generate variations from.")
            return []

        generated_questions = []
        attempts = 0
        max_attempts = num_to_generate * 2 + 5  # Give some leeway for failed validations

        while len(generated_questions) < num_to_generate and attempts < max_attempts:
            attempts += 1
            source_question = random.choice(base_questions)

            prompt = self._generate_variation_prompt(source_question)

            try:
                response_text = self.model.prompt(
                    prompt,
                    system="You are a JSON-generating assistant."
                ).text()

                new_q_data = json.loads(response_text)

                new_prompt = new_q_data.get('prompt')
                new_response = new_q_data.get('response')

                if not new_prompt or not new_response:
                    logger.warning("Generated question missing prompt or response. Skipping.")
                    continue

                # Validate the generated kubectl command
                validation_result = validate_kubectl_syntax(new_response)
                if not validation_result['valid']:
                    logger.warning(f"Generated command '{new_response}' failed validation: {validation_result['errors']}. Retrying.")
                    continue

                # Assemble the new question
                new_question = {
                    'id': f"ai-gen::{random.randint(1000, 9999)}",
                    'prompt': new_prompt,
                    'response': new_response,
                    'category': new_q_data.get('category', source_question.get('category')),
                    'type': 'command',  # Generated questions are command-based
                    'validator': {'type': 'ai', 'expected': new_response}
                }

                generated_questions.append(new_question)
                logger.info(f"Successfully generated and validated a new question: {new_prompt}")

            except Exception as e:
                logger.error(f"Error during AI question generation or validation: {e}")

        if len(generated_questions) < num_to_generate:
            logger.warning(f"Failed to generate the requested number of questions. Got {len(generated_questions)} out of {num_to_generate}.")

        return generated_questions
