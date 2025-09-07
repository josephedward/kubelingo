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
from kubelingo.llm_utils import ai_chat

class DifficultyLevel(Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"

class KubernetesTopics(Enum):
    PODS = "pods"
    DEPLOYMENTS = "deployments"
    SERVICES = "services"
    CONFIGMAPS = "configmaps"
    SECRETS = "secrets"
    INGRESS = "ingress"
    VOLUMES = "volumes"
    RBAC = "rbac"
    NETWORKING = "networking"
    MONITORING = "monitoring"
    SECURITY = "security"
    TROUBLESHOOTING = "troubleshooting"

class QuestionGenerator:
    def __init__(self, manifest_generator=None):
        # These will be removed or refactored as AI takes over
        self.question_templates = {}
        self.contexts = {}
        # placeholder for an external manifest generator interface
        self.manifest_generator = manifest_generator
    
    def generate_ai_question(self, 
                             topic: str, 
                             difficulty: str, 
                             question_type: str) -> Dict[str, Any]:
        """Generates a Kubernetes question using AI"""
        system_prompt = f"""You are an expert in Kubernetes. Your task is to generate a {difficulty} level Kubernetes question about {topic} in a {question_type} format.
The question should be clear, concise, and test practical Kubernetes knowledge.
Provide the question, expected resources (e.g., Pod, Deployment), success criteria, and hints.
Format your response as a JSON object with the following keys:
"question": "The generated question text",
"expected_resources": ["List", "of", "resources"],
"success_criteria": ["List", "of", "criteria"],
"hints": ["List", "of", "hints"]
"""
        user_prompt = f"Generate a {difficulty} level {question_type} question about {topic}."
        
        try:
            response_text = ai_chat(system_prompt, user_prompt)
            question_data = json.loads(response_text)
            
            # Add ID and other metadata
            question_data["id"] = self._generate_question_id()
            question_data["topic"] = topic
            question_data["difficulty"] = difficulty
            question_data["question_type"] = question_type
            
            return question_data
        except Exception as e:
            print(f"Error generating AI question: {e}")
            return {
                "id": self._generate_question_id(),
                "topic": topic,
                "difficulty": difficulty,
                "question_type": question_type,
                "question": f"Failed to generate AI question for {topic} ({difficulty}, {question_type}). Error: {e}",
                "expected_resources": [],
                "success_criteria": [],
                "hints": []
            }

    def generate_question(self, 
                         topic: Optional[str] = None, 
                         difficulty: Optional[str] = None,
                         question_type: str = "tf", # Default to true/false for now
                         include_context: bool = True) -> Dict[str, Any]:
        """Generate a Kubernetes question with specified parameters"""
        
        # Select random topic and difficulty if not specified
        if topic is None:
            topic = random.choice(list(KubernetesTopics)).value
        if difficulty is None:
            difficulty = random.choice(list(DifficultyLevel)).value
            
        # Use AI to generate the question
        question = self.generate_ai_question(topic, difficulty, question_type)
        
        # The AI-generated question already includes context, resources, criteria, and hints
        # The original _generate_context_variables, _get_expected_resources, _generate_success_criteria, _generate_hints, _generate_scenario_context will be removed or refactored.
        
        return question
    
    def _generate_question_id(self) -> str:
        """Generate unique question ID"""
        import hashlib
        import time
        return hashlib.md5(f"{time.time()}".encode()).hexdigest()[:8]
    
    def generate_question_set(self, count: int = 10, **filters) -> List[Dict[str, Any]]:
        """Generate a set of questions with optional filters"""
        questions = []
        for _ in range(count):
            question = self.generate_question(**filters)
            questions.append(question)
        return questions
    
    def save_questions_to_file(self, questions: List[Dict[str, Any]], filename: str):
        """Save generated questions to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(questions, f, indent=2, ensure_ascii=False)
    # Static definitions for TF and vocab questions
    VOCAB_DEFINITIONS = {
        "pod": "the smallest deployable unit in Kubernetes",
        "deployment": "an abstraction for managing a set of identical Pods",
        "service": "an abstraction which defines a logical set of Pods and a policy to access them",
        "configmap": "a key-value store for configuration data",
        "secret": "an object to store sensitive information securely",
        "ingress": "a collection of rules that allow inbound connections to reach cluster services",
        "namespace": "a virtual cluster for logical partitioning",
        "volume": "a directory containing data accessible to containers in a Pod",
        "node": "a worker machine in Kubernetes",
        "statefulset": "a controller for stateful applications"
    }

    def generate_tf_questions(self, topic: str, count: int, correct_folder: str = None) -> List[Dict[str, Any]]:
        """Generate True/False questions based on static vocabulary definitions"""
        # Build all possible statements
        terms = list(self.VOCAB_DEFINITIONS.items())
        tf_items = []
        for idx, (term, definition) in enumerate(terms):
            tf_items.append((f"True or False: {term} is {definition}", "true"))
            wrong_def = terms[(idx + 1) % len(terms)][1]
            tf_items.append((f"True or False: {term} is {wrong_def}", "false"))
        # Exclude used questions
        used = set()
        if correct_folder:
            for root, _, files in os.walk(correct_folder):
                for file in files:
                    if file.endswith('.json'):
                        try:
                            data = json.load(open(os.path.join(root, file)))
                            used.add(data.get('question', ''))
                        except Exception:
                            pass
        available = [(q, a) for q, a in tf_items if q not in used]
        random.shuffle(available)
        selected = available[:count]
        return [{"id": self._generate_question_id(), "topic": topic, "type": "tf", "question": q, "answer": a} for q, a in selected]

    def generate_vocab_questions(self, count: int, correct_folder: str = None, topic: str = None) -> List[Dict[str, Any]]:
        """Generate vocabulary questions based on static definitions"""
        defs = dict(self.VOCAB_DEFINITIONS)
        if correct_folder:
            used = set()
            for root, _, files in os.walk(correct_folder):
                for file in files:
                    if file.endswith('.json'):
                        try:
                            data = json.load(open(os.path.join(root, file)))
                            used.add(data.get('answer', ''))
                        except Exception:
                            pass
            for term in used:
                defs.pop(term, None)
        items = list(defs.items())
        random.shuffle(items)
        selected = items[:count]
        return [{"id": self._generate_question_id(), "topic": term, "type": "vocab", "question": f"Which Kubernetes term matches the following definition: '{definition}'?", "answer": term} for term, definition in selected]

    def generate_mcq_questions(self, topic: str, count: int) -> List[Dict[str, Any]]:
        """Generate multiple-choice questions (stub implementation)"""
        return [self.generate_question(topic=topic) for _ in range(count)]

def main():
    """Demo usage of the question generator"""
    generator = QuestionGenerator()
    
    # Generate single questions
    print("=== Single Question Examples ===")
    
    # Beginner pod question
    question1 = generator.generate_question(topic="pods", difficulty="beginner", question_type="true/false")
    print(f"Beginner Pod Question: {question1['question']}")
    print(f"Success Criteria: {question1['success_criteria']}")
    print()
    
    # Advanced deployment question  
    question2 = generator.generate_question(topic="deployments", difficulty="advanced", question_type="multiple choice")
    print(f"Advanced Deployment Question: {question2['question']}")
    print(f"Hints: {question2['hints']}")
    print()
    
    # Generate a question set
    print("=== Question Set Generation ===")
    question_set = generator.generate_question_set(count=2, difficulty="intermediate", question_type="short answer")
    
    for i, q in enumerate(question_set, 1):
        print(f"{i}. [{q['topic'].title()}] {q['question']}\n   Expected Resources: {q['expected_resources']}\n   Success Criteria: {q['success_criteria']}\n   Hints: {q['hints']}")
    
    # Save to file
    generator.save_questions_to_file(question_set, "sample_questions.json")
    print(f"\nSaved {len(question_set)} questions to sample_questions.json")

if __name__ == "__main__":
    main()