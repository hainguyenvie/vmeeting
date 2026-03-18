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
    employee_code: str

class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    html_summary: Optional[str] = None
    employee_code: str

class Meeting(BaseModel):
    id: str
    title: str
    created_at: int
    duration: Optional[float] = None
    summary: Optional[str] = None
    html_summary: Optional[str] = None
    employee_code: Optional[str] = None

@router.get("/get-meetings", response_model=List[Meeting])
async def get_meetings(employee_code: str):
    """Get all meetings for an employee"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM meetings WHERE employee_code = ? ORDER BY created_at DESC", (employee_code,))
        rows = cursor.fetchall()
        conn.close()
        
        print(f"📋 Retrieved {len(rows)} meetings for employee: {employee_code}")
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"❌ Error in get_meetings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/get-meeting/{meeting_id}", response_model=Meeting)
async def get_meeting(meeting_id: str, employee_code: str):
    """Get single meeting (must belong to employee)"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM meetings WHERE id = ? AND employee_code = ?", (meeting_id, employee_code))
        row = cursor.fetchone()
        conn.close()
        
        if row is None:
            raise HTTPException(status_code=404, detail="Meeting not found or access denied")
        
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
            "INSERT INTO meetings (id, title, created_at, employee_code) VALUES (?, ?, ?, ?)",
            (meeting_id, meeting.title, created_at, meeting.employee_code)
        )
        conn.commit()
        conn.close()
        
        print(f"✅ Created meeting: {meeting_id} - {meeting.title} by {meeting.employee_code}")
        
        return Meeting(
            id=meeting_id,
            title=meeting.title,
            created_at=created_at,
            employee_code=meeting.employee_code
        )
    except Exception as e:
        print(f"❌ Error creating meeting: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/update-meeting/{meeting_id}", response_model=Meeting)
async def update_meeting(meeting_id: str, meeting: MeetingUpdate):
    """Update meeting (must belong to employee)"""
    try:
        conn = sqlite3.connect(get_db_path())
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Verify ownership
        cursor.execute("SELECT id FROM meetings WHERE id = ? AND employee_code = ?", (meeting_id, meeting.employee_code))
        if cursor.fetchone() is None:
            conn.close()
            raise HTTPException(status_code=403, detail="Meeting not found or access denied")
        
        updates = []
        params = []
        
        if meeting.title is not None:
            updates.append("title = ?")
            params.append(meeting.title)
            
        if meeting.html_summary is not None:
            updates.append("html_summary = ?")
            params.append(meeting.html_summary)
        
        if meeting.summary is not None:
            summary_val = str(meeting.summary).strip()
            
            # Theo yêu cầu 2: "nếu là lưu thẳng html thì chỉ cập nhật html thôi không cần cập nhật markdown đâu"
            if summary_val.startswith("<") and ">" in summary_val and not summary_val.startswith("{"):
                if meeting.html_summary is None:
                    updates.append("html_summary = ?")
                    params.append(summary_val)
            else:
                # Flow thông thường: Lưu json / markdown
                updates.append("summary = ?")
                params.append(summary_val)
                
                # Theo yêu cầu 1: auto convert từ markdown sang HTML lúc lưu
                if meeting.html_summary is None:
                    try:
                        import json
                        from datetime import datetime
                        from .summary import markdown_to_html
                        
                        summary_data = json.loads(summary_val)
                        if isinstance(summary_data, dict):
                            if "markdown" in summary_data:
                                cursor.execute("SELECT title, created_at FROM meetings WHERE id = ?", (meeting_id,))
                                row = cursor.fetchone()
                                metadata = {}
                                if row:
                                    metadata['meeting_title'] = row[0]
                                    metadata['date'] = datetime.fromtimestamp(row[1]).strftime('%d/%m/%Y')
                                    
                                html_content = markdown_to_html(summary_data["markdown"], metadata)
                                updates.append("html_summary = ?")
                                params.append(html_content)
                                
                            elif "html" in summary_data or "html_summary" in summary_data:
                                html_content = summary_data.get("html", summary_data.get("html_summary"))
                                updates.append("html_summary = ?")
                                params.append(html_content)
                    except Exception as e:
                        print(f"⚠️ Could not auto-sync HTML generation: {e}")
        
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
async def delete_meeting(meeting_id: str, employee_code: str):
    """Delete meeting and its transcripts (must belong to employee)"""
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()

        # Verify ownership
        cursor.execute("SELECT id FROM meetings WHERE id = ? AND employee_code = ?", (meeting_id, employee_code))
        if cursor.fetchone() is None:
            conn.close()
            raise HTTPException(status_code=403, detail="Meeting not found or access denied")
        
        # Delete transcripts first (foreign key)
        cursor.execute("DELETE FROM transcripts WHERE meeting_id = ?", (meeting_id,))
        
        # Delete meeting
        cursor.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
        
        conn.commit()
        conn.close()
        
        print(f"🗑️ Deleted meeting: {meeting_id} by {employee_code}")
        
        return {"status": "deleted", "id": meeting_id}
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error deleting meeting: {e}")
        raise HTTPException(status_code=500, detail=str(e))
