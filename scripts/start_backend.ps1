# Start FastAPI backend (development)
$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\..\backend"
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000 --reload
