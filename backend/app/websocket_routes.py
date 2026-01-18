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


# Calculate RMS for VAD
import numpy as np
def calculate_rms(audio_chunk: bytes) -> float:
    """Calculate Root Mean Square (RMS) amplitude of audio chunk"""
    # Assuming 16-bit PCM (2 bytes per sample)
    if len(audio_chunk) == 0: return 0.0
    arr = np.frombuffer(audio_chunk, dtype=np.int16)
    if len(arr) == 0: return 0.0  # Safety check
    mean_val = np.mean(arr**2)
    if mean_val <= 0: return 0.0  # Prevent sqrt of negative
    return np.sqrt(mean_val)

@router.websocket("/ws/audio/{meeting_id}")
async def websocket_audio_endpoint(websocket: WebSocket, meeting_id: str):
    """
    WebSocket endpoint with VAD-triggered Live Transcription.
    """
    await manager.connect(websocket, meeting_id)
    
    # Configuration
    SAMPLE_RATE = 16000
    BYTES_PER_SAMPLE = 2 # 16-bit
    
    # VAD Constants - TUNED for continuous speech
    SILENCE_THRESHOLD = 300
    SILENCE_DURATION = 2.0
    MIN_PHRASE_DURATION = 2.0
    MAX_PHRASE_DURATION = 20.0 
    COOLDOWN_DURATION = 0.5
    
    # Buffers & State
    final_buffer = bytearray()      # Full meeting audio (for DB save on stop)
    phrase_buffer = bytearray()     # Current active phrase (for live transcript)
    
    silence_start_time = None
    last_process_time = datetime.now()
    is_processing = False  # Flag to prevent duplicate processing
    
    try:
        while True:
            data = await websocket.receive()
            
            if 'text' in data:
                 message = json.loads(data['text'])
                 msg_type = message.get('type')
                 print(f"📩 Received TEXT message: {msg_type}")
                 
                 if msg_type == 'stop':
                     # Process any remaining phrase
                     if len(phrase_buffer) > 0:
                         asyncio.create_task(process_live_phrase(bytes(phrase_buffer), meeting_id))
                     
                     # Final flush (FULL PIPELINE)
                     if len(final_buffer) > 0:
                         await manager.broadcast(meeting_id, {'type': 'status', 'status': 'processing'})
                         asyncio.create_task(process_full_meeting_and_broadcast(bytes(final_buffer), meeting_id))
                     
                     await manager.broadcast(meeting_id, {'type': 'status', 'status': 'stopped'})
                     break

            elif 'bytes' in data:
                audio_chunk = data['bytes']
                result = None
                
                # 1. Feed buffers
                final_buffer.extend(audio_chunk)
                phrase_buffer.extend(audio_chunk)
                
                # 2. VAD & Trigger Logic
                rms = calculate_rms(audio_chunk)
                now = datetime.now()
                
                is_silence = rms < SILENCE_THRESHOLD
                
                # Calculate durations
                phrase_duration = len(phrase_buffer) / (SAMPLE_RATE * BYTES_PER_SAMPLE)
                time_since_last_process = (now - last_process_time).total_seconds()
                
                if is_silence:
                    if silence_start_time is None:
                        silence_start_time = now
                    else:
                        silence_duration = (now - silence_start_time).total_seconds()
                        
                        # Trigger condition: Sufficient silence AND enough audio AND not in cooldown
                        should_trigger = (
                            silence_duration > SILENCE_DURATION and 
                            phrase_duration > MIN_PHRASE_DURATION and
                            time_since_last_process > COOLDOWN_DURATION and
                            not is_processing
                        )
                        
                        if should_trigger:
                             print(f"🎤 VAD Trigger: Silence={silence_duration:.2f}s, Phrase={phrase_duration:.2f}s")
                             
                             # Set flag to prevent duplicate
                             is_processing = True
                             
                             # Copy buffer to process
                             audio_to_process = bytes(phrase_buffer)
                             
                             # --- OVERLAP STRATEGY ---
                             # Keep last 1.0s of audio (usually silence) as context for next phrase
                             # This fixes "missing start of next sentence" by giving Whisper context
                             overlap_duration = 1.0 
                             overlap_bytes = int(SAMPLE_RATE * BYTES_PER_SAMPLE * overlap_duration)
                             
                             if len(phrase_buffer) > overlap_bytes:
                                 phrase_buffer = phrase_buffer[-overlap_bytes:]
                             else:
                                 # If buffer is short (unlikely due to duration check), keep all
                                 # But actually we want to reset if it's just silence? 
                                 # No, context is good.
                                 pass 
                                 
                             # Reset only timing, keep phrase_buffer with overlap
                             silence_start_time = None
                             last_process_time = now
                             
                             # Async Process with callback to reset flag
                             async def process_with_reset():
                                 await process_live_phrase(audio_to_process, meeting_id)
                                 nonlocal is_processing
                                 is_processing = False
                             
                             asyncio.create_task(process_with_reset())
                             
                else:
                    # Voice detected, reset silence timer
                    silence_start_time = None
                    
                # 3. Force Trigger (Safety Net) - only if enough time has passed
                if phrase_duration > MAX_PHRASE_DURATION and time_since_last_process > COOLDOWN_DURATION and not is_processing:
                     print(f"⏰ Force Trigger: Max phrase duration reached ({phrase_duration:.2f}s)")
                     is_processing = True
                     audio_to_process = bytes(phrase_buffer)
                     
                     # Keep overlap even on force trigger to avoid cutting words
                     overlap_bytes = int(SAMPLE_RATE * BYTES_PER_SAMPLE * 1.0)
                     if len(phrase_buffer) > overlap_bytes:
                         phrase_buffer = phrase_buffer[-overlap_bytes:]
                     else:
                         phrase_buffer = bytearray() # Should not happen on Max Duration
                         
                     silence_start_time = None
                     last_process_time = now
                     
                     async def process_with_reset():
                         await process_live_phrase(audio_to_process, meeting_id)
                         nonlocal is_processing
                         is_processing = False
                     
                     asyncio.create_task(process_with_reset())

    except WebSocketDisconnect:
        print(f"🔌 WebSocket disconnected for meeting: {meeting_id}")
        manager.disconnect(websocket, meeting_id)
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        import traceback
        traceback.print_exc()
        manager.disconnect(websocket, meeting_id)
        
    finally:
        print(f"🏁 WebSocket loop exited. Final Buffer Size: {len(final_buffer)} bytes")

async def process_live_phrase(audio_data: bytes, meeting_id: str):
    """
    Process a specific phrase for live display.
    Broadcasting 'live_transcript' event.
    """
    # WRAP IN WAV HEADER (Critical fix for raw PCM)
    wav_data = create_wav_bytes(audio_data)
    
    # Disable diarization for live transcripts as requested
    result = await process_audio_chunk(wav_data, meeting_id, diarize=False)
    
    if result and result.get('transcript'):
        text = result['transcript'].strip()
        
        # --- TRASH FILTER for Live Transcripts ---
        text_upper = text.upper()
        blacklist = ["Ừ", "À", "ẬM", "Ờ", "UM", "UH", "AH", "OH", "A", "O", "HỬ", "Ử"]
        
        is_trash = False
        if text_upper in blacklist:
            is_trash = True
        elif len(text) < 2 and not text.isdigit():
            is_trash = True
        elif len(set(text_upper)) == 1 and len(text_upper) > 3:  # Repeated char
            is_trash = True
        elif text_upper in ["HỬ HỬ", "Ử Ử", "ỬA", "ỬM"]:  # Common Vietnamese fillers
            is_trash = True
            
        if is_trash:
            print(f"🚮 Filtered trash from live: '{text}'")
            return  # Don't broadcast
        # -------------------
        
        # Broadcast special "live_transcript" type
        await manager.broadcast(meeting_id, {
            'type': 'live_transcript',
            'transcript': text,
            'speaker': result.get('speaker', 'Unknown'),
            'timestamp': datetime.now().isoformat()
        })


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
