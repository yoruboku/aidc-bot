Write-Host "=== vito-Bot Updater ==="

if (-not (Test-Path "venv")) {
    Write-Host "No installation found. Run install.ps1 first."
    exit
}

& venv\Scripts\Activate.ps1
Write-Host "Updating dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium

Write-Host "Updating repository..."
git pull

Write-Host "Starting bot..."
python main.py
