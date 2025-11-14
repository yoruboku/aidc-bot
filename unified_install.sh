#!/bin/bash
set -e

# Colors
RED="\e[31m"
GREEN="\e[32m"
YELLOW="\e[33m"
BLUE="\e[34m"
MAGENTA="\e[35m"
CYAN="\e[36m"
RESET="\e[0m"

# ASCII Art Header
echo -e "${CYAN}"
echo "#########################################"
echo "#                                       #"
echo "#         VITO - Installer              #"
echo "#                                       #"
echo "#########################################"
echo -e "${RESET}"

sleep 1

# Check if already installed
if [ -d "venv" ] && [ -f ".env" ]; then
    echo -e "${YELLOW}Bot already installed. Updating dependencies...${RESET}"
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    playwright install chromium
    echo -e "${GREEN}Starting bot...${RESET}"
    python3 main.py
    exit 0
fi

# Step 1: Create virtual environment
echo -e "${BLUE}Creating virtual environment...${RESET}"
python3 -m venv venv
source venv/bin/activate

# Step 2: Upgrade pip and install requirements
echo -e "${BLUE}Installing Python dependencies...${RESET}"
pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium

# Step 3: Setup .env
echo -e "${MAGENTA}Setting up Discord credentials...${RESET}"
read -p "Enter your Discord Bot Token: " DISCORD_TOKEN
read -p "Enter your Discord Bot ID: " BOT_ID
cat > .env <<EOL
DISCORD_TOKEN=$DISCORD_TOKEN
BOT_ID=$BOT_ID
EOL
echo -e "${GREEN}.env created!${RESET}"

# Step 4: Launch Chromium for Gemini login
echo -e "${CYAN}Opening Chromium for Gemini login...${RESET}"
python3 - <<EOF
from playwright.sync_api import sync_playwright
import os
os.makedirs("playwright_data", exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(storage_state="playwright_data/state.json")
    page = context.new_page()
    page.goto("https://gemini.google.com/")
    print("Please log in to Gemini. After login, type 'done' and press Enter.")
    input("Type 'done' once logged in: ")
    browser.close()
EOF

# Step 5: Start bot
echo -e "${GREEN}Starting BOKU AIDC Bot...${RESET}"
python3 main.py
