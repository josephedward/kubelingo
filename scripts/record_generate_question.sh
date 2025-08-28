#!/usr/bin/env bash
set -euo pipefail

# Script to record an Asciinema session of Kubelingo generating a new question.
# Usage: bash scripts/record_generate_question.sh [TOPIC_INDEX]

# Topic index to select when prompted; defaults to 1
TOPIC_INDEX=${1:-1}

# Directory and file for the Asciinema recording
CAST_DIR="recordings"
CAST_FILE="${CAST_DIR}/generate_question.cast"

# Check that Asciinema is installed
if ! command -v asciinema >/dev/null 2>&1; then
    echo "Error: 'asciinema' not found in PATH. Please install Asciinema to continue." >&2
    exit 1
fi

# Determine CLI command to run Kubelingo
if command -v kubelingo >/dev/null 2>&1; then
    CLI_CMD="kubelingo"
else
    CLI_CMD="python -m kubelingo.kubelingo"
fi

mkdir -p "${CAST_DIR}"

echo "Recording Kubelingo generating a question for topic index ${TOPIC_INDEX}..."

# Record session: select topic, generate question, then quit
asciinema rec "${CAST_FILE}" -c "printf '%s\n' '${TOPIC_INDEX}' 'g' 'q' | ${CLI_CMD}"

echo "Recording saved to ${CAST_FILE}"