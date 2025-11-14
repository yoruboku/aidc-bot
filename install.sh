#!/usr/bin/env bash
# install.sh — Interactive installer for AIDC-Bot (Zom)
# Works on Linux, macOS, Termux
set -euo pipefail

# Color helpers (works in most terminals)
GREEN="\033[1;32m"
YELLOW="\033[1;33m"
BLUE="\033[1;34m"
RED="\033[1;31m"
RESET="\033[0m"

banner() {
  echo -e "${BLUE}"
  echo "    _    _ ___  ____   ____      _ "
  echo "   / \\  / |_ _|/ ___| / ___| ___| |"
  echo "  / _ \\| || || |    | |  _ / _ \\ |"
  echo " / ___ \\ || || |___ | |_| |  __/ |"
  echo "/_/   \\_\\___| \\____(_)____|\\___|_|"
  echo -e "${RESET}"
  echo -e "${GREEN}AIDC-Bot (Zom) installer${RESET}"
  echo
}

prompt_nonempty() {
  local prompt="$1"
  local var
  while :; do
    read -rp "$prompt" var
    if [[ -n "${var// /}" ]]; then
      echo "$var"
      return 0
    fi
    echo -e "${YELLOW}Value cannot be empty. Try again.${RESET}"
  done
}

prompt_botid() {
  local botid
  while :; do
    read -rp "Enter your Discord Bot ID (numeric): " botid
    if [[ "$botid" =~ ^[0-9]+$ ]]; then
      echo "$botid"
      return 0
    fi
    echo -e "${YELLOW}Bot ID must be numeric. Try again.${RESET}"
  done
}

banner
echo -e "${BLUE}Step 1 — creating Python virtual environment${RESET}"
PY=python3
if ! command -v $PY &> /dev/null; then
  echo -e "${YELLOW}python3 not found — trying python${RESET}"
  PY=python
  if ! command -v $PY &> /dev/null; then
    echo -e "${RED}Python not found. Install Python 3.9+ and re-run.${RESET}"
    exit 1
  fi
fi

venv_dir="venv"
echo -e "${GREEN}Creating venv in ./${venv_dir}${RESET}"
$PY -m venv "$venv_dir"
# shellcheck disable=SC1091
source "$venv_dir/bin/activate"

echo -e "${BLUE}Upgrading pip and installing requirements...${RESET}"
pip install --upgrade pip
pip install -r requirements.txt

echo
echo -e "${BLUE}Step 2 — Ask credentials${RESET}"
DISCORD_TOKEN="$(prompt_nonempty 'Enter your DISCORD BOT TOKEN: ')"
BOT_ID="$(prompt_botid)"

cat > .env <<EOF
DISCORD_TOKEN="$DISCORD_TOKEN"
BOT_ID="$BOT_ID"
EOF

chmod 600 .env
echo -e "${GREEN}.env created and secured (${PWD}/.env)${RESET}"

echo
echo -e "${BLUE}Step 3 — Playwright browser install${RESET}"
python -m playwright install chromium

echo
echo -e "${GREEN}Installation complete!${RESET}"
echo -e "${BLUE}Run the bot:${RESET}"
echo -e "  source ${venv_dir}/bin/activate"
echo -e "  python zom_bot.py"
echo
echo -e "${YELLOW}Extras:${RESET}"
echo -e "  To update from the repo: ./update.sh"
echo -e "  To remove local session data: rm -rf playwright_data/"

