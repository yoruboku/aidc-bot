#!/usr/bin/env bash
set -euo pipefail

# -------- Colors --------
GREEN="\033[1;32m"; YELLOW="\033[1;33m"; BLUE="\033[1;34m"; RED="\033[1;31m"; MAGENTA="\033[1;35m"; CYAN="\033[1;36m"; RESET="\033[0m"

echo -e "${CYAN}"
echo "┌───────────────────────────────────────────────────┐"
echo "│                V I T O   I N S T A L L E R        │"
echo "└───────────────────────────────────────────────────┘"
echo -e "${RESET}"

# -------- Python Detection --------
PYTHON_BIN=""
for p in python3 python py; do
    if command -v $p &>/dev/null; then PYTHON_BIN=$p; break; fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo -e "${RED}Python 3.11+ not found. Install Python before continuing.${RESET}"
    exit 1
fi
echo -e "${GREEN}Using Python: $PYTHON_BIN${RESET}"

# -------- Quick-run if installed --------
if [[ -d "venv" && -f ".env" ]]; then
    echo -e "${YELLOW}Existing installation detected. Updating...${RESET}"
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    $PYTHON_BIN -m playwright install chromium
    [[ -f open_gemini.sh ]] && chmod +x open_gemini.sh
    echo -e "${GREEN}Starting bot...${RESET}"
    $PYTHON_BIN main.py
    exit 0
fi

# -------- Begin Fresh Install --------
echo -e "${BLUE}Creating virtual environment...${RESET}"
$PYTHON_BIN -m venv venv
source venv/bin/activate

echo -e "${BLUE}Installing Python dependencies...${RESET}"
pip install --upgrade pip
pip install -r requirements.txt

echo -e "${BLUE}Installing Chromium for Playwright...${RESET}"
$PYTHON_BIN -m playwright install chromium

# -------- Credentials Setup --------
while true; do
    DISCORD_TOKEN=""
    read -rp "Enter Discord BOT TOKEN: " DISCORD_TOKEN
    read -rp "Enter Discord BOT ID (numeric): " BOT_ID
    [[ "$BOT_ID" =~ ^[0-9]+$ ]] || { echo -e "${RED}Invalid Bot ID. Try again.${RESET}"; continue; }
    echo -e "\n${MAGENTA}You entered:${RESET}\nTOKEN: ${DISCORD_TOKEN:0:8}...   ID: $BOT_ID"
    read -rp "Is this correct? (y/n) " yn
    [[ $yn == [Yy]* ]] && break
done

# -------- Owner Setup --------
echo
echo -e "${CYAN}Owner Selection:${RESET}"
echo "1) Default (only 'yoruboku' has priority)"
echo "2) Custom Owners"
read -rp "> " choice

OWNERS=""
if [[ $choice == "2" ]]; then
    while true; do
        read -rp "Enter owner username (global, case-sensitive): " ow
        if [[ -z "$OWNERS" ]]; then OWNERS="$ow"; else OWNERS="$OWNERS,$ow"; fi
        read -rp "Add another? (y/n): " more
        [[ $more != [Yy]* ]] && break
    done
fi

# -------- Write .env --------
{
echo "DISCORD_TOKEN=$DISCORD_TOKEN"
echo "BOT_ID=$BOT_ID"
echo "OWNERS=$OWNERS"
} > .env
chmod 600 .env

# -------- Ensure helper perms --------
echo -e "${BLUE}Setting executable permissions...${RESET}"
for FILE in install.sh update.sh open_gemini.sh; do
    [[ -f "$FILE" ]] && chmod +x "$FILE" && echo " → $FILE enabled"
done

# -------- Gemini Login --------
echo -e "${CYAN}\nLaunching Gemini login window...${RESET}"

$PYTHON_BIN << 'EOF'
from playwright.sync_api import sync_playwright
import os
os.makedirs("playwright_data", exist_ok=True)

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context("playwright_data", headless=False)
    page = context.new_page()
    page.goto("https://gemini.google.com")
    print("\n────────────────────────────────────────────")
    print(" Log in to GEMINI in the opened browser.")
    print(" Close the browser window ONLY when login completes.")
    print("────────────────────────────────────────────\n")
    context.wait_for_event("close")
EOF

echo -e "${GREEN}Login saved. Starting VITO...${RESET}\n"
$PYTHON_BIN main.py
