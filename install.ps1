# install.ps1 - Windows installer for VITO (styled)
param()
function writec([string]$text,[string]$color="White"){ Write-Host $text -ForegroundColor $color }

writec "#########################################" Cyan
writec "#                                       #" Cyan
writec "#              V I T O - Installer      #" Cyan
writec "#                                       #" Cyan
writec "#########################################" Cyan
Start-Sleep -Seconds 1

# Pick python
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { writec "Python not found. Install Python 3.9+ and re-run." Red; exit 1 }

if (Test-Path "venv" -and Test-Path ".env") {
    writec "Existing installation found. Updating dependencies..." Yellow
    & .\venv\Scripts\Activate.ps1
    pip install --upgrade pip
    pip install -r requirements.txt
    python -m playwright install chromium
    writec "Starting VITO..." Green
    python main.py
    exit 0
}

writec "Creating virtual environment..." Blue
python -m venv venv
.\venv\Scripts\Activate.ps1

writec "Installing dependencies..." Blue
pip install --upgrade pip
pip install -r requirements.txt

writec "Installing Playwright Chromium..." Blue
python -m playwright install chromium

# Ask for token and ID with confirmation
while ($true) {
    $token = Read-Host "Enter your Discord Bot TOKEN"
    $botid = Read-Host "Enter your Discord Bot ID (numeric)"
    writec "`nYou entered:" Magenta
    writec ("DISCORD_TOKEN: {0}..." -f $token.Substring(0,[Math]::Min(6,$token.Length))) Magenta
    writec ("BOT_ID: {0}" -f $botid) Magenta
    $ok = Read-Host "Is this correct? (y/n)"
    if ($ok -match '^[Yy]') { break }
}

# Write .env
@"
DISCORD_TOKEN=$token
BOT_ID=$botid
"@ | Out-File -Encoding utf8 .env
writec ".env created and secured." Green

# Open Playwright headful browser for Gemini login
writec "Opening Chromium for Gemini login..." Cyan
python - <<'PY'
from playwright.sync_api import sync_playwright
import os
os.makedirs("playwright_data", exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://gemini.google.com/")
    print("Please log in to Gemini. When finished, type 'done' here.")
    try:
        input("Type 'done' once logged in: ")
    except:
        pass
    browser.close()
PY

writec "Starting VITO..." Green
python main.py
