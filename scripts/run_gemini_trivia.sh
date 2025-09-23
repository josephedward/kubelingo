#!/bin/bash

# Set the LLM provider to gemini
export KUBELINGO_LLM_PROVIDER="gemini"

# Run the kubelingo CLI with simulated user input
# Select "Quiz", then "Trivia", then "ingress"
(echo "Quiz"; echo "Trivia"; echo "ingress") | python3 cli.py
