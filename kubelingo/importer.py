#!/usr/bin/env python3
"""
Utilities for importing and formatting questions into the canonical schema.
"""
import uuid

def format_question(
    topic: str,
    question: str,
    suggested_answer: str,
    source: str,
    qid: str = None
) -> dict:
    """
    Build a question dict matching the canonical schema:
      {
        "id": "a1b2c3d4",
        "topic": "pods",
        "question": "...",
        "source": "...",
        "suggested_answer": "...",
        "user_answer": "",
        "ai_feedback": ""
      }

    If qid is provided, use it, otherwise generate an 8-character hex id.
    Strips leading/trailing whitespace from suggested_answer.
    """
    qid_str = qid if qid else uuid.uuid4().hex[:8]
    return {
        "id": qid_str,
        "topic": topic,
        "question": question,
        "source": source,
        "suggested_answer": suggested_answer.strip(),
        "user_answer": "",
        "ai_feedback": "",
    }