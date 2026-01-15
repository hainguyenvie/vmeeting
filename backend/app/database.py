import sqlite3
from pathlib import Path
import os

# Try desktop database first, fallback to local
# Assumes structure: d:/viettel/meeting-minutes/meeting-minutes/backend/meeting_minutes.db
DESKTOP_DB = Path("D:/viettel/meeting-minutes/meeting-minutes/backend/meeting_minutes.db")

# Local DB relative to web-version/backend/meeting_minutes.db
# __file__ is backend/app/database.py -> parent=app -> parent=backend
LOCAL_DB = Path(__file__).parent.parent / "meeting_minutes.db"

# Determine which database to use
if DESKTOP_DB.exists():
    DB_PATH = DESKTOP_DB
    print(f"✅ [DB] Using desktop database: {DB_PATH}")
else:
    DB_PATH = LOCAL_DB
    print(f"⚠️ [DB] Desktop DB not found, using local: {DB_PATH}")

def get_db_path():
    return str(DB_PATH)

def init_database():
    """Create database tables if they don't exist"""
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        
        # Check if meetings table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='meetings'")
        if not cursor.fetchone():
            print("creating meetings table...")
            cursor.execute("""
                CREATE TABLE meetings (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    duration REAL,
                    summary TEXT
                )
            """)
        
        # Check if transcripts table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transcripts'")
        if not cursor.fetchone():
            print("creating transcripts table...")
            cursor.execute("""
                CREATE TABLE transcripts (
                    id TEXT PRIMARY KEY,
                    meeting_id TEXT NOT NULL,
                    transcript TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    speaker TEXT,
                    audio_start_time REAL,
                    audio_end_time REAL,
                    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
                )
            """)
        
        conn.commit()
        conn.close()
        print(f"✅ Database initialized at: {DB_PATH}")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
