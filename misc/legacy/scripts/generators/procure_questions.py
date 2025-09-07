#!/usr/bin/env python3
"""
procure_questions.py

Script to reliably procure new CKAD practice questions for each topic,
using Jsonnet templates, snippet scraping, or LLM fallback as needed.
Refer to shared_context.md at the repo root for design and flow guidelines.
"""
import sys
import os
import yaml

# Attempt Jsonnet-based generation first
try:
    from kubelingo.jsonnet_generator import generate_from_jsonnet
except ImportError:
    generate_from_jsonnet = None

# Fallback generator (scrape or LLM)
from kubelingo.question_generator import generate_more_questions

# List of topics to generate questions for (empty => all available JSONnet templates)
DEFAULT_TOPICS = []

def procure_question(topic):
    # 1) Jsonnet template
    if generate_from_jsonnet:
        q = generate_from_jsonnet(topic, ext_vars={})
        if q:
            return q
    # 2) Scrape or LLM fallback via existing question generator
    return generate_more_questions(topic)

def main(topics=None):
    questions = []
    if topics is None or not topics:
        topics = DEFAULT_TOPICS
    for topic in topics:
        print(f"Processing topic: {topic}")
        try:
            q = procure_question(topic)
        except Exception as e:
            print(f"Error generating for {topic}: {e}", file=sys.stderr)
            continue
        if q:
            questions.append(q)
    # Output as a single YAML document
    payload = {'questions': questions}
    print(yaml.safe_dump(payload, sort_keys=False))

if __name__ == '__main__':
    # Allow passing topics via command line
    topics = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_TOPICS
    main(topics)