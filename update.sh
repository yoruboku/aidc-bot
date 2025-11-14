#!/bin/bash
set -e

echo "=== AIDC-Bot Updater ==="

if [ ! -d "venv" ]; then
    echo "No installation found. Run unified_install.sh first."
    exit 1
fi

source venv/bin/activate
echo "Updating dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium

echo "Updating repository..."
git pull

echo "Starting bot..."
python3 zom_bot.py
