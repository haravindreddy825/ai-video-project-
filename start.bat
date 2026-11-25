@echo off
setlocal
cd /d "%~dp0"

if not exist ".env" (
    copy ".env.example" ".env" >nul
)

echo [1/3] Running database migrations...
cd backend
.venv\Scripts\alembic.exe upgrade head
if errorlevel 1 (
    echo Database migration failed.
    pause
    exit /b 1
)
cd ..

if not exist "frontend\.next" (
    echo [2/3] Building Next.js production frontend...
    cd frontend
    call npm run build
    cd ..
)

echo [3/3] Starting OpenSource AI Video Studio...
start "AI Video Studio - Backend (8000)" cmd /k "cd /d "%~dp0backend" && .venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000"
start "AI Video Studio - Frontend (3000)" cmd /k "cd /d "%~dp0frontend" && npm run start -- -p 3000 -H 127.0.0.1"

timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:3000"
echo Studio launched at http://127.0.0.1:3000
