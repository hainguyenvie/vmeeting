@echo off
setlocal
title Meetily Lite Setup

echo ============================================================
echo   MEETILY LITE - SETUP
echo ============================================================
echo.

:: 1. Backend Setup
echo [1/3] Setting up Backend...
cd backend
if not exist "venv" (
    echo Creating Python Venv...
    python -m venv venv
)
call venv\Scripts\activate
echo Installing Backend Requirements...
pip install -r requirements.txt
pip install uvicorn python-multipart
deactivate
cd ..
echo.

:: 2. Whisper Setup
echo [2/3] Setting up Whisper Service...
cd whisper
if not exist "venv" (
    echo Creating Whisper Venv...
    python -m venv venv
)
call venv\Scripts\activate
echo Installing Whisper Requirements (This may take a while)...
pip install -r requirements.txt
deactivate
cd ..
echo.

:: 3. Frontend Setup
echo [3/3] Setting up Frontend...
cd frontend
if exist "pnpm-lock.yaml" (
    echo Detected pnpm...
    call pnpm install
) else (
    echo Using npm...
    call npm install
)
cd ..

echo.
echo ============================================================
echo   SETUP COMPLETE! 
echo   Please Run 'start.bat' to launch the application.
echo ============================================================
pause
