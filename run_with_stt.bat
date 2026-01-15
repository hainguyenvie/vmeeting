@echo off
title Meetily Lite (Existing 'stt' Env)

echo ============================================================
echo   MEETILY LITE - RUNNING WITH 'stt' ENV
echo ============================================================

:: Check if conda is available
where conda >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: Conda not found in PATH.
    pause
    exit /b
)

:: 1. Start Backend
echo [1/3] Starting Backend...
start "Meetily Backend" /min cmd /c "conda activate stt && cd backend && python main.py"

:: 2. Start Whisper
echo [2/3] Starting Whisper Service...
start "Meetily Whisper" /min cmd /c "conda activate stt && cd whisper && python service.py"

:: 3. Start Frontend
echo [3/3] Starting Frontend...
cd frontend
if exist "pnpm-lock.yaml" (
    call pnpm run dev
) else (
    call npm run dev
)

pause
