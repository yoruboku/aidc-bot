Write-Host "update.ps1 — pulling updates"
if (Test-Path .git) {
    git pull --rebase
} else {
    Write-Host "Not a git repo. Skipping git update."
}

if (Test-Path venv) {
    & .\venv\Scripts\Activate.ps1
    pip install -r requirements.txt --upgrade
    python -m playwright install chromium
    Write-Host "Update complete."
} else {
    Write-Host "No venv found. Run install.ps1 first."
}
