#!/usr/bin/env bash
# update.sh — update repo & dependencies
set -euo pipefail

echo "Attempting to update from git..."
if [ -d .git ]; then
  git pull --rebase
else
  echo "Not a git repo. Skipping git update."
fi

# update venv packages if venv exists
if [ -d venv ]; then
  source venv/bin/activate
  echo "Upgrading packages..."
  pip install -r requirements.txt --upgrade
  python -m playwright install chromium
  echo "Update complete."
else
  echo "No venv found. Run install.sh first."
fi
