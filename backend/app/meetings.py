"""
Meeting CRUD Endpoints
Creates new database with proper schema if desktop DB not found
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
from pathlib import Path
import time

router = APIRouter()

from .database import DB_PATH, get_db_path, init_database

# Initialize on import
init_database()

class MeetingCreate(BaseModel):
    title: str

class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None

class Meeting(BaseModel):
    id: str
    title: str
    created_at: int
    duration: Optional[float] = None
    summary: Optional[str] = None

@router.get("/get-meetings", response_model=List[Meeting])
async def get_meetings():
    """Get all meetings"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM meetings ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        
        print(f"📋 Retrieved {len(rows)} meetings")
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"❌ Error in get_meetings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/get-meeting/{meeting_id}", response_model=Meeting)
async def get_meeting(meeting_id: str):
    """Get single meeting"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row is None:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create-meeting", response_model=Meeting)
async def create_meeting(meeting: MeetingCreate):
    """Create new meeting"""
    try:
        import uuid
        meeting_id = str(uuid.uuid4())
        created_at = int(time.time())
        
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO meetings (id, title, created_at) VALUES (?, ?, ?)",
            (meeting_id, meeting.title, created_at)
        )
        conn.commit()
        conn.close()
        
        print(f"✅ Created meeting: {meeting_id} - {meeting.title}")
        
        return Meeting(
            id=meeting_id,
            title=meeting.title,
            created_at=created_at
        )
    except Exception as e:
        print(f"❌ Error creating meeting: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/update-meeting/{meeting_id}", response_model=Meeting)
async def update_meeting(meeting_id: str, meeting: MeetingUpdate):
    """Update meeting"""
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if meeting.title is not None:
            updates.append("title = ?")
            params.append(meeting.title)
        
        if meeting.summary is not None:
            updates.append("summary = ?")
            params.append(meeting.summary)
        
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        params.append(meeting_id)
        cursor.execute(
            f"UPDATE meetings SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()
        
        # Fetch updated meeting
        cursor.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,))
        conn.row_factory = sqlite3.Row
        row = cursor.fetchone()
        conn.close()
        
        if row is None:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/delete-meeting/{meeting_id}")
async def delete_meeting(meeting_id: str):
    """Delete meeting and its transcripts"""
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        
        # Delete transcripts first (foreign key)
        cursor.execute("DELETE FROM transcripts WHERE meeting_id = ?", (meeting_id,))
        
        # Delete meeting
        cursor.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
        
        conn.commit()
        conn.close()
        
        print(f"🗑️ Deleted meeting: {meeting_id}")
        
        return {"status": "deleted", "id": meeting_id}
    except Exception as e:
        print(f"❌ Error deleting meeting: {e}")
        raise HTTPException(status_code=500, detail=str(e))
