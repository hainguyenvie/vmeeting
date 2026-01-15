@echo off
setlocal
title Meetily Lite Launcher

echo ============================================================
echo   STARTING MEETILY LITE
echo ============================================================

:: 1. Start Backend (Background)
echo [1/3] Starting Backend (Port 5167)...
start "Meetily Backend" /min cmd /c "cd backend && call venv\Scripts\activate && python main.py"

:: 2. Start Whisper (Background)
echo [2/3] Starting Whisper Service (Port 8178)...
start "Meetily Whisper" /min cmd /c "cd whisper && call venv\Scripts\activate && python service.py"

:: 3. Start Frontend
echo [3/3] Starting Frontend (Port 3000)...
echo.
echo    The application will open in your browser shortly...
echo    Local:   http://localhost:3000
echo    Network: (Check your IP)
echo.

cd frontend
:: Check for pnpm
if exist "pnpm-lock.yaml" (
    call pnpm run dev
) else (
    call npm run dev
)

pause
