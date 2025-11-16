#!/usr/bin/env bash
set -euo pipefail

# Colors
CYAN="\033[1;36m"
GREEN="\033[1;32m"
RED="\033[1;31m"
RESET="\033[0m"

echo -e "${CYAN}"
echo "==============================================="
echo "      OPENING PERSISTENT GEMINI CHROMIUM"
echo "==============================================="
echo -e "${RESET}"

# Pick Python binary
PYTHON_BIN=""
for p in python3 python py python; do
  if command -v "$p" >/dev/null 2>&1; then
    PYTHON_BIN="$p"
    break
  fi
done

if [ -z "$PYTHON_BIN" ]; then
  echo -e "${RED}Python not found. Install Python 3.9+ and retry.${RESET}"
  exit 1
fi

mkdir -p playwright_data

echo -e "${GREEN}Launching Chromium using saved session...${RESET}"
$PYTHON_BIN - <<'PYCODE'
from playwright.sync_api import sync_playwright
import os

os.makedirs("playwright_data", exist_ok=True)

with sync_playwright() as p:
    print("Opening Chromium (persistent profile: playwright_data)...")
    context = p.chromium.launch_persistent_context(
        user_data_dir="playwright_data",
        headless=False
    )
    page = context.new_page()
    page.goto("https://gemini.google.com/")
    print("You may now adjust Gemini settings, system prompt, or test queries.")
    print("Close the window when done.")
    page.wait_for_timeout(999999999)  # keep alive
PYCODE
