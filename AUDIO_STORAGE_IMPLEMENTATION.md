# ✅ Audio Storage Implementation Complete!

## 🎉 ĐÃ IMPLEMENT XONG

### Các Thay Đổi Đã Áp Dụng:

#### 1. **Database Updates** (`backend/app/database.py`)
✅ Thêm constant `AUDIO_STORAGE_DIR` cho thư mục lưu audio
✅ Tạo function `init_audio_storage()` để tạo thư mục tự động
✅ Update `init_database()` để:
   - Thêm column `audio_file_path` vào table `meetings` (cho DB mới)
   - Auto-migrate DB cũ bằng ALTER TABLE (nếu column chưa tồn tại)
   - Tự động tạo thư mục `backend/audio_recordings/`

#### 2. **WebSocket Routes** (`backend/app/websocket_routes.py`)
✅ Update function `process_full_meeting_and_broadcast()` để:
   - Save WAV file vào `backend/audio_recordings/{meeting_id}.wav`
   - Update database với `audio_file_path`
   - Log chi tiết quá trình save
   - Xử lý lỗi gracefully (nếu save audio fail, vẫn tiếp tục save transcripts)

---

## 📂 Cấu Trúc Directory

```
backend/
├── app/
│   ├── database.py          ← Updated
│   ├── websocket_routes.py  ← Updated
│   └── ...
├── audio_recordings/        ← NEW! Auto-created
│   ├── {meeting-id-1}.wav
│   ├── {meeting-id-2}.wav
│   └── ...
└── meeting_minutes.db       ← Updated schema
```

---

## 🧪 Cách Test

### Test 1: Recording Mới (Live)

1. **Start a new meeting** trên frontend
2. **Record audio** (nói vài câu)
3. **Stop recording**
4. **Kiểm tra terminal backend**, bạn sẽ thấy:
   ```
   🚀 Starting Full Pipeline for {meeting-id} (123456 bytes, raw=True)...
   ✅ Full Pipeline Success! Got 3 segments.
   💾 Saved audio file: {meeting-id}.wav (123456 bytes)
   ✅ Updated meeting {meeting-id} with audio_file_path
   💾 Saved 3 transcripts to DB.
   ```

5. **Kiểm tra folder**:
   ```powershell
   # Check nếu file audio đã được tạo
   ls d:\viettel\meeting-minutes\meeting-minutes\web-version\meetily-lite\backend\audio_recordings\
   ```

6. **Verify trong DB**:
   ```sql
   SELECT id, title, audio_file_path FROM meetings ORDER BY created_at DESC LIMIT 1;
   -- Kết quả phải có audio_file_path không null
   ```

### Test 2: Upload File Audio

1. **Upload một file MP3/WAV** vào meeting
2. **Kiểm tra terminal** - Output tương tự Test 1
3. **Verify file đã được save** trong `audio_recordings/`

### Test 3: Database Migration (Existing DB)

Nếu bạn đã có database cũ (không có column `audio_file_path`):

1. **Restart backend** lần đầu tiên
2. **Kiểm tra log**, phải thấy:
   ```
   📋 Adding audio_file_path column to meetings table...
   ✅ [DB] Database initialized at: ...
   ✅ [Audio] Storage directory ready: ...
   ```
3. **Verify column mới**:
   ```sql
   PRAGMA table_info(meetings);
   -- Phải thấy audio_file_path trong list columns
   ```

---

## 🔍 Debug / Troubleshooting

### Issue 1: "Failed to save audio file"

**Possible causes:**
- Thư mục `audio_recordings/` không tồn tại
- Không có quyền write

**Fix:**
```powershell
# Manual create directory
mkdir d:\viettel\meeting-minutes\meeting-minutes\web-version\meetily-lite\backend\audio_recordings

# Check permissions
icacls d:\viettel\meeting-minutes\meeting-minutes\web-version\meetily-lite\backend\audio_recordings
```

### Issue 2: "audio_file_path is NULL in database"

**Possible causes:**
- Backend restart chưa apply migration
- Meeting được tạo trước khi implement feature

**Fix:**
```powershell
# Restart backend để apply migration
# Stop (Ctrl+C) và start lại
cd d:\viettel\meeting-minutes\meeting-minutes\web-version\meetily-lite\backend
python .\main.py
```

### Issue 3: File audio không play được

**Possible causes:**
- WAV header bị corrupt
- is_raw_pcm flag sai

**Fix:**
- Check log để verify `create_wav_bytes()` được gọi
- Dùng VLC player (hỗ trợ nhiều format hơn) để test

---

## 📊 Database Schema (Updated)

### Meetings Table

```sql
CREATE TABLE meetings (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    duration REAL,
    summary TEXT,
    audio_file_path TEXT  -- NEW COLUMN!
);
```

**Example row:**
```
id: "3ddd76ed-2f27-4115-9479-04d92d92fb25"
title: "Test Meeting"
created_at: 1737870123
duration: 45.2
summary: NULL
audio_file_path: "D:\viettel\meeting-minutes\meeting-minutes\web-version\meetily-lite\backend\audio_recordings\3ddd76ed-2f27-4115-9479-04d92d92fb25.wav"
```

---

## 🎯 Next Steps (Optional)

### 1. Add Download Endpoint

Để frontend có thể download audio file:

```python
# backend/app/meetings.py

from fastapi.responses import FileResponse
import os

@router.get("/download-audio/{meeting_id}")
async def download_audio(meeting_id: str):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("SELECT audio_file_path FROM meetings WHERE id = ?", (meeting_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row or not row[0]:
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    audio_path = row[0]
    if not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail="Audio file missing")
    
    return FileResponse(
        audio_path,
        media_type="audio/wav",
        filename=f"meeting_{meeting_id}.wav"
    )
```

### 2. Add Frontend Download Button

```tsx
// frontend/src/components/MeetingDetails.tsx

const downloadAudio = async () => {
  const response = await fetch(`http://localhost:5167/download-audio/${meetingId}`);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `meeting_${meetingId}.wav`;
  a.click();
};

// In JSX:
<button onClick={downloadAudio}>
  <Download className="mr-2" />
  Download Audio
</button>
```

### 3. Add Audio Playback in UI

```tsx
// Display audio player in meeting details
{meeting.audio_file_path && (
  <audio controls className="w-full">
    <source 
      src={`http://localhost:5167/download-audio/${meeting.id}`} 
      type="audio/wav" 
    />
  </audio>
)}
```

---

## 🎉 Summary

**DONE:**
- ✅ Audio files are now saved to `backend/audio_recordings/`
- ✅ Database tracks file path in `meetings.audio_file_path`
- ✅ Auto-migration for existing databases
- ✅ Works for both live recording and file upload
- ✅ Graceful error handling

**Storage Format:**
- Format: WAV (16kHz, 16-bit, mono)
- Filename: `{meeting_id}.wav`
- Location: `backend/audio_recordings/`

**Test it:** Record một meeting mới và check folder `audio_recordings/`! 🎤

Bạn có muốn tôi implement thêm download endpoint và UI button không? 🚀
