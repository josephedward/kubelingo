#!/usr/bin/env bash
set -euo pipefail

# install_all.sh
# This script installs all Python dependencies and CLI tools required
# for the Kubernetes Question Generation System.

# Navigate to the script directory
cd "$(dirname "$0")"

PYTHON_CMD="${PYTHON:-python3}"

echo "==> Installing Python dependencies and tools via setup.py"
$PYTHON_CMD setup.py

echo
echo "Installation complete."
echo "Please edit the .env file in this directory to add your API keys and configuration as needed."
echo "If you installed any tools locally into ./bin, add that directory to your PATH:"
echo "  export PATH=\"$(pwd)/bin:$PATH\""
echo
echo "You can verify the setup by generating a sample question or manifest:" 
echo "  python question_generator.py" 
echo "  python k8s_manifest_generator.py --mode question --question-count 1"