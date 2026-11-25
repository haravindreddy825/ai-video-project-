# One-command local launcher for Windows 11
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

Write-Host "[1/3] Applying database migrations..." -ForegroundColor Cyan
Set-Location "$Root\backend"
.\.venv\Scripts\alembic.exe upgrade head

if (-not (Test-Path "$Root\frontend\.next")) {
    Write-Host "[2/3] Building Next.js production frontend..." -ForegroundColor Cyan
    Set-Location "$Root\frontend"
    npm run build
}

Write-Host "[3/3] Starting Backend (127.0.0.1:8000) & Frontend (127.0.0.1:3000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$Root\backend'; .\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$Root\frontend'; npm run start -- -p 3000 -H 127.0.0.1"

Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:3000"
