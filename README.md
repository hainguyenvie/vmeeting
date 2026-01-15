# Meetily Lite - Web Version

This is a simplified, lightweight version of the Meeting Minutes Web Application.

## 📦 Requirements

- **Python 3.10+** (Added to PATH)
- **Node.js 18+**
- **Git** (Optional, but recommended)
- **CUDA Toolkit** (Optional, for GPU acceleration)

## 🚀 Quick Start

1.  **Run `setup.bat`**
    - This will create Python virtual environments and install all dependencies.
    - It handles Backend, Whisper, and Frontend one by one.

2.  **Run `start.bat`**
    - This launches the Backend, Whisper Service, and Frontend.
    - Access the app at: `http://localhost:3000`

## 📁 Structure

- `backend/`: FastAPI backend (Logic, Database).
- `frontend/`: Next.js Frontend (UI).
- `whisper/`: Self-contained Transcription Service.
    - You may need to copy models to `whisper/models/` or let them auto-download.

## 🐍 Use Existing Python Environment (Advanced)

If you already have a Python environment (e.g., Conda `stt` or system Python) and want to use it instead of creating new venvs:

1.  **Skip `setup.bat`** (or only run step 3 for Frontend).
2.  **Install Dependencies** in your environment:
    ```bash
    pip install -r backend/requirements.txt
    pip install -r whisper/requirements.txt
    ```
3.  **Run Manually**:
    Instead of `start.bat`, open 3 terminals:
    
    *Terminal 1 (Backend):*
    ```bash
    cd backend
    python main.py
    ```

    *Terminal 2 (Whisper):*
    ```bash
    cd whisper
    python service.py
    ```

    *Terminal 3 (Frontend):*
    ```bash
    cd frontend
    npm run dev
    ```

## 🔧 Troubleshooting

- **Models not found**:
  - The app looks for models in `%APPDATA%\com.meetily.ai\models`.
  - OR in `whisper/models`.
  - Ensure you have internet access for the first run to download small models, or copy your existing models folder here.

- **Port Conflicts**:
  - Backend: 5167
  - Whisper: 8178
  - Frontend: 3000
