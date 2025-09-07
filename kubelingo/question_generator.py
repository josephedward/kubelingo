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
                             question_type: Optional[str] = None) -> Dict[str, Any]:
        if topic is None:
            topic_prompt = "Suggest a single, concise Kubernetes topic (e.g., 'pods', 'deployments', 'services'). Respond with only the topic name."
            topic = ai_chat(topic_prompt, "").strip().lower()
            if not topic:
                topic = "general Kubernetes" # Fallback

        if question_type is None:
            type_prompt = "Suggest a single question type from 'true/false', 'vocabulary', 'multiple choice', 'short answer'. Respond with only the type name."
            question_type = ai_chat(type_prompt, "").strip().lower()
            if not question_type:
                question_type = "short answer" # Fallback

        """Generates a Kubernetes question using AI"""
        if question_type == "true/false":
            system_prompt = f"""You are an expert in Kubernetes. Your task is to generate a Kubernetes true/false question about {topic}.
The question should be clear, concise, and test practical Kubernetes knowledge.
Format your response as a JSON object with the following keys:
"question": "The generated true/false statement",
"answer": "true" or "false"
"""
        elif question_type == "vocabulary":
            system_prompt = f"""You are an expert in Kubernetes. Your task is to generate a Kubernetes vocabulary question about {topic}.
The question should provide a definition and ask for the corresponding Kubernetes term.
Format your response as a JSON object with the following keys:
"question": "The definition of a Kubernetes term",
"answer": "The Kubernetes term being defined"
"""
        elif question_type == "multiple choice":
            system_prompt = f"""You are an expert in Kubernetes. Your task is to generate a Kubernetes multiple choice question about {topic}.
The question should be clear, concise, and test practical Kubernetes knowledge.
Provide 4 detailed answers: one correct answer and three deceptively wrong distractors.
Format your response as a JSON object with the following keys:
"question": "The generated multiple choice question text",
"options": ["Option A", "Option B", "Option C", "Option D"],
"answer": "The correct option (e.g., 'Option B')"
"""
        else: # Default for general questions (e.g., short answer, manifest generation)
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
            response_text = ai_chat(system_prompt, user_prompt)
            question_data = json.loads(response_text)

            # Add ID and other metadata
            question_data["id"] = self._generate_question_id()
            question_data["topic"] = topic
            
            question_data["question_type"] = question_type

            return question_data
        except Exception as e:
            print(f"Error generating AI question: {e}")
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
        include_context: bool = True
    ) -> Dict[str, Any]:
        """Generate a Kubernetes question with specified parameters."""
        return self.generate_ai_question(topic, question_type)


    
    
    def _generate_question_id(self) -> str:
        """Generate unique question ID"""
        import hashlib
        import time
        return hashlib.md5(f"{time.time()}".encode()).hexdigest()[:8]
    
    def generate_question_set(self, count: int = 10, **filters) -> List[Dict[str, Any]]:
        """Generate a set of questions with optional filters"""
        questions: List[Dict[str, Any]] = []
        for _ in range(count):
            question = self.generate_question(**filters)
            questions.append(question)
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