import sqlite3
from pathlib import Path
import os

# Try desktop database first, fallback to local
# Assumes structure: d:/viettel/meeting-minutes/meeting-minutes/backend/meeting_minutes.db
DESKTOP_DB = Path("D:/viettel/meeting-minutes/meeting-minutes/backend/meeting_minutes.db")

# Local DB relative to web-version/backend/meeting_minutes.db
# __file__ is backend/app/database.py -> parent=app -> parent=backend
LOCAL_DB = Path(__file__).parent.parent / "meeting_minutes.db"

# Audio storage directory (parallel to backend folder)
AUDIO_STORAGE_DIR = Path(__file__).parent.parent / "audio_recordings"

# Determine which database to use
if DESKTOP_DB.exists():
    DB_PATH = DESKTOP_DB
    print(f"✅ [DB] Using desktop database: {DB_PATH}")
else:
    DB_PATH = LOCAL_DB
    print(f"⚠️ [DB] Desktop DB not found, using local: {DB_PATH}")

def get_db_path():
    return str(DB_PATH)

def init_audio_storage():
    """Create audio storage directory if not exists"""
    try:
        AUDIO_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        print(f"✅ [Audio] Storage directory ready: {AUDIO_STORAGE_DIR}")
    except Exception as e:
        print(f"❌ [Audio] Failed to create storage directory: {e}")

def init_database():
    """Create database tables if they don't exist"""
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        
        # Check if meetings table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='meetings'")
        if not cursor.fetchone():
            print("📋 Creating meetings table...")
            cursor.execute("""
                CREATE TABLE meetings (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    duration REAL,
                    summary TEXT,
                    audio_file_path TEXT,
                    employee_code TEXT
                )
            """)
        else:
            # Check if audio_file_path column exists, if not add it
            cursor.execute("PRAGMA table_info(meetings)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'audio_file_path' not in columns:
                print("📋 Adding audio_file_path column to meetings table...")
                cursor.execute("ALTER TABLE meetings ADD COLUMN audio_file_path TEXT")
            
            if 'html_summary' not in columns:
                print("📋 Adding html_summary column to meetings table...")
                cursor.execute("ALTER TABLE meetings ADD COLUMN html_summary TEXT")
            
            if 'employee_code' not in columns:
                print("📋 Adding employee_code column to meetings table...")
                cursor.execute("ALTER TABLE meetings ADD COLUMN employee_code TEXT")
        
        # Check if transcripts table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transcripts'")
        if not cursor.fetchone():
            print("📋 Creating transcripts table...")
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
        print(f"✅ [DB] Database initialized at: {DB_PATH}")
        
        # Initialize audio storage
        init_audio_storage()
        
    except Exception as e:
        print(f"❌ [DB] Database initialization failed: {e}")
