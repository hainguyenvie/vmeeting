import os
import sys
import glob
import time
import io
import shutil
import tempfile
import numpy as np
import soundfile as sf
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from scipy import signal

# ==========================================
# 1. SETUP & UTILS
# ==========================================

app = FastAPI(title="Meetily STT Server (Zipformer Only)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 2. MODEL ENGINES
# ==========================================

def load_audio_robust(file_source):
    """
    Robust audio loader that handles BytesIO or paths.
    Falls back to librosa/ffmpeg if soundfile fails (e.g. WebM).
    Returns: (audio_np_array, sample_rate)
    """
    # If bytes/BytesIO, make sure we are at start
    if hasattr(file_source, 'seek'):
        file_source.seek(0)
        
    try:
        # Try soundfile first (Fast, standard)
        return sf.read(file_source, dtype='float32')
    except Exception as e:
        # Need a real file path for librosa/ffmpeg
        temp_path = None
        created_temp = False
        
        try:
            if hasattr(file_source, 'read'):
                # It's a file-like object
                file_source.seek(0)
                # Assume WebM if failing? Or just generic
                with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
                    tmp.write(file_source.read())
                    temp_path = tmp.name
                    created_temp = True
            else:
                # It's a string path?
                temp_path = file_source

            import librosa
            # librosa.load flattens to mono by default (mono=True)
            audio, sr = librosa.load(temp_path, sr=None, mono=False)
            
            # If stereo (C, N) or (N,), convert to (N, C) or (N,) to match sf.read behavior roughly
            if len(audio.shape) > 1:
                # librosa returns (channels, samples), sf returns (samples, channels)
                audio = audio.T
                
            return audio, sr
            
        except Exception as e2:
            print(f"❌ Robust load failed: {e2}")
            raise e2
        finally:
            if created_temp and temp_path and os.path.exists(temp_path):
                try: os.unlink(temp_path)
                except: pass

class ZipformerEngine:
    def __init__(self):
        self.recognizer = None
        self.loaded = False
        
    def get_model_path(self):
        # 1. Look in local 'models' folder first (Portable Mode)
        if os.path.exists("models/zipformer"):
            return "models/zipformer"
        if os.path.exists("../models/zipformer"):
            return "../models/zipformer"

        # 2. Look in AppData (Installed Mode)
        appdata = os.getenv('APPDATA')
        if appdata:
            base_path = os.path.join(appdata, "com.meetily.ai", "models", "zipformer")
            if os.path.exists(base_path): return base_path
            
        # Raise if not found
        # Ideally we might auto-download here but let's keep it simple
        raise FileNotFoundError(f"Zipformer model not found. Checked ./models and AppData.")
            
    def load(self):
        if self.loaded: return
        print("🚀 Loading Zipformer 70k (Sherpa-ONNX)...")
        
        import sherpa_onnx
        
        try:
            model_dir = self.get_model_path()
            print(f"📂 Model dir: {model_dir}")
            
            # Find files (sometimes names carry epoch numbers which change)
            encoder = glob.glob(os.path.join(model_dir, "encoder*.onnx"))[0]
            decoder = glob.glob(os.path.join(model_dir, "decoder*.onnx"))[0]
            joiner = glob.glob(os.path.join(model_dir, "joiner*.onnx"))[0]
            tokens = os.path.join(model_dir, "tokens.txt") 
            
            print(f"  - Encoder: {os.path.basename(encoder)}")
            
            # Try loading with CUDA first
            try:
                print("  - Attempting to load with provider='cuda'...")
                self.recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
                    encoder=encoder,
                    decoder=decoder,
                    joiner=joiner,
                    tokens=tokens,
                    num_threads=4,
                    sample_rate=16000,
                    feature_dim=80,
                    decoding_method="greedy_search",
                    provider="cuda"
                )
                print("✅ Zipformer Loaded on CUDA")
            except Exception as e_cuda:
                print(f"⚠️ Failed to load on CUDA: {e_cuda}")
                print("  - Falling back to provider='cpu'...")
                self.recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
                    encoder=encoder,
                    decoder=decoder,
                    joiner=joiner,
                    tokens=tokens,
                    num_threads=4,
                    sample_rate=16000,
                    feature_dim=80,
                    decoding_method="greedy_search",
                    provider="cpu"
                )
                print("✅ Zipformer Loaded on CPU")
            
            self.loaded = True
            
        except Exception as e:
            print(f"❌ Failed to load Zipformer: {e}")
            raise e

    def _check_cuda(self):
        return True 

    def unload(self):
        if self.loaded:
            print("🛑 Unloading Zipformer...")
            del self.recognizer
            import gc
            gc.collect()
            self.loaded = False

    def transcribe(self, audio_data: io.BytesIO):
        if not self.loaded: self.load()
        
        start = time.time()
        
        # Load audio robustly
        audio, sample_rate = load_audio_robust(audio_data)
        
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)
            
        if sample_rate != 16000:
            import librosa
            audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=16000)

        # Inference
        stream = self.recognizer.create_stream()
        stream.accept_waveform(16000, audio)
        self.recognizer.decode_stream(stream)
        
        text = stream.result.text.strip()
        
        # Extract segments using timestamps if available
        segments = []
        try:
            # Check if timestamps are available
            if hasattr(stream.result, 'timestamps') and hasattr(stream.result, 'tokens'):
                timestamps = stream.result.timestamps
                tokens = stream.result.tokens
                
                if timestamps and len(timestamps) == len(tokens):
                    current_seg_start = timestamps[0]
                    current_seg_tokens = []
                    last_end = timestamps[0]
                    
                    for i, t in enumerate(timestamps):
                        gap = t - last_end
                        current_dur = t - current_seg_start
                        should_split = False
                        
                        if gap > 0.35: should_split = True
                        elif current_dur > 2.5 and gap > 0.15: should_split = True
                        elif current_dur > 7.0 and gap > 0.05: should_split = True
                            
                        if should_split:
                             segment_text = "".join(current_seg_tokens).replace(" ", " ").strip()
                             if segment_text:
                                 segments.append({
                                     "start": current_seg_start,
                                     "end": last_end + 0.1,
                                     "text": segment_text
                                 })
                             current_seg_start = t
                             current_seg_tokens = []
                        
                        current_seg_tokens.append(tokens[i])
                        last_end = t
                    
                    segment_text = "".join(current_seg_tokens).replace(" ", " ").strip()
                    if segment_text:
                        segments.append({
                             "start": current_seg_start,
                             "end": last_end + 0.1,
                             "text": segment_text
                        })
                        
        except Exception as e:
            print(f"⚠️ Failed to extract timestamps from Zipformer: {e}")
            
        # Fallback if no segments created
        if not segments:
            duration_sec = len(audio) / 16000.0
            segments = [{"start": 0.0, "end": duration_sec, "text": text}]
        
        elapsed = (time.time() - start) * 1000
        
        return {
            "text": text,
            "segments": segments, 
            "total_ms": round(elapsed, 1), 
            "device": "sherpa-onnx", 
            "model": "Zipformer-70k"
        }


# ==========================================
# 3. SERVER STATE
# ==========================================

# Only Zipformer engine
engines = {
    "zipformer": ZipformerEngine(),
    "phowhisper": ZipformerEngine() # map phowhisper to zipformer just in case client requests it
}

# Default model
current_model_id = "zipformer"

@app.on_event("startup")
async def startup():
    # Pre-load default
    try:
        engines[current_model_id].load()
    except Exception:
        print("⚠️ Failed to load default model, will retry on request")


@app.post("/switch_model")
async def switch_model(model_id: str):
    global current_model_id
    # Always use zipformer regardless of what is requested, or support aliases
    return {"status": "ok", "current_model": "zipformer"}

@app.get("/current_model")
async def get_current_model():
    return {"current_model": "zipformer"}

class SpeakerManager:
    def __init__(self, model_path=None, threshold=0.45): 
        self.extractor = None
        self.threshold = threshold
        self.registry = {} 
        self.next_id = 0
        self.buffer = [] 
        self.loaded = False
        self.model_path = model_path
        self.last_speaker_id = -1
        self.last_speaker_time = 0

    def load(self):
        if self.loaded: return
        print("🚀 Loading Speaker Recognition Model (3D-Speaker ERes2Net)...")
        import sherpa_onnx
        
        # 1. Local Models (Portable)
        if not self.model_path:
             if os.path.exists("models/speaker"):
                 # Assume model file is there
                 files = glob.glob("models/speaker/*.onnx")
                 if files: self.model_path = files[0]

        # 2. AppData (Installed)
        if not self.model_path or not os.path.exists(self.model_path):
             # Auto-detect in AppData
            appdata = os.getenv('APPDATA')
            if appdata:
                base = os.path.join(appdata, "com.meetily.ai", "models", "speaker-recognition", "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k")
                if os.path.exists(base):
                     self.model_path = os.path.join(base, "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx")

        if not self.model_path or not os.path.exists(self.model_path):
            print(f"⚠️ Speaker model not found via local check or AppData")
            return

        try:
            config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                model=self.model_path,
                num_threads=2,
                debug=False,
                provider="cpu" 
            )
            self.extractor = sherpa_onnx.SpeakerEmbeddingExtractor(config)
            self.loaded = True
            print(f"✅ Speaker Recognition Loaded (Threshold: {self.threshold})")
        except Exception as e:
            print(f"❌ Failed to load speaker model: {e}")

    def identify(self, audio_samples, sample_rate=16000):
        # Enforce minimum duration of 0.5s (8000 samples at 16k)
        if not self.loaded or len(audio_samples) < 8000: 
            return None

        # Create stream
        stream = self.extractor.create_stream()
        stream.accept_waveform(sample_rate, audio_samples)
        stream.input_finished()
        
        if not self.extractor.is_ready(stream):
            return None
            
        embedding = self.extractor.compute(stream)
        embedding = np.array(embedding)
        
        # Norm
        norm = np.linalg.norm(embedding)
        if norm > 0: embedding /= norm
        
        best_score = -1
        best_id = -1
        current_time = time.time()
        
        # Compare
        for pid, data in self.registry.items():
            score = np.dot(embedding, data['centroid'])
            
            # Temporal Bias
            if pid == self.last_speaker_id and (current_time - self.last_speaker_time) < 3.0:
                 score += 0.1 
                 
            if score > best_score:
                best_score = score
                best_id = pid
                
        # Decision
        final_id = -1
        if best_score > self.threshold:
            final_id = best_id
            
            # Update centroid (Moving Average)
            alpha = 0.95
            old_centroid = self.registry[best_id]['centroid']
            new_centroid = alpha * old_centroid + (1 - alpha) * embedding
            # Renormalize
            new_norm = np.linalg.norm(new_centroid)
            if new_norm > 0: new_centroid /= new_norm
            
            self.registry[best_id]['centroid'] = new_centroid
            self.registry[best_id]['count'] += 1
            self.registry[best_id]['last_seen'] = current_time
            
        else:
            # New speaker
            final_id = self.next_id
            self.registry[final_id] = {
                'centroid': embedding, 
                'count': 1,
                'last_seen': current_time
            }
            self.next_id += 1
            
        return f"SPEAKER_{final_id:02d}"

# Global Speaker Manager
speaker_manager = SpeakerManager()

@app.on_event("startup")
async def startup_speaker():
    try:
        speaker_manager.load()
    except Exception:
        pass


@app.post("/inference")
async def inference(
    file: UploadFile = File(...),
    temperature: str = Form("0.0"),
    temperature_inc: str = Form("0.2"),
    response_format: str = Form("json"),
    diarize: str = Form("true")
):
    try:
        start = time.time()
        do_diarize = diarize.lower() == "true"
        
        audio_data = await file.read()
        audio_file = io.BytesIO(audio_data)
        
        # 1. Transcription - ALWAYS ZIPFORMER
        engine = engines["zipformer"]
        result = engine.transcribe(audio_file)
        text = result['text']
        
        if not text:
            return result 

        # 2. Diarization
        if do_diarize:
            audio_file.seek(0)
            audio, sr = load_audio_robust(audio_file)
            if len(audio.shape) > 1: audio = audio.mean(axis=1) # Mono
            if sr != 16000:
                 import librosa
                 audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
                 
            segments = result.get('segments', [])
            formatted_parts = []
            
            if not segments:
                segments = [{"start": 0.0, "end": len(audio)/16000, "text": text}]
                
            for seg in segments:
                start_sample = int(seg['start'] * 16000)
                end_sample = int(seg['end'] * 16000)
                
                start_sample = max(0, start_sample)
                end_sample = min(len(audio), end_sample)
                
                segment_audio = audio[start_sample:end_sample]
                
                # --- TRASH FILTER ---
                text_upper = seg['text'].strip().upper()
                blacklist = ["Ừ", "À", "ẬM", "Ờ", "UM", "UH", "AH", "OH", "A", "O"]
                
                is_trash = False
                if text_upper in blacklist: is_trash = True
                elif len(seg['text'].strip()) < 2 and not seg['text'].strip().isdigit(): is_trash = True
                elif len(set(text_upper)) == 1 and len(text_upper) > 3: is_trash = True
                    
                if is_trash: continue 
                # -------------------

                speaker_label = speaker_manager.identify(segment_audio)
                
                seg['speaker'] = speaker_label if speaker_label else "UNKNOWN"
                
                if speaker_label:
                    formatted_parts.append(f"[{speaker_label}]: {seg['text']}")
                else:
                    formatted_parts.append(seg['text'])
                    
            result['text'] = " ".join(formatted_parts)
            result['segments'] = segments
            
        return result
        
    except Exception as e:
        print(f"❌ Inference error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 4. FULL PIPELINE (DIARIZE-FIRST) - RESTORED
# ==========================================

def preprocess_audio_pipeline(audio):
    # Resample already done if needed, assume audio is 16k mono numpy array
    try:
        # Bandpass
        sos = signal.butter(10, [200, 7000], 'bandpass', fs=16000, output='sos')
        audio = signal.sosfilt(sos, audio)
        
        # Norm
        max_val = np.abs(audio).max()
        if max_val > 0: audio = audio / max_val * 0.9
        
        return audio
    except Exception as e:
        print(f"⚠️ Preprocessing failed: {e}")
        return audio

async def run_diarize_first_pipeline(audio_bytes, speaker_mgr, stt_engine):
    start_time = time.time()
    
    # 1. Load Audio
    try:
        audio, sr = load_audio_robust(io.BytesIO(audio_bytes))
        if len(audio.shape) > 1: audio = audio.mean(axis=1)
        if sr != 16000:
            import librosa
            audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
    except Exception as e:
        print(f"❌ Error loading audio for pipeline: {e}")
        return []

    # 2. Preprocess
    audio = preprocess_audio_pipeline(audio)
    
    # 3. Diarize (Full Scan)
    print("🔍 [Pipeline] Step 1: Diarizing...")
    
    # Reuse speaker_mgr
    if not speaker_mgr.loaded: speaker_mgr.load()
    
    window_sec = 2.0
    step_sec = 1.0
    window_samples = int(window_sec * 16000)
    step_samples = int(step_sec * 16000)
    
    timeline = [] # (start, end, speaker_id)
    current_spk = -1
    current_start = 0.0
    
    total_len = len(audio)
    
    # Local speaker registry for this session
    session_speakers = [] # {id, centroid, vector_sum, count}
    
    def get_embedding(chunk):
        stream = speaker_mgr.extractor.create_stream()
        stream.accept_waveform(16000, chunk)
        stream.input_finished()
        if not speaker_mgr.extractor.is_ready(stream): return None
        emb = np.array(speaker_mgr.extractor.compute(stream))
        n = np.linalg.norm(emb)
        if n > 0: emb /= n
        return emb

    def assign_local(emb, threshold=0.30):
        best_sim = -1.0
        best_idx = -1
        for i, spk in enumerate(session_speakers):
            sim = np.dot(emb, spk['centroid'])
            if sim > best_sim:
                best_sim = sim
                best_idx = i
        
        if best_sim > threshold:
             spk = session_speakers[best_idx]
             spk['vector_sum'] += emb
             spk['count'] += 1
             spk['centroid'] = spk['vector_sum'] / np.linalg.norm(spk['vector_sum'])
             return best_idx
        else:
             new_id = len(session_speakers)
             session_speakers.append({
                 'id': new_id, 'centroid': emb, 'vector_sum': emb, 'count': 1
             })
             return new_id

    # Scan
    for i in range(0, total_len - window_samples, step_samples):
        chunk = audio[i : i+window_samples]
        energy = np.mean(chunk**2)
        if energy < 0.001: 
            if current_spk != -1:
                timeline.append((current_start, i/16000.0 + window_sec, current_spk))
                current_spk = -1
            continue
            
        emb = get_embedding(chunk)
        if emb is None: continue
        
        spk_id = assign_local(emb)
        ts = i / 16000.0
        
        if spk_id != current_spk:
            if current_spk != -1:
                timeline.append((current_start, ts, current_spk))
            current_spk = spk_id
            current_start = ts
            
    if current_spk != -1:
         timeline.append((current_start, total_len/16000.0, current_spk))

    # 4. Merge
    print("🔗 [Pipeline] Step 2: Merging...")
    merged_timeline = []
    if timeline:
        curr_start, curr_end, curr_spk = timeline[0]
        for i in range(1, len(timeline)):
            s, e, spk = timeline[i]
            gap = s - curr_end
            if spk == curr_spk and gap < 2.0:
                curr_end = max(curr_end, e)
            else:
                if curr_end - curr_start > 1.0:
                    merged_timeline.append((curr_start, curr_end, curr_spk))
                curr_start = s
                curr_end = e
                curr_spk = spk
        if curr_end - curr_start > 1.0:
            merged_timeline.append((curr_start, curr_end, curr_spk))
            
    # 5. Transcribe Segments
    print("📝 [Pipeline] Step 3: Transcribing...")
    final_output = []
    
    for start, end, spk in merged_timeline:
        s_idx = max(0, int((start - 0.1) * 16000))
        e_idx = min(len(audio), int((end + 0.1) * 16000))
        seg_audio = audio[s_idx:e_idx]
        
        # Use ZipformerEngine's recognizer directly
        # stt_engine is a ZipformerEngine instance
        s = stt_engine.recognizer.create_stream()
        s.accept_waveform(16000, seg_audio)
        stt_engine.recognizer.decode_stream(s)
        text = s.result.text.strip()
        
        if text and len(text) > 1:
            final_output.append({
                "start": start,
                "end": end,
                "speaker": f"Speaker {spk+1}",
                "text": text
            })
            
    elapsed = time.time() - start_time
    print(f"✅ Full Pipeline Complete in {elapsed:.2f}s")
    return final_output

@app.post("/process_full_meeting")
async def process_full_meeting(file: UploadFile = File(...)):
    audio_data = await file.read()
    
    # Use current default STT
    if current_model_id not in engines:
        raise HTTPException(500, "STT Engine not ready")
        
    engine = engines[current_model_id]
    if not engine.loaded: engine.load()
    
    if not speaker_manager.loaded: speaker_manager.load()
    
    results = await run_diarize_first_pipeline(audio_data, speaker_manager, engine)
    
    return {"status": "ok", "transcripts": results}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8178)
