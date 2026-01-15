"""
Speaker Diarization Endpoints
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
import subprocess
import json
import tempfile
import os
from pathlib import Path

router = APIRouter()

# Path to diarization server script
DIARIZATION_SCRIPT = Path(__file__).parent.parent.parent.parent / "scripts" / "diarization_server.py"

@router.post("/process")
async def process_diarization(file: UploadFile = File(...)):
    """
    Process audio for speaker detection
    Calls diarization_server.py subprocess
    """
    try:
        # Save uploaded audio temporarily
        suffix = Path(file.filename).suffix if file.filename else ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        # Call diarization server subprocess
        # Similar to how Rust does it
        process = subprocess.Popen(
            ["python", str(DIARIZATION_SCRIPT)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Read audio file and send to stdin
        with open(temp_path, "rb") as audio_file:
            audio_data = audio_file.read()
            stdout, stderr = process.communicate(input=audio_data, timeout=30)

        # Cleanup
        os.unlink(temp_path)

        # Parse result
        if process.returncode == 0:
            try:
                result = json.loads(stdout.decode())
                return {
                    "speaker": result.get("speaker", "SPEAKER_00"),
                    "score": result.get("score", 0.0),
                    "is_new": result.get("is_new", False)
                }
            except json.JSONDecodeError as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to parse diarization result: {str(e)}"
                )
        else:
            error_msg = stderr.decode() if stderr else "Unknown error"
            raise HTTPException(
                status_code=500,
                detail=f"Diarization failed: {error_msg}"
            )

    except subprocess.TimeoutExpired:
        process.kill()
        raise HTTPException(status_code=504, detail="Diarization timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
