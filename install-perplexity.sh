#!/usr/bin/env bash
set -euo pipefail

# Creates a Python virtualenv (venv) and installs requirements.txt
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

echo "Creating virtualenv in $VENV_DIR"
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r "$PROJECT_DIR/requirements.txt"

echo "Done. Activate the venv with: source $VENV_DIR/bin/activate"
