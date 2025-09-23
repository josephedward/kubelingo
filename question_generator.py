"""Top-level QuestionGenerator stub for tests.

This provides a lightweight, offline `QuestionGenerator` with a permissive
signature so tests can call `generate_question(topic=..., include_context=True)`
or `generate_question(kind=..., count=1)` without hitting external providers.
"""
from typing import Any, Dict, List, Optional, Union


class GenerationError(Exception):
    pass


class QuestionGenerator:
    def generate_question(
        self,
        topic: Optional[str] = None,
        kind: Optional[str] = None,
        count: int = 1,
        include_context: bool = False,
        difficulty: Optional[str] = None,
        **_: Any,
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        t = (topic or kind or 'pods').lower()
        base = {
            "id": "stub-123",
            "topic": t,
            "question": f"Create a resource for topic '{t}'.",
            "source": "https://kubernetes.io/",
        }
        if include_context:
            base["context_variables"] = {
                "pod_name": "test-pod",
                "image": "nginx:latest",
            }
        # For command-style questions, provide a suggested answer for nicer output
        base.setdefault("suggested_answer", "kubectl run test-pod --image=nginx:latest")
        return base if count == 1 else [base for _i in range(count)]


def generate_questions(kind: str, count: int = 1, difficulty: Optional[str] = None) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    qg = QuestionGenerator()
    return qg.generate_question(kind=kind, count=count, difficulty=difficulty)

