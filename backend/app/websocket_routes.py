"""
WebSocket Routes for Real-time Audio Streaming and Transcription
Handles audio chunks from frontend and broadcasts transcript updates
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, File, UploadFile
from typing import Dict, List
import json
import asyncio
import httpx
import os
from datetime import datetime
import wave
import io
import os
import sys

# Add NVIDIA libs to PATH for CTranslate2 on Windows
if os.name == 'nt':
    try:
        import nvidia.cublas.lib
        import nvidia.cudnn.lib
        # os.add_dll_directory only works on Python 3.8+ Windows
        if hasattr(os, 'add_dll_directory'):
            os.add_dll_directory(os.path.dirname(nvidia.cublas.lib.__file__))
            os.add_dll_directory(os.path.dirname(nvidia.cudnn.lib.__file__))
    except Exception:
        pass

def create_wav_bytes(pcm_data: bytes) -> bytes:
    """Wrap raw PCM data with WAV header"""
    with io.BytesIO() as wav_buffer:
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2) # 16-bit
            wav_file.setframerate(16000)
            wav_file.writeframes(pcm_data)
        return wav_buffer.getvalue()

router = APIRouter()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, meeting_id: str):
        await websocket.accept()
        if meeting_id not in self.active_connections:
            self.active_connections[meeting_id] = []
        self.active_connections[meeting_id].append(websocket)
        print(f"✅ WebSocket connected for meeting: {meeting_id}")
    
    def disconnect(self, websocket: WebSocket, meeting_id: str):
        if meeting_id in self.active_connections:
            self.active_connections[meeting_id].remove(websocket)
            if not self.active_connections[meeting_id]:
                del self.active_connections[meeting_id]
        print(f"🔌 WebSocket disconnected for meeting: {meeting_id}")
    
    async def broadcast(self, meeting_id: str, message: dict):
        """Broadcast message to all connections for this meeting"""
        if meeting_id in self.active_connections:
            dead_connections = []
            for connection in self.active_connections[meeting_id]:
                try:
                    await connection.send_json(message)
                except:
                    dead_connections.append(connection)
            
            # Clean up dead connections
            for connection in dead_connections:
                self.disconnect(connection, meeting_id)

manager = ConnectionManager()

# Whisper/STT server configuration
# Set WHISPER_SERVER_URL env var to point to your STT server
# Default: local whisper service (run whisper/service.py)
WHISPER_SERVER_URL = os.getenv("WHISPER_SERVER_URL", "http://localhost:8178")

async def process_audio_chunk(audio_data: bytes, meeting_id: str, diarize: bool = True):
    """
    Process audio chunk through Whisper.cpp
    Returns transcript text or None if error
    """
    try:
        # Call Whisper STT API (OpenAI-compatible endpoint)
        async with httpx.AsyncClient(timeout=60.0) as client:  # Increased to 60s
            files = {"file": ("audio.wav", audio_data, "audio/wav")}
            response = await client.post(
                f"{WHISPER_SERVER_URL}/v1/audio/transcriptions",
                files=files,
                data={
                    "model": "whisper-1",
                    "response_format": "verbose_json",  # Get segments with speaker info
                    "diarization": "false",  # Live mode - fast, no speaker labels
                    "temperature": 0.0
                }
            )
            
            print(f"🔍 Whisper response status: {response.status_code} (Diarize: {diarize})")
            print(f"🔍 Whisper response: {response.text[:200]}")  # First 200 chars
            
            if response.status_code == 200:
                result = response.json()
                print(f"🔍 Parsed JSON: {result}")
                
                transcript = result.get("text", "").strip()
                speaker = result.get("speaker", None)
                
                # Clean transcript if it contains speaker tag (to avoid duplication in UI)
                import re
                if speaker and transcript.startswith(f"[{speaker}]:"):
                    transcript = transcript.replace(f"[{speaker}]:", "").strip()
                elif speaker:
                     # General regex fallback
                     transcript = re.sub(r"^\[SPEAKER_\d+\]:\s*", "", transcript)

                print(f"🔍 Extracted transcript: '{transcript}' (Speaker: {speaker})")
                
                if transcript:
                    print(f"📝 Transcribed: {transcript[:50]}...")
                    return {
                        "transcript": transcript,
                        "timestamp": datetime.now().isoformat(),
                        "meeting_id": meeting_id,
                        "speaker": speaker
                    }
                else:
                    print("⚠️ Transcript is empty!")
                    return None
            else:
                print(f"❌ Whisper error: {response.status_code}")
                return None
                
    except Exception as e:
        print(f"❌ Transcription error: {e}")
        import traceback
        traceback.print_exc()
        return None


# Moonshine Voice model initialization
import numpy as np

moonshine_model_path = None
moonshine_model_arch = None

def get_moonshine_model():
    global moonshine_model_path, moonshine_model_arch
    if moonshine_model_path is None:
        try:
            from moonshine_voice.download import get_model_for_language
            print("🚀 Loading Vietnamese Moonshine model for streaming...")
            moonshine_model_path, moonshine_model_arch = get_model_for_language("vi")
        except Exception as e:
            print(f"❌ Failed to load Moonshine model: {e}")
            import traceback
            traceback.print_exc()
    return moonshine_model_path, moonshine_model_arch

@router.websocket("/ws/audio/{meeting_id}")
async def websocket_audio_endpoint(websocket: WebSocket, meeting_id: str):
    """
    WebSocket endpoint with Real-Time Streaming (Moonshine C++ Engine).
    """
    await manager.connect(websocket, meeting_id)
    
    # Configuration
    SAMPLE_RATE = 16000
    
    # Buffers & State
    final_buffer = bytearray()      # Full meeting audio (for DB save on stop)
    
    try:
        from moonshine_voice.transcriber import Transcriber, TranscriptEventListener, TranscriptLine
        
        model_path, model_arch = get_moonshine_model()
        if not model_path:
            raise ValueError("Moonshine model not loaded")
            
        transcriber = Transcriber(
            model_path=model_path,
            model_arch=model_arch,
            update_interval=1.0, # Wait longer (1s) before pushing text to allow AI to gain enough context for accurate translation
            options={
                "max_tokens_per_second": "13.0",    # Hard limit to avoid hallucination loops
                "identify_speakers": "false",
                "vad_threshold": "0.1",             # Extremely sensitive: capture even soft speech to avoid truncating words
                "vad_max_segment_duration": "30.0", # Allow very long sentences (up to 30s) to gather context
            }
        )
        
        loop = asyncio.get_running_loop()
        last_text = ""
        
        class LiveTranscriptListener(TranscriptEventListener):
            def broadcast_line(self, line: TranscriptLine, is_completed: bool):
                text = line.text.strip()
                nonlocal last_text
                
                # Filter out pure noise/empty lines
                if len(text) < 2 and not text.isdigit(): return
                
                # Apply Regex to collapse infinite repetition (e.g., "Hẹn gặp lại Hẹn gặp lại")
                import re
                text = re.sub(r'(.{6,}?)(?:\s*\1){2,}', r'\1', text)
                
                # Comprehensive Hallucination Filter 
                t_lower = text.lower()
                blacklist = ["ừ", "à", "ậm", "ờ", "um", "uh", "ah", "oh", "a", "o", "hử", "ử", "hử hử", "ử ử"]
                hallu_keywords = [
                    "ghiền mì", "youtube", "subscribe", "la la school",
                    "đăng ký kênh", "để không bỏ lỡ", "những video hấp dẫn",
                    "bạn đã xem video", "cảm ơn các bạn", "người dịch:", 
                    "subtitles by", "amara.org", "viết phụ đề bởi", "like và share",
                    "hẹn gặp lại", "hẹn gặp lạ"
                ]
                
                if t_lower in blacklist: return
                if any(hk in t_lower for hk in hallu_keywords): return
                if len(set(t_lower)) == 1 and len(t_lower) > 3: return
                
                # Check if it didn't change (to avoid spamming websocket)
                if text == last_text and not is_completed:
                    return
                last_text = text
                
                # Prepare speaker name
                speaker_name = f'SPEAKER_{line.speaker_index:02d}' if line.has_speaker_id else 'Unknown'

                # Thread-safe broadcast
                asyncio.run_coroutine_threadsafe(
                    manager.broadcast(meeting_id, {
                        'type': 'live_transcript',
                        'transcript': text,
                        'speaker': speaker_name,
                        'timestamp': datetime.now().isoformat(),
                        'is_completed': is_completed
                    }),
                    loop
                )

            def on_line_text_changed(self, event):
                self.broadcast_line(event.line, False)

            def on_line_completed(self, event):
                self.broadcast_line(event.line, True)
                nonlocal last_text
                last_text = ""

        # Add listener and start Transcriber background thread
        transcriber.add_listener(LiveTranscriptListener())
        transcriber.start()

        try:
            while True:
                data = await websocket.receive()
                
                if 'text' in data:
                     message = json.loads(data['text'])
                     msg_type = message.get('type')
                     print(f"📩 Received TEXT message: {msg_type}")
                     
                     if msg_type == 'stop':
                         # Final flush (FULL PIPELINE)
                         if len(final_buffer) > 0:
                             await manager.broadcast(meeting_id, {'type': 'status', 'status': 'processing'})
                             asyncio.create_task(process_full_meeting_and_broadcast(bytes(final_buffer), meeting_id))
                         
                         await manager.broadcast(meeting_id, {'type': 'status', 'status': 'stopped'})
                         break

                elif 'bytes' in data:
                    audio_chunk = data['bytes']
                    
                    # 1. Feed final buffer
                    final_buffer.extend(audio_chunk)
                    
                    # 2. Feed stream to Transcriber C++ Engine
                    if len(audio_chunk) > 0:
                        # Convert Int16 PCM to Float32 [-1.0, 1.0] for streaming ASR
                        pcm_array = np.frombuffer(audio_chunk, dtype=np.int16)
                        float_array = pcm_array.astype(np.float32) / 32768.0
                        
                        # Apply static gain instead of variable AGC to avoid gain pumping and distortion
                        float_array = float_array * 4.0
                        float_array = np.clip(float_array, -1.0, 1.0)
                            
                        transcriber.add_audio(float_array, SAMPLE_RATE)

        except WebSocketDisconnect:
            print(f"🔌 WebSocket disconnected for meeting: {meeting_id}")
        except Exception as e:
            print(f"❌ WebSocket loop error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print(f"🛑 Stopping Live Transcriber for {meeting_id}")
            transcriber.stop()
            manager.disconnect(websocket, meeting_id)
            print(f"🏁 WebSocket loop exited. Final Buffer Size: {len(final_buffer)} bytes")

    except Exception as e:
        print(f"❌ WebSocket Transcriber init error: {e}")
        import traceback
        traceback.print_exc()
        manager.disconnect(websocket, meeting_id)

async def process_final_and_broadcast(audio_data: bytes, meeting_id: str):
    """
    Process large chunk for permanent record.
    """
    # Diarize=True for accuracy
    result = await process_audio_chunk(audio_data, meeting_id, diarize=True)
    if result and result.get('text', '').strip():
        await manager.broadcast(meeting_id, {
            'type': 'transcript',        # STANDARD TYPE (Persisted)
            'is_final': True,
            **result
        })

async def process_full_meeting_and_broadcast(audio_data: bytes, meeting_id: str, is_raw_pcm: bool = True):
    """
    Call the full pipeline endpoint on stop or upload.
    """
    try:
        print(f"🚀 Starting Full Pipeline for {meeting_id} ({len(audio_data)} bytes, raw={is_raw_pcm})...")
        
        if is_raw_pcm:
            wav_data = create_wav_bytes(audio_data)
            filename = "audio.wav"
        else:
            wav_data = audio_data
            filename = "upload.wav" # Librosa/ffmpeg should detect format regardless of extension

        async with httpx.AsyncClient(timeout=300.0) as client: # 5 mins timeout
            files = {"file": (filename, wav_data, "audio/wav")}
            
            # Use standard OpenAI-compatible endpoint (tested and working)
            response = await client.post(
                f"{WHISPER_SERVER_URL}/v1/audio/transcriptions",
                files=files,
                data={
                    "model": "whisper-1",
                    "response_format": "verbose_json",
                    "diarization": "true",  # Enable speaker labels for full meeting
                    "temperature": 0.0
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                # Response format: {"text": "...", "segments": [...], "language": "vi"}
                # Convert to expected format
                segments = data.get("segments", [])
                transcripts = []
                for seg in segments:
                    transcripts.append({
                        "text": seg.get("text", ""),
                        "speaker": seg.get("speaker", "SPEAKER_00"),
                        "start": seg.get("start", 0.0),
                        "end": seg.get("end", 0.0)
                    })
                print(f"✅ Full Pipeline Success! Got {len(transcripts)} segments.")
                
                # Calculate meeting duration
                # Option 1: Get from API response (if available)
                duration = data.get("duration")
                # Option 2: Calculate from segments (fallback)
                if duration is None and transcripts:
                    duration = max(seg["end"] for seg in transcripts)
                
                print(f"📏 Meeting duration: {duration:.2f}s" if duration else "⚠️ Duration not available")
                
                # DB Connection
                import sqlite3
                import uuid
                from pathlib import Path
                from .database import get_db_path
                
                try:
                    conn = sqlite3.connect(get_db_path())
                    cursor = conn.cursor()
                    
                    # Create audio storage directory path
                    # Use backend/audio_recordings/ directory
                    backend_dir = Path(__file__).parent.parent
                    audio_storage_dir = backend_dir / "audio_recordings"
                    audio_storage_dir.mkdir(parents=True, exist_ok=True)
                    
                    # NEW: Save audio file to disk
                    audio_filename = f"{meeting_id}.wav"
                    audio_path = audio_storage_dir / audio_filename
                    
                    try:
                        # Save WAV file
                        with open(audio_path, 'wb') as f:
                            f.write(wav_data)
                        print(f"💾 Saved audio file: {audio_path.name} ({len(wav_data)} bytes)")
                        
                        # Update meeting with audio_file_path AND duration
                        cursor.execute(
                            "UPDATE meetings SET audio_file_path = ?, duration = ? WHERE id = ?",
                            (str(audio_path), duration, meeting_id)
                        )
                        conn.commit()
                        print(f"✅ Updated meeting {meeting_id} with audio_file_path and duration")
                        
                    except Exception as audio_err:
                        print(f"⚠️ Failed to save audio file: {audio_err}")
                        # Continue with transcripts even if audio save fails
                    
                    # Process and Broadcast
                    for item in transcripts:
                        # 1. Save to DB
                        t_id = str(uuid.uuid4())
                        now = datetime.now().isoformat()
                        
                        cursor.execute(
                            """
                            INSERT INTO transcripts 
                            (id, meeting_id, transcript, timestamp, speaker, audio_start_time, audio_end_time)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                t_id,
                                meeting_id, 
                                item['text'],
                                now,
                                item['speaker'],
                                item['start'],
                                item['end']
                            )
                        )
                        # Commit immediately after each insert to make it available
                        conn.commit()
                        
                        # 2. Broadcast AFTER commit
                        await manager.broadcast(meeting_id, {
                            'type': 'transcript',
                            'meeting_id': meeting_id,
                            'is_final': True,
                            'transcript': item['text'],
                            'speaker': item['speaker'],
                            'timestamp': now,
                            'start_time': item['start'],
                            'end_time': item['end']
                        })
                        
                    conn.close()
                    print(f"💾 Saved {len(transcripts)} transcripts to DB.")
                    
                    # Add small delay to ensure frontend receives all broadcasts
                    await asyncio.sleep(0.2)
                    
                except Exception as db_err:
                    print(f"❌ DB Save Error: {db_err}")
                    
            else:
                print(f"❌ Full Pipeline Failed: {response.text}")
                
    except Exception as e:
        print(f"❌ Full Pipeline Exception: {e}")

async def process_and_broadcast(audio_data: bytes, meeting_id: str):
    """Process audio and broadcast result"""
    result = await process_audio_chunk(audio_data, meeting_id)
    if result:
        await manager.broadcast(meeting_id, {
            'type': 'transcript',
            **result
        })

@router.websocket("/ws/transcripts/{meeting_id}")
async def websocket_transcripts_endpoint(websocket: WebSocket, meeting_id: str):
    """
    WebSocket endpoint for receiving transcript updates only
    (No audio sending, just listening for updates)
    """
    await manager.connect(websocket, meeting_id)
    
    try:
        # Send initial connection success
        await websocket.send_json({
            'type': 'connected',
            'meeting_id': meeting_id
        })
        
        # Keep connection alive
        while True:
            # Wait for messages (will be sent via broadcast)
            data = await websocket.receive_text()
            # Echo back for keepalive
            await websocket.send_json({'type': 'pong'})
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, meeting_id)
    except Exception as e:
        print(f"❌ Transcript WS error: {e}")
        manager.disconnect(websocket, meeting_id)

@router.post("/broadcast/{meeting_id}")
async def broadcast_message(meeting_id: str, message: dict):
    """
    Manual broadcast endpoint for testing
    POST /broadcast/meeting-id {"type": "test", "data": "..."}
    """
    await manager.broadcast(meeting_id, message)
    return {"status": "broadcasted", "meeting_id": meeting_id}

@router.post("/ws/upload/{meeting_id}")
async def upload_audio(meeting_id: str, file: UploadFile = File(...)):
    """
    Upload audio file (mp3/wav) for processing.
    Triggers full pipeline and broadcasts results.
    """
    try:
        content = await file.read()
        print(f"📂 Received upload: {file.filename} ({len(content)} bytes) for {meeting_id}")
        
        # Trigger pipeline (awaits result, saves to DB, broadcasts to UI)
        await process_full_meeting_and_broadcast(content, meeting_id, is_raw_pcm=False)
        
        return {"status": "success", "message": "File processed"}
    except Exception as e:
        print(f"❌ Upload Error: {e}")
        return {"status": "error", "message": str(e)}
