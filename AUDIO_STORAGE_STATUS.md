# 🎙️ Tình Trạng Lưu Trữ Audio File

## ❌ HIỆN TRẠNG: AUDIO KHÔNG ĐƯỢC LƯU VÀO DISK

### Tóm Tắt
Sau khi phân tích code, tôi xác nhận rằng **hệ thống KHÔNG lưu raw audio file** vào disk. Audio chỉ tồn tại trong memory trong quá trình xử lý.

---

## 📊 Luồng Xử Lý Audio Hiện Tại

### 1. Recording (Live)
```
Frontend (Browser)
  ↓ Microphone Capture
  ↓ MediaRecorder API → PCM chunks
  ↓ WebSocket
Backend (websocket_routes.py)
  ↓ final_buffer = bytearray()  ← Chỉ trong RAM!
  ↓ final_buffer.extend(audio_chunk)
  ↓ Khi STOP
  ↓ process_full_meeting_and_broadcast(bytes(final_buffer), meeting_id)
Whisper Service
  ↓ Xử lý audio → transcripts
  ↓ Trả về: [{start, end, speaker, text}, ...]
Backend
  ↓ Lưu vào DB: transcripts table
  
❌ Raw audio bị DISCARD sau khi xử lý xong!
```

### 2. Upload File (Full Audio)
```
Frontend
  ↓ Upload MP3/WAV
  ↓ POST /ws/upload/{meeting_id}
Backend (websocket_routes.py)
  ↓ content = await file.read()  ← Chỉ trong RAM!
  ↓ process_full_meeting_and_broadcast(content, meeting_id, is_raw_pcm=False)
Whisper Service
  ↓ Xử lý audio → transcripts
Backend
  ↓ Lưu transcripts vào DB
  
❌ Uploaded audio bị DISCARD sau khi xử lý!
```

---

## 💾 Database Schema Hiện Tại

### Meetings Table
```sql
CREATE TABLE meetings (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    duration REAL,
    summary TEXT
    -- ❌ KHÔNG CÓ audio_file_path!
)
```

### Transcripts Table
```sql
CREATE TABLE transcripts (
    id TEXT PRIMARY KEY,
    meeting_id TEXT NOT NULL,
    transcript TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    speaker TEXT,
    audio_start_time REAL,
    audio_end_time REAL
    -- ❌ KHÔNG CÓ audio segment file!
)
```

---

## 🤔 TẠI SAO KHÔNG LƯU AUDIO?

### Lý do có thể:
1. **Design Decision**: Ưu tiên transcripts, không cần lưu raw audio
2. **Storage**: Audio files rất nặng (1 giờ ≈ 100-500MB tùy format)
3. **Privacy**: Không muốn lưu voice data của participants
4. **Simplicity**: Chỉ cần transcripts để tạo summary

### Hậu quả:
- ✅ **Pro**: Database nhẹ, fast, không lo storage
- ❌ **Con**: 
  - Không thể replay audio
  - Không thể re-transcribe với model mới
  - Không thể verify transcription accuracy
  - Mất dữ liệu nếu transcription sai

---

## 🛠️ GIẢI PHÁP: THÊM AUDIO STORAGE

### Option 1: Lưu Full Audio (Recommended)

#### A. Update Database Schema
```sql
-- Add audio_file_path to meetings table
ALTER TABLE meetings ADD COLUMN audio_file_path TEXT;
```

#### B. Create Audio Storage Directory
```python
# backend/app/database.py
import os
from pathlib import Path

AUDIO_STORAGE_DIR = Path(__file__).parent.parent / "audio_recordings"

def init_audio_storage():
    """Create audio storage directory if not exists"""
    AUDIO_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"✅ Audio storage initialized at: {AUDIO_STORAGE_DIR}")
```

#### C. Save Audio on Recording Stop
```python
# backend/app/websocket_routes.py

async def process_full_meeting_and_broadcast(audio_data: bytes, meeting_id: str, is_raw_pcm: bool = True):
    # ... existing code ...
    
    # NEW: Save audio file
    from .database import AUDIO_STORAGE_DIR
    import wave
    
    audio_filename = f"{meeting_id}.wav"
    audio_path = AUDIO_STORAGE_DIR / audio_filename
    
    try:
        if is_raw_pcm:
            # Convert PCM to WAV
            with wave.open(str(audio_path), 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(16000)
                wav_file.writeframes(audio_data)
        else:
            # Already WAV/MP3, save as-is
            with open(audio_path, 'wb') as f:
                f.write(audio_data)
        
        print(f"💾 Saved audio: {audio_path.name} ({len(audio_data)} bytes)")
        
        # Update database
        import sqlite3
        from .database import get_db_path
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE meetings SET audio_file_path = ? WHERE id = ?",
            (str(audio_path), meeting_id)
        )
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"❌ Failed to save audio: {e}")
    
    # ... continue with existing transcription logic ...
```

#### D. Add Download Endpoint
```python
# backend/app/meetings.py

from fastapi import APIRouter
from fastapi.responses import FileResponse
import os

@router.get("/download-audio/{meeting_id}")
async def download_audio(meeting_id: str):
    """Download original audio file for a meeting"""
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        cursor.execute("SELECT audio_file_path FROM meetings WHERE id = ?", (meeting_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row or not row[0]:
            raise HTTPException(status_code=404, detail="Audio file not found")
        
        audio_path = row[0]
        if not os.path.exists(audio_path):
            raise HTTPException(status_code=404, detail="Audio file missing on disk")
        
        return FileResponse(
            audio_path,
            media_type="audio/wav",
            filename=f"meeting_{meeting_id}.wav"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

#### E. Frontend: Add Download Button
```tsx
// frontend/src/components/MeetingDetails.tsx

const handleDownloadAudio = async () => {
  try {
    const response = await fetch(`http://localhost:5167/download-audio/${meetingId}`);
    if (!response.ok) {
      throw new Error('Audio file not available');
    }
    
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `meeting_${meetingId}.wav`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Failed to download audio:', error);
    alert('Không thể tải xuống audio file');
  }
};

// In JSX:
<button onClick={handleDownloadAudio}>
  📥 Download Audio
</button>
```

---

### Option 2: Lưu Segment Audio (Advanced)

Thay vì lưu full audio, lưu từng segment riêng:

```python
# Save individual segments
for item in transcripts:
    seg_start = item['start']
    seg_end = item['end']
    
    # Extract segment audio
    start_sample = int(seg_start * 16000)
    end_sample = int(seg_end * 16000)
    seg_audio = audio[start_sample:end_sample]
    
    # Save segment
    seg_filename = f"{meeting_id}_{item['speaker']}_{seg_start:.2f}-{seg_end:.2f}.wav"
    seg_path = AUDIO_STORAGE_DIR / seg_filename
    
    with wave.open(str(seg_path), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(seg_audio.tobytes())
```

**Pros:**
- Dễ replay từng câu nói
- Dễ re-transcribe từng segment
- Có thể tạo audio clips cho summary

**Cons:**
- Nhiều files hơn
- Phức tạp hơn

---

### Option 3: Cloud Storage (Production)

Nếu deploy production, nên dùng cloud:

```python
# AWS S3, Google Cloud Storage, etc.
import boto3

s3_client = boto3.client('s3')

def upload_to_s3(audio_data: bytes, meeting_id: str):
    bucket_name = "meetily-audio-recordings"
    object_key = f"meetings/{meeting_id}.wav"
    
    s3_client.put_object(
        Bucket=bucket_name,
        Key=object_key,
        Body=audio_data,
        ContentType='audio/wav'
    )
    
    # Store S3 URL in database
    s3_url = f"s3://{bucket_name}/{object_key}"
    return s3_url
```

---

## 📝 RECOMMENDATION

### Immediate Action (Local Development):
1. ✅ **Implement Option 1** - Lưu full audio vào local disk
2. ✅ Thêm download endpoint
3. ✅ Test với một meeting

### Long-term (Production):
1. ✅ Migrate to cloud storage (S3/GCS)
2. ✅ Add retention policy (auto-delete sau 30 ngày?)
3. ✅ Add audio playback trong UI
4. ✅ Add re-transcribe feature với model mới

---

## 🎯 TÓM TẮT

**Câu hỏi:** "Audio đã save ở đâu chưa?"

**Trả lời:** ❌ **CHƯA!** Audio chỉ tồn tại trong memory và bị discard ngay sau khi transcribe xong.

**Next Step:** Implement audio storage theo Option 1 ở trên để:
- Lưu raw audio vào `backend/audio_recordings/{meeting_id}.wav`
- Cập nhật database với `audio_file_path`
- Thêm download endpoint
- Thêm UI button để download

**Ước lượng công việc:** ~2 hours để implement đầy đủ

Bạn có muốn tôi implement feature này không? 🎯
