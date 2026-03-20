#!/bin/bash
set -euo pipefail

# Only run in Claude Code remote environment
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

echo "Installing Python dependencies..."
pip install -r "$CLAUDE_PROJECT_DIR/requirements.txt" --quiet

# Set PYTHONPATH for module imports
echo 'export PYTHONPATH="$CLAUDE_PROJECT_DIR"' >> "$CLAUDE_ENV_FILE"

echo "SessionStart hook completed."
