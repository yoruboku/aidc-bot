Write-Host "Updating repo and dependencies..." -ForegroundColor Green

if (Test-Path .git) { git pull --rebase } else { Write-Host "Not a git repo." -ForegroundColor Yellow }

if (Test-Path venv) {
    & .\venv\Scripts\Activate.ps1
    pip install --upgrade pip
    pip install -r requirements.txt
    python -m playwright install chromium
    Write-Host "Update complete." -ForegroundColor Green
    python main.py
} else {
    Write-Host "No venv found. Run install.ps1 first." -ForegroundColor Yellow
    exit 1
}
