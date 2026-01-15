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

# Whisper.cpp server configuration
WHISPER_SERVER_URL = os.getenv("WHISPER_SERVER_URL", "http://localhost:8178")

async def process_audio_chunk(audio_data: bytes, meeting_id: str, diarize: bool = True):
    """
    Process audio chunk through Whisper.cpp
    Returns transcript text or None if error
    """
    try:
        # Call Whisper.cpp API
        async with httpx.AsyncClient(timeout=60.0) as client:  # Increased to 60s
            files = {"file": ("audio.wav", audio_data, "audio/wav")}
            response = await client.post(
                f"{WHISPER_SERVER_URL}/inference",
                files=files,
                data={
                    "temperature": "0.0",
                    "temperature_inc": "0.2",
                    "response_format": "json",
                    "diarize": str(diarize).lower() # Pass flag
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

@router.websocket("/ws/audio/{meeting_id}")
async def websocket_audio_endpoint(websocket: WebSocket, meeting_id: str):
    """
    WebSocket endpoint with 'Sliding Window Preview' & 'Periodic Final'.
    """
    await manager.connect(websocket, meeting_id)
    
    # Configuration
    SLIDING_WINDOW_SIZE = 16000 * 2 * 6  # 6 seconds sliding window for context
    FINAL_MIN_DURATION = 10.0            # 10s accumulation for final
    
    # Buffers
    draft_sliding_buffer = bytearray()   # Rolling context for preview
    final_buffer = bytearray()           # accumulated audio for final
    
    try:
        while True:
            # print("DEBUG: Waiting for message...") 
            data = await websocket.receive()
            # print(f"DEBUG: Received message keys: {data.keys()}")
            
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
                
                # 1. Feed buffers
                final_buffer.extend(audio_chunk)
                
                # NO REAL-TIME PROCESSING AS REQUESTED
                # Just accumulate.
                
                # Optional: Send "Recording..." status update every 5 seconds?
                # For now, silent.

    except WebSocketDisconnect:
        print(f"🔌 WebSocket disconnected for meeting: {meeting_id}")
        manager.disconnect(websocket, meeting_id)
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        manager.disconnect(websocket, meeting_id)
        
    finally:
        # Debug buffer size on exit
        print(f"🏁 WebSocket loop exited. Final Buffer Size: {len(final_buffer)} bytes")

async def process_preview_broadcast(audio_data: bytes, meeting_id: str):
    """
    Process sliding window for ephemeral preview.
    """
    # Diarize=False for speed
    result = await process_audio_chunk(audio_data, meeting_id, diarize=False)
    
    # If result is empty, we send empty string to "clear" the preview
    # or if silence, we just send whatever we got.
    transcript = result.get('text', '') if result else ''
    
    # Only broadcast if we have a result (even empty one could be useful to clear?)
    # But usually we only want to show text.
    # Let's broadcast updates.
    if result:
        await manager.broadcast(meeting_id, {
            'type': 'preview',
            'transcript': transcript,
            'timestamp': datetime.now().isoformat()
        })

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
            response = await client.post(
                f"{WHISPER_SERVER_URL}/process_full_meeting", # Use restored FULL PIPELINE endpoint
                files=files
            )
            
            if response.status_code == 200:
                data = response.json()
                transcripts = data.get("transcripts", [])
                print(f"✅ Full Pipeline Success! Got {len(transcripts)} segments.")
                
                # DB Connection
                import sqlite3
                import uuid
                from .database import get_db_path
                
                try:
                    conn = sqlite3.connect(get_db_path())
                    cursor = conn.cursor()
                    
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
