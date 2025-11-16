Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Banner {
    Write-Host "╔═══════════════════════════════════════════════╗" -ForegroundColor Magenta
    Write-Host "║           V I T O   A I   C O R E            ║" -ForegroundColor Magenta
    Write-Host "║      Discord × Gemini × Playwright           ║" -ForegroundColor Magenta
    Write-Host "╚═══════════════════════════════════════════════╝" -ForegroundColor Magenta
}
Banner

# --- Python detection ---
$pyCmd = (Get-Command python, python3, py -ErrorAction SilentlyContinue | Select-Object -First 1)
if (-not $pyCmd) {
    Write-Host "[!] Python 3.11+ not found. Install Python first." -ForegroundColor Red
    exit 1
}
$PY = $pyCmd.Source
Write-Host "[✓] Python detected: $PY" -ForegroundColor Green

function Run-Bot {
    Write-Host "[*] Spinning up VITO core..." -ForegroundColor Cyan
    & venv\Scripts\Activate.ps1
    & $PY main.py
}

function Do-Install {
    Write-Host "▶ STEP 1: Virtual environment" -ForegroundColor Blue
    & $PY -m venv venv
    & venv\Scripts\Activate.ps1

    Write-Host "▶ STEP 2: Dependencies" -ForegroundColor Blue
    pip install --upgrade pip
    pip install -r requirements.txt
    & $PY -m playwright install chromium

    # Credentials
    Write-Host "▶ STEP 3: Discord credentials" -ForegroundColor Blue
    while ($true) {
        $token = Read-Host "Discord BOT TOKEN"
        $botId = Read-Host "Discord BOT ID (numeric)"
        if ($botId -notmatch '^\d+$') {
            Write-Host "[!] BOT ID must be numeric." -ForegroundColor Red
            continue
        }
        Write-Host ("TOKEN: {0}..." -f ($token.Substring(0, [Math]::Min(8, $token.Length)))) -ForegroundColor Magenta
        Write-Host ("BOT ID: {0}" -f $botId) -ForegroundColor Magenta
        $ok = Read-Host "Is this correct? (y/n)"
        if ($ok -match '^[Yy]') { break }
    }

    # Owner mode
    Write-Host "▶ STEP 4: Owner configuration" -ForegroundColor Blue
    Write-Host "  [1] Default (priority owner 'yoruboku' only)" -ForegroundColor Cyan
    Write-Host "  [2] Custom owners" -ForegroundColor Cyan
    Write-Host "  [3] No owners" -ForegroundColor Cyan
    $choice = Read-Host "Select [1-3] (Enter = 1)"
    if ($choice -notmatch '^[123]$') { $choice = "1" }

    $owners = ""
    if ($choice -eq "2") {
        while ($true) {
            $u = Read-Host "Owner username (empty to finish)"
            if ([string]::IsNullOrWhiteSpace($u)) { break }
            if ($owners -eq "") { $owners = $u } else { $owners += ",$u" }
        }
    }

    Write-Host ("Owners: {0}" -f ($(if ($owners) { $owners } else { "<none (yoruboku only)>" }))) -ForegroundColor Magenta

    # .env
    Write-Host "▶ STEP 5: Writing .env" -ForegroundColor Blue
    @"
DISCORD_TOKEN=$token
BOT_ID=$botId
OWNERS=$owners
"@ | Out-File -Encoding utf8 .env
    Write-Host "[✓] .env created" -ForegroundColor Green

    # Gemini login
    Write-Host "▶ STEP 6: Gemini login" -ForegroundColor Blue
    Write-Host "[*] Launching Chromium persistent context..." -ForegroundColor Cyan

    $code = @"
from playwright.sync_api import sync_playwright
import os
os.makedirs('playwright_data', exist_ok=True)
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context('playwright_data', headless=False)
    pg = ctx.new_page()
    pg.goto('https://gemini.google.com')
    print('\\n────────────────────────────────────────────')
    print('  Log in to GEMINI in the opened browser.')
    print('  When finished, close the browser window.')
    print('────────────────────────────────────────────\\n')
    ctx.wait_for_event('close')
"@
    & $PY -c $code

    Run-Bot
}

# --- Main menu logic ---

$hasInstall = (Test-Path "venv" -PathType Container) -and (Test-Path ".env")

if ($hasInstall) {
    Write-Host ""
    Write-Host "VITO Launcher" -ForegroundColor Cyan
    Write-Host "  [1] Run VITO (default)" -ForegroundColor Gray
    Write-Host "  [2] Reinstall / fresh setup" -ForegroundColor Gray
    Write-Host "  [3] Exit" -ForegroundColor Gray
    $sel = Read-Host "Select [1-3] (Enter = 1)"
    if ($sel -eq "2") {
        Do-Install
    } elseif ($sel -eq "3") {
        Write-Host "Exiting VITO launcher." -ForegroundColor Yellow
        exit 0
    } else {
        Run-Bot
    }
} else {
    Write-Host "[!] No existing install found. Running full install..." -ForegroundColor Yellow
    Do-Install
}
