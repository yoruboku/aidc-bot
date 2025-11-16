Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "     OPENING PERSISTENT GEMINI CHROMIUM       " -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan

# Find Python
$pythonCandidates = @("python", "python3", "py")
$PYTHON_BIN = $null

foreach ($p in $pythonCandidates) {
    if (Get-Command $p -ErrorAction SilentlyContinue) {
        $PYTHON_BIN = $p
        break
    }
}

if (-not $PYTHON_BIN) {
    Write-Host "Python 3.9+ not found. Install Python and try again." -ForegroundColor Red
    exit
}

# Ensure folder
if (-not (Test-Path "playwright_data")) {
    New-Item -ItemType Directory -Path "playwright_data" | Out-Null
}

Write-Host "Launching Chromium using persistent session..." -ForegroundColor Green

$code = @"
from playwright.sync_api import sync_playwright
import os

os.makedirs("playwright_data", exist_ok=True)

with sync_playwright() as p:
    print("Opening persistent Chromium...")
    context = p.chromium.launch_persistent_context(
        user_data_dir="playwright_data",
        headless=False
    )
    page = context.new_page()
    page.goto("https://gemini.google.com/")
    print("Chromium opened. Close the window when done.")
    page.wait_for_timeout(999999999)
"@

# Run inline Python
& $PYTHON_BIN -c $code
