"""
Transcript Endpoints
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
from pathlib import Path

router = APIRouter()

# Database path (shared)
from .database import get_db_path

class Transcript(BaseModel):
    id: str
    meeting_id: str
    transcript: str
    timestamp: str
    speaker: Optional[str] = None
    audio_start_time: Optional[float] = None
    audio_end_time: Optional[float] = None

@router.get("/get-transcripts/{meeting_id}", response_model=List[Transcript])
async def get_transcripts(meeting_id: str):
    """Get all transcripts for a meeting"""
    try:
        conn = sqlite3.connect(get_db_path())
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM transcripts WHERE meeting_id = ? ORDER BY audio_start_time",
            (meeting_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class RenameSpeakerRequest(BaseModel):
    meeting_id: str
    old_name: str
    new_name: str

@router.post("/rename-speaker")
async def rename_speaker(request: RenameSpeakerRequest):
    """Rename a speaker across all transcripts for a meeting"""
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE transcripts SET speaker = ? WHERE meeting_id = ? AND speaker = ?",
            (request.new_name, request.meeting_id, request.old_name)
        )
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        return {"status": "success", "affected_rows": affected, "message": f"Renamed {request.old_name} to {request.new_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class MergeSpeakerRequest(BaseModel):
    meeting_id: str
    from_speaker: str
    to_speaker: str

@router.post("/merge-speakers")
async def merge_speakers(request: MergeSpeakerRequest):
    """Merge one speaker into another (effectively deleting the first speaker)"""
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE transcripts SET speaker = ? WHERE meeting_id = ? AND speaker = ?",
            (request.to_speaker, request.meeting_id, request.from_speaker)
        )
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        return {"status": "success", "affected_rows": affected, "message": f"Merged {request.from_speaker} into {request.to_speaker}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
