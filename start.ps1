# One-command start for Windows.
# Usage: .\start.ps1                 (rules mode)
#        .\start.ps1 -Mode ollama
param(
    [string]$Mode = $(if ($env:LLM_MODE) { $env:LLM_MODE } else { "rules" }),
    [int]$Port = 8000
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path "backend\.venv")) {
    Write-Host "Creating Python virtual environment..."
    python -m venv backend\.venv
}
& backend\.venv\Scripts\python.exe -m pip install -q -r backend\requirements.txt

if (-not (Test-Path "frontend\node_modules")) {
    Write-Host "Installing frontend packages..."
    Push-Location frontend; npm install; Pop-Location
}
Write-Host "Building the frontend..."
Push-Location frontend; npm run build; Pop-Location
if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }

$env:LLM_MODE = $Mode
Write-Host ""
Write-Host "Pukaar is starting on http://localhost:$Port (LLM_MODE=$Mode)"
Write-Host "Landing page:       http://localhost:$Port/"
Write-Host "Officer dashboard:  http://localhost:$Port/control"
Write-Host "Citizen chat:       http://localhost:$Port/chat"
Write-Host ""
Set-Location backend
& .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port $Port
