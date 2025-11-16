#!/usr/bin/env bash
set -euo pipefail

# =======================
#  VITO AI CORE INSTALLER
# =======================

GREEN="\033[1;32m"
YELLOW="\033[1;33m"
BLUE="\033[1;34m"
RED="\033[1;31m"
MAGENTA="\033[1;35m"
CYAN="\033[1;36m"
RESET="\033[0m"

banner() {
  echo -e "${MAGENTA}"
  echo "╔═══════════════════════════════════════════════╗"
  echo "║         V I T O   A I   C O R E              ║"
  echo "║        Discord  ×  Gemini  ×  Playwright     ║"
  echo "╚═══════════════════════════════════════════════╝"
  echo -e "${RESET}"
}

banner

echo -e "${CYAN}[*] Scanning environment...${RESET}"

# ---------- Detect Python ----------
PYTHON_BIN=""
for p in python3 python py; do
  if command -v "$p" >/dev/null 2>&1; then
    PYTHON_BIN="$p"
    break
  fi
done

if [ -z "${PYTHON_BIN}" ]; then
  echo -e "${RED}[!] Python 3.11+ not found. Install Python first.${RESET}"
  exit 1
fi

echo -e "${GREEN}[✓] Python detected:${RESET} ${PYTHON_BIN}"

# ---------- Detect menu backend ----------
MENU_TOOL="bash"
if command -v whiptail >/dev/null 2>&1; then
  MENU_TOOL="whiptail"
elif command -v dialog >/dev/null 2>&1; then
  MENU_TOOL="dialog"
fi

echo -e "${CYAN}[*] UI backend:${RESET} ${MENU_TOOL}"

# ---------- Helpers ----------

menu_main() {
  local choice="run"
  if [ "$MENU_TOOL" = "whiptail" ]; then
    choice=$(
      whiptail --title "VITO AI CORE" \
        --backtitle "VITO Launcher · Neon Mode" \
        --menu "Select an action:" 17 70 3 \
        "run"     "Run VITO (default)" \
        "install" "New install / reinstall" \
        "exit"    "Exit" 3>&1 1>&2 2>&3 || echo "exit"
    )
  elif [ "$MENU_TOOL" = "dialog" ]; then
    choice=$(
      dialog --stdout --title "VITO AI CORE" \
        --backtitle "VITO Launcher · Neon Mode" \
        --menu "Select an action:" 17 70 3 \
        "run"     "Run VITO (default)" \
        "install" "New install / reinstall" \
        "exit"    "Exit"
    ) || choice="exit"
  else
    echo
    echo -e "${CYAN}VITO Launcher:${RESET}"
    echo "  [1] Run VITO (default)"
    echo "  [2] New install / reinstall"
    echo "  [3] Exit"
    read -rp "Select [1-3] (Enter = 1): " ans
    case "$ans" in
      2) choice="install" ;;
      3) choice="exit" ;;
      *) choice="run" ;;
    esac
  fi
  echo "$choice"
}

menu_owner_mode() {
  local choice="default"
  if [ "$MENU_TOOL" = "whiptail" ]; then
    choice=$(
      whiptail --title "Owner Mode" \
        --backtitle "VITO AI CORE · Access Control" \
        --menu "Choose owner configuration:" 18 70 3 \
        "default" "Built-in priority owner 'yoruboku' only" \
        "custom"  "Add extra owner usernames" \
        "none"    "No owners (not recommended)" 3>&1 1>&2 2>&3 || echo "default"
    )
  elif [ "$MENU_TOOL" = "dialog" ]; then
    choice=$(
      dialog --stdout --title "Owner Mode" \
        --backtitle "VITO AI CORE · Access Control" \
        --menu "Choose owner configuration:" 18 70 3 \
        "default" "Built-in priority owner 'yoruboku' only" \
        "custom"  "Add extra owner usernames" \
        "none"    "No owners (not recommended)"
    ) || choice="default"
  else
    echo
    echo -e "${CYAN}Owner Mode:${RESET}"
    echo "  [1] Default (only 'yoruboku')"
    echo "  [2] Custom owners"
    echo "  [3] No owners"
    read -rp "Select [1-3] (Enter = 1): " ans
    case "$ans" in
      2) choice="custom" ;;
      3) choice="none" ;;
      *) choice="default" ;;
    esac
  fi
  echo "$choice"
}

set_exec_perms() {
  echo -e "${CYAN}[*] Enabling execute bit on helper scripts...${RESET}"
  for f in install.sh update.sh open_gemini.sh; do
    if [ -f "$f" ]; then
      chmod +x "$f"
      echo -e "   ${GREEN}[✓]${RESET} $f"
    fi
  done
}

run_bot() {
  echo -e "${CYAN}[*] Spinning up VITO core...${RESET}"
  # shellcheck disable=SC1091
  source venv/bin/activate
  $PYTHON_BIN main.py
}

do_install() {
  echo -e "${BLUE}▶ STEP 1: Virtual environment${RESET}"
  $PYTHON_BIN -m venv venv
  # shellcheck disable=SC1091
  source venv/bin/activate

  echo -e "${BLUE}▶ STEP 2: Python dependencies${RESET}"
  pip install --upgrade pip
  pip install -r requirements.txt

  echo -e "${BLUE}▶ STEP 3: Playwright + Chromium${RESET}"
  $PYTHON_BIN -m playwright install chromium

  # Credentials
  echo -e "${BLUE}▶ STEP 4: Discord credentials${RESET}"
  local DISCORD_TOKEN BOT_ID
  while true; do
    read -rp "Discord BOT TOKEN: " DISCORD_TOKEN
    read -rp "Discord BOT ID (numeric): " BOT_ID
    if ! [[ "$BOT_ID" =~ ^[0-9]+$ ]]; then
      echo -e "${RED}[!] BOT ID must be numeric.${RESET}"
      continue
    fi
    echo -e "${MAGENTA}You entered:${RESET}"
    echo "  TOKEN: ${DISCORD_TOKEN:0:8}..."
    echo "  BOT ID: $BOT_ID"
    read -rp "Is this correct? (y/n): " ok
    [[ "$ok" == [Yy]* ]] && break
  done

  # Owner mode
  echo -e "${BLUE}▶ STEP 5: Owner configuration${RESET}"
  local OWNER_MODE OWNERS=""
  OWNER_MODE=$(menu_owner_mode)
  if [ "$OWNER_MODE" = "custom" ]; then
    echo
    echo -e "${CYAN}Enter extra owner usernames (global @ names, case-insensitive).${RESET}"
    echo "Leave empty and press Enter to finish."
    while true; do
      read -rp "Owner username: " ow
      [ -z "$ow" ] && break
      if [ -z "$OWNERS" ]; then
        OWNERS="$ow"
      else
        OWNERS="$OWNERS,$ow"
      fi
    done
  elif [ "$OWNER_MODE" = "none" ]; then
    OWNERS=""
  fi

  echo -e "${MAGENTA}Final owner list:${RESET} ${OWNERS:-<none (only 'yoruboku' internal)>}"

  # .env
  echo -e "${BLUE}▶ STEP 6: Writing .env${RESET}"
  cat > .env <<EOF
DISCORD_TOKEN=$DISCORD_TOKEN
BOT_ID=$BOT_ID
OWNERS=$OWNERS
EOF
  chmod 600 .env
  echo -e "${GREEN}[✓] .env created${RESET}"

  # helper perms
  set_exec_perms

  # Gemini login
  echo -e "${BLUE}▶ STEP 7: Gemini login (browser)${RESET}"
  echo -e "${CYAN}[*] Launching Chromium with persistent profile...${RESET}"

  $PYTHON_BIN << 'PYCODE'
from playwright.sync_api import sync_playwright
import os
os.makedirs("playwright_data", exist_ok=True)

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context("playwright_data", headless=False)
    page = ctx.new_page()
    page.goto("https://gemini.google.com")
    print("\n────────────────────────────────────────────")
    print("  Log in to GEMINI in the opened browser.")
    print("  When finished, CLOSE the browser window.")
    print("────────────────────────────────────────────\n")
    ctx.wait_for_event("close")
PYCODE

  echo -e "${GREEN}[✓] Gemini login stored${RESET}"
  echo -e "${CYAN}[*] Launching VITO AI CORE...${RESET}"
  run_bot
}

# ---------- Main ----------

HAS_INSTALL=0
if [[ -d "venv" && -f ".env" ]]; then
  HAS_INSTALL=1
fi

if [ "$HAS_INSTALL" -eq 1 ]; then
  choice=$(menu_main)
  case "$choice" in
    run)
      run_bot
      ;;
    install)
      do_install
      ;;
    exit)
      echo -e "${YELLOW}Exiting VITO launcher. Goodbye.${RESET}"
      exit 0
      ;;
    *)
      run_bot
      ;;
  esac
else
  echo -e "${YELLOW}[!] No previous install detected. Running full setup...${RESET}"
  do_install
fi
