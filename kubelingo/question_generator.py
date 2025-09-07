#!/usr/bin/env python3
"""
Kubernetes Question Generator Module

This module generates natural language questions about Kubernetes topics
with varying difficulty levels for training and assessment purposes.
"""

import random
import json
import os
from typing import Any, Dict, List, Optional
from enum import Enum
import kubelingo.llm_utils as llm_utils

class QuestionGenerator:
    def __init__(self, manifest_generator=None):
        # These will be removed or refactored as AI takes over
        self.question_templates = {}
        self.contexts = {}
        # placeholder for an external manifest generator interface
        self.manifest_generator = manifest_generator
    
    def generate_ai_question(self,
                             topic: Optional[str] = None,
                             question_type: Optional[str] = None,
                             exclude_question_texts: Optional[List[str]] = None) -> Dict[str, Any]:
        if topic is None:
            topic_prompt = "Suggest a single, concise Kubernetes topic (e.g., 'pods', 'deployments', 'services'). Respond with only the topic name."
            topic = llm_utils.ai_chat(topic_prompt, "").strip().lower()
            if not topic:
                topic = ""

        if question_type is None:
            type_prompt = "Suggest a single question type (e.g., 'true/false', 'vocabulary', 'multiple choice', 'imperative', 'declarative'). Respond with only the type name."
            question_type = llm_utils.ai_chat(type_prompt, "").strip().lower()
            if not question_type:
                question_type = ""

        """Generates a Kubernetes question using AI"""
        if question_type == "true/false":
            exclude_instruction = ""
            if exclude_question_texts:
                # Escape single quotes in the question texts for the prompt
                escaped_exclude_texts = [text.replace("'", "'\'" ) for text in exclude_question_texts]
                exclude_instruction = f"Ensure this question is *semantically* and *structurally* significantly different from these: {escaped_exclude_texts}. Do not repeat any of these questions or their core meaning."

            system_prompt = f"""You are an expert in Kubernetes. Your task is to generate a Kubernetes true/false question about {topic}.
The question should be clear, concise, and test practical Kubernetes knowledge.
{exclude_instruction}
Format your response as a JSON object with the following keys:
"question": "The generated true/false statement",
"answer": "true" or "false"
"""
        elif question_type == "vocabulary":
            system_prompt = f"""You are an expert in Kubernetes. Your task is to generate a Kubernetes vocabulary question about {topic}.
The question should ask for a single Kubernetes term given a concise definition.
Respond with only the JSON object using the following keys:
  "question": "Provide the Kubernetes term that matches the following definition: ...",
  "answer": "the-term"
"""
        elif question_type == "multiple choice":
            exclude_instruction = ""
            if exclude_question_texts:
                # Escape single quotes in the question texts for the prompt
                escaped_exclude_texts = [text.replace("'", "'\''" ) for text in exclude_question_texts]
                exclude_instruction = f"Generate a question that is semantically distinct and tests a different aspect of {topic}. Avoid any questions that are similar in meaning or rephrased versions of these: {escaped_exclude_texts}."

            system_prompt = f"""You are an expert in Kubernetes. Your task is to generate a Kubernetes multiple choice question about {topic}.
The question should be clear, concise, and test practical Kubernetes knowledge.
Provide 4 detailed answers: one correct answer and three deceptively wrong distractors.
{exclude_instruction}
Format your response as a JSON object with the following keys:
"question": "The generated multiple choice question text",
"options": ["Option A", "Option B", "Option C", "Option D"],
"answer": "The correct option (e.g., 'Option B')"
"""
        elif question_type in ("imperative", "command"):  # support 'imperative' alias
            exclude_instruction = ""
            if exclude_question_texts:
                # Escape single quotes in the question texts for the prompt
                escaped_exclude_texts = [text.replace("'", "'\''" ) for text in exclude_question_texts]
                exclude_instruction = f"Generate a question that is semantically distinct and tests a different aspect of {topic}. Avoid any questions that are similar in meaning or rephrased versions of these: {escaped_exclude_texts}."

            system_prompt = f"""
You are an expert in Kubernetes. Your task is to generate a Kubernetes command question about {topic}.
The question should be clear, concise, and test practical Kubernetes knowledge.
The command in the 'answer' field MUST be syntactically correct.
All variables used in the 'answer' command MUST be defined in the 'question' field.
{exclude_instruction}
Format your response as a JSON object with the following keys:
"question": "The natural language question, including any variable definitions (e.g., 'Given a deployment named 'my-app', how do you scale it to 3 replicas?')",
"answer": "The syntactically correct kubectl, helm, or linux command (e.g., 'kubectl scale deployment my-app --replicas=3')",
"explanation": "A brief explanation of the command"
"""
        elif question_type in ("declarative", "manifest"):  # support 'declarative' alias
            exclude_instruction = ""
            if exclude_question_texts:
                # Escape single quotes in the question texts for the prompt
                escaped_exclude_texts = [text.replace("'", "'\''" ) for text in exclude_question_texts]
                exclude_instruction = f"Generate a question that is semantically distinct and tests a different aspect of {topic}. Avoid any questions that are similar in meaning or rephrased versions of these: {escaped_exclude_texts}."

            system_prompt = f"""You are an expert in Kubernetes. Your task is to generate a Kubernetes manifest question about {topic}.
The question should be clear, concise, and test practical Kubernetes knowledge.
The manifest in the 'answer' field MUST be syntactically correct YAML.
All variables used in the 'answer' manifest MUST be defined in the 'question' field.
{exclude_instruction}
Format your response as a JSON object with the following keys:
"question": "The natural language question, including any variable definitions (e.g., 'Create a Pod named \'nginx-pod\' using the \'nginx\' image.')",
"answer": "The syntactically correct YAML manifest for the resource (e.g., 'apiVersion: v1\nkind: Pod\nmetadata:\n  name: nginx-pod\nspec:\n  containers:\n  - name: nginx\n    image: nginx')",
"explanation": "A brief explanation of the manifest"
"""
        
        else: # Default for general questions (e.g., short answer)
            system_prompt = f"""You are an expert in Kubernetes. Your task is to generate a Kubernetes question about {topic} in a {question_type} format.
The question should be clear, concise, and test practical Kubernetes knowledge.
Provide the question, expected resources (e.g., Pod, Deployment), success criteria, and hints.
Format your response as a JSON object with the following keys:
"question": "The generated question text",
"expected_resources": ["List", "of", "resources"],
"success_criteria": ["List", "of", "criteria"],
"hints": ["List", "of", "hints"]
"""

        user_prompt = f"Generate a {question_type} question about {topic}."

        try:
            
            
            response_text = llm_utils.ai_chat(system_prompt, user_prompt)
            
            question_data = json.loads(response_text)
            
            # Ensure CLI has a suggested_answer field for display
            if 'answer' in question_data and 'suggested_answer' not in question_data:
                question_data['suggested_answer'] = question_data['answer']

            # For multiple choice questions, ensure options are unique
            if question_type == "multiple choice" and "options" in question_data:
                original_options = question_data["options"]
                unique_options = list(dict.fromkeys(original_options)) # Preserves order while removing duplicates
                
                # Ensure the correct answer is still in the unique options.
                # If not, it means the AI generated a duplicate for the answer,
                # and we need to handle this gracefully, e.g., by re-adding it
                # or logging a warning. For now, we'll just ensure it's present.
                if question_data["answer"] not in unique_options:
                    unique_options.append(question_data["answer"])
                
                # If the number of unique options is less than 4, and we expect 4,
                # we might need to pad or regenerate. For now, just use unique.
                question_data["options"] = unique_options

            if question_type == "manifest":
                if self.manifest_generator:
                    manifest_prompt = question_data.get("question", "")
                    if manifest_prompt:
                        generated_yaml = self.manifest_generator.generate_with_gemini(manifest_prompt)
                        validation_result = self.manifest_generator.validate_yaml(generated_yaml)
                        if validation_result["valid"]:
                            question_data["answer"] = generated_yaml
                            
                        else:
                            print(f"WARNING: Generated manifest is invalid: {validation_result['error']}")
                            # Optionally, handle invalid manifest, e.g., by setting answer to error message
                            question_data["answer"] = f"ERROR: Invalid manifest generated. {validation_result['error']}"
                    else:
                        print("WARNING: No manifest prompt found in question data.")
                else:
                    print("WARNING: Manifest generator not initialized for manifest question type.")

            # Add ID and other metadata
            question_data["id"] = self._generate_question_id()
            question_data["topic"] = topic
            
            question_data["question_type"] = question_type

            return question_data
            return {
                "id": self._generate_question_id(),
                "topic": topic,
                "question_type": question_type,
                "question": f"Failed to generate AI question for {topic} ({question_type}). Error: {e}",
                "expected_resources": [],
                "success_criteria": [],
                "hints": []
            }
    
    def generate_question(
        self,
        topic: Optional[str] = None,
        question_type: Optional[str] = None,
        include_context: bool = True,
        exclude_question_texts: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generate a Kubernetes question with specified parameters."""
        return self.generate_ai_question(topic, question_type, exclude_question_texts)


    
    
    def _normalize_text(self, text: str) -> str:
        """Normalizes text for comparison (lowercase, remove punctuation)."""
        import re
        return re.sub(r'[^a-zA-Z0-9\s]', '', text).lower().strip()

    def _generate_question_id(self) -> str:
        """Generate unique question ID"""
        import hashlib
        import time
        return hashlib.md5(f"{time.time()}".encode()).hexdigest()[:8]
    
    def generate_question_set(self, count: int = 10, question_type: Optional[str] = None, subject_matter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Generate a set of questions with optional filters, ensuring diversity."""
        questions: List[Dict[str, Any]] = []
        generated_question_texts = set()
        retries = 0
        max_retries_per_question = 5 # Limit retries to prevent infinite loops
        max_consecutive_failures = 3 # If AI fails to generate unique question 3 times in a row for the same topic, stop.
        consecutive_failures = 0

        while len(questions) < count and retries < count * max_retries_per_question:
            # Pass normalized texts for exclusion
            normalized_excluded_texts = [self._normalize_text(text.split('|')[0]) for text in generated_question_texts]
            question = self.generate_question(topic=subject_matter, question_type=question_type, exclude_question_texts=normalized_excluded_texts)
            
            question_text = question.get("question")
            question_topic = question.get("topic", "")
            question_type_val = question.get("question_type", "")
            
            # Use normalized text for uniqueness check
            normalized_question_text = self._normalize_text(question_text)
            unique_question_id = f"{normalized_question_text}|{question_topic}|{question_type_val}"

            if question_text and unique_question_id not in generated_question_texts:
                questions.append(question)
                generated_question_texts.add(unique_question_id)
                retries = 0 # Reset retries for the next unique question
                consecutive_failures = 0 # Reset consecutive failures
            else:
                retries += 1
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    print(f"Warning: AI consistently failed to generate unique questions for topic '{subject_matter}'. Stopping question generation for this topic.")
                    break # Exit the while loop

        if len(questions) < count:
            print(f"Warning: Could only generate {len(questions)} unique questions out of {count} requested.")

        return questions
    
    def save_questions_to_file(self, questions: List[Dict[str, Any]], filename: str):
        """Save generated questions to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(questions, f, indent=2, ensure_ascii=False)
    

    

    

    

def main():
    """Demo usage of the question generator"""
    generator = QuestionGenerator()
    
    # Generate single questions
    print("=== Single Question Examples ===")
    
    # AI-driven question
    question1 = generator.generate_question()
    print(f"Question: {question1['question']}")
    print(f"Topic: {question1['topic']}")
    print(f"Type: {question1['question_type']}")
    print()
    question2 = generator.generate_question()
    print(f"Question: {question2['question']}")
    print(f"Topic: {question2['topic']}")
    print(f"Type: {question2['question_type']}")
    print()
    
    # Generate a question set
    print("=== Question Set Generation ===")
    question_set = generator.generate_question_set(count=2)
    
    for i, q in enumerate(question_set, 1):
        print(f"{i}. [{q['topic'].title()}] {q['question']}\n   Expected Resources: {q['expected_resources']}\n   Success Criteria: {q['success_criteria']}\n   Hints: {q['hints']}")
    
    # Save to file
    generator.save_questions_to_file(question_set, "sample_questions.json")
    print(f"\nSaved {len(question_set)} questions to sample_questions.json")

if __name__ == "__main__":
    main()