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
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

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


def enhance_audio_for_asr(audio: np.ndarray, sr: int = 16000) -> np.ndarray:
    """
    Pipeline D_LITE — kết quả benchmark tốt nhất trên 3 file meeting thực tế.

    Chỉ 2 bước, overhead ~2–21ms (thay vì ~450–550ms của pipeline cũ):
    1. RMS normalization  — đảm bảo biên độ nhất quán (~-20 dBFS)
    2. Bandpass filter    — giữ lại dải tần tiếng nói (80–7500 Hz)
    3. Peak normalization — output ổn định vào model

    ✅ Lý do bỏ spectral denoising:
    - Tốn 450–550ms cho 100s audio — phần lớn thời gian xử lý
    - Benchmark thực tế: word count tương đương baseline (chênh ~0.17%)
    - Noisereduce tạo artifacts ('musical noise') → model đọc sai fricatives
      VD: 'treo banner' → 'chịu bánh nước' khi dùng prop_decrease=0.6

    ✅ Lý do bỏ pre-emphasis (α=0.95):
    - Modern neural ASR (Moonshine/Whisper) có learned feature extraction
    - Research 2024: pre-emphasis có thể distort fricatives (s, sh, ch)
    - Benchmark: không cải thiện word count trên bất kỳ file nào
    """
    if len(audio) == 0:
        return audio

    audio = audio.astype(np.float32)

    # 1. RMS Normalization → target -20 dBFS
    rms = np.sqrt(np.mean(audio ** 2))
    if rms > 1e-8:
        audio = audio * (0.1 / rms)          # 0.1 ≈ -20 dBFS
        audio = np.clip(audio, -1.0, 1.0)

    # 2. Bandpass filter: 80 Hz – 7500 Hz
    #    - Loại bỏ hum điện / rung bàn (< 80 Hz)
    #    - Loại bỏ HF noise gần Nyquist (> 7500 Hz)
    #    - Lightweight: ~2ms cho 100s audio
    nyq = sr / 2.0
    try:
        sos = signal.butter(4, [80.0 / nyq, 7500.0 / nyq], btype='band', output='sos')
        audio = signal.sosfilt(sos, audio)
    except Exception:
        pass

    # 3. Peak normalization → [-0.95, 0.95]
    peak = np.max(np.abs(audio))
    if peak > 1e-8:
        audio = audio / peak * 0.95

    return audio.astype(np.float32)


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

class MoonshineEngine:
    """
    Moonshine ASR với Silero VAD tích hợp (chuẩn production như whisperX).

    Pipeline:
      1. Silero VAD → phát hiện đoạn có voice (loại bỏ nhạc/tiếng ồn)
      2. Merge các speech segment gần nhau thành chunk ≤ 30s
      3. Transcribe từng chunk với MoonshineForConditionalGeneration
         sử dụng đúng max_length theo công thức tác giả (13 tok/s cho Việt)

    Why Silero VAD?
      - Lightweight (~1MB), real-time capable
      - Được dùng bởi whisperX, faster-whisper, insanely-fast-whisper
      - Loại bỏ hoàn toàn hallucination do nhạc/noise-only sections
    """

    # Công thức từ model card của UsefulSensors
    MAX_TOKENS_PER_SEC = 13.0    # non-Latin (Việt, Hàn, Nhật...). Anh = 6.5
    MAX_CHUNK_SEC      = 30.0    # chunk tối đa gửi vào model
    MIN_SPEECH_SEC     = 0.5     # speech segment ngắn hơn → bỏ qua
    VAD_MERGE_GAP_SEC  = 0.3     # merge 2 speech segments cách nhau < 0.3s

    def __init__(self, model_id="UsefulSensors/moonshine-base-vi"):
        self.model_id    = model_id
        self.processor   = None
        self.model       = None
        self.vad_model   = None    # Silero VAD
        self.vad_utils   = None    # get_speech_timestamps, ...
        self.loaded      = False
        self.device      = "cuda" if torch.cuda.is_available() else "cpu"
        self.torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

    # ------------------------------------------------------------------
    # Load / Unload
    # ------------------------------------------------------------------
    def load(self):
        if self.loaded: return
        print(f"🚀 Loading Moonshine + Silero VAD on {self.device.upper()} ({self.torch_dtype})...")
        from transformers import AutoProcessor, MoonshineForConditionalGeneration

        # 1. Moonshine ASR model (theo model card chính thức)
        self.processor = AutoProcessor.from_pretrained(self.model_id)
        self.model = MoonshineForConditionalGeneration.from_pretrained(
            self.model_id,
            torch_dtype=self.torch_dtype,
            low_cpu_mem_usage=True,
        ).to(self.device)
        self.model.eval()

        # 2. Silero VAD (torch.hub — tự cache, không cần cài thêm)
        print("  📡 Loading Silero VAD...")
        try:
            self.vad_model, self.vad_utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                trust_repo=True,
            )
            self.vad_model = self.vad_model.to(self.device)
            print("  ✅ Silero VAD loaded")
        except Exception as e:
            print(f"  ⚠️ Silero VAD load failed ({e}), will transcribe without VAD")
            self.vad_model = None

        self.loaded = True
        print(f"✅ MoonshineEngine ready")

    def unload(self):
        if self.loaded:
            print("🛑 Unloading Moonshine + VAD...")
            del self.model, self.processor
            if self.vad_model is not None:
                del self.vad_model
            import gc
            if self.device == "cuda":
                torch.cuda.empty_cache()
            gc.collect()
            self.loaded = False

    # ------------------------------------------------------------------
    # Silero VAD: trả về list [{"start": float, "end": float}, ...]
    # ------------------------------------------------------------------
    def _get_speech_segments(self, audio: np.ndarray, duration_sec: float) -> list:
        """
        Chạy Silero VAD. Smart packing:
        Gộp các speech segments có khoảng cách < 2s thành 1 chunk lớn,
        nhưng đảm bảo max length <= 29s để cắt chính xác vào lúc lặng 
        (không bị cắt giữa từ do blind cut ở 30s).
        Thêm padding 0.3s để không mất âm VAD cắt quá sát.
        """
        if self.vad_model is None:
            return [{"start": 0.0, "end": duration_sec}]

        get_speech_timestamps = self.vad_utils[0]
        audio_tensor = torch.from_numpy(audio.astype(np.float32))
        if self.device == "cuda":
            audio_tensor = audio_tensor.to(self.device)

        with torch.no_grad():
            raw_timestamps = get_speech_timestamps(
                audio_tensor,
                self.vad_model,
                sampling_rate=16000,
                return_seconds=True,
                threshold=0.5,             # Default Silero — benchmark cho thấy 0.6 quá strict, miss speech
                min_speech_duration_ms=500,
                min_silence_duration_ms=200,
            )

        # raw_timestamps: [{"start": ..., "end": ...}, ...]
        if not raw_timestamps:
            print("  ⚠️ VAD: không phát hiện voice")
            return []

        # Smart packing
        merged = []
        curr_start = raw_timestamps[0]["start"]
        curr_end   = raw_timestamps[0]["end"]

        for seg in raw_timestamps[1:]:
            gap = seg["start"] - curr_end
            
            # TẠI SAO GỘP <= 29s? 
            # Model kiến trúc Whisper / Moonshine được train trên các chunk audio tối đa 30s. 
            # Nếu đưa audio dài hơn 30s, model sẽ tự động "blind cut" (cắt mù) 30s đầu rồi bỏ đi phần sau, 
            # hoặc phải tìm thuật toán cắt rủi ro (thường cắt ngang chữ nằm giữa giây số 29 và 30).
            # Do đó chúng ta chủ động tìm chỗ im lặng (lúc người ta nín thở / hết câu) ĐỂ CẮT TRƯỚC (<29s)
            # để đảm bảo không một chữ nào bị cắt làm đôi.
            if gap <= 2.0 and (seg["end"] - curr_start <= 29.0):
                curr_end = seg["end"]
            else:
                # Pad 0.3s để hứng âm đuôi (âm gió)
                merged.append({
                    "start": max(0.0, curr_start - 0.3),
                    "end": min(duration_sec, curr_end + 0.3)
                })
                curr_start = seg["start"]
                curr_end = seg["end"]

        merged.append({
            "start": max(0.0, curr_start - 0.3), 
            "end": min(duration_sec, curr_end + 0.3)
        })

        print(f"  🎙️ VAD: {len(raw_timestamps)} raw → {len(merged)} smartly packed chunks")
        return merged

    # ------------------------------------------------------------------
    # Transcribe một đoạn audio numpy (đã là 16kHz mono)
    # ------------------------------------------------------------------
    def _transcribe_segment(self, audio_seg: np.ndarray) -> str:
        """
        Transcribe một numpy array audio sử dụng Moonshine.
        max_length tính từ attention_mask theo công thức tác giả.
        """
        if len(audio_seg) == 0:
            return ""

        inputs = self.processor(
            audio_seg,
            sampling_rate=16000,
            return_tensors="pt",
        )
        # ✅ Cast dtype đúng như model card
        inputs = inputs.to(self.device, self.torch_dtype)

        # ✅ max_length theo công thức chính thức của tác giả:
        #    token_limit_factor = MAX_TOKENS_PER_SEC / sampling_rate
        #    max_length = int((attention_mask.sum(dim=-1) * token_limit_factor).max())
        #
        # ⚠️  Note về warning "exceeded model's predefined maximum length (194)":
        #    Model gốc có generation_config.max_length=194 (cho tiếng Anh, 6.5 tok/s × 30s).
        #    Ta dùng 13.0 tok/s cho tiếng Việt → max_length=390 cho chunk 30s.
        #    Transformers cảnh báo khi vượt 194, nhưng vẫn generate đúng đến 390.
        #    Đây là behavior BÌNH THƯỜNG và ĐÚNG cho tiếng Việt.
        if hasattr(inputs, "attention_mask") and inputs.attention_mask is not None:
            # Dùng .float() để tránh precision loss khi sum lớn số lượng samples
            dur_sec = (inputs.attention_mask.sum(dim=-1).float().max().item()) / 16000.0
        else:
            dur_sec = len(audio_seg) / 16000.0

        # ✅ Sửa Lỗi Cắt Chữ: Tăng giới hạn sinh mã lên 35 tokens/giây, vì Tiếng Việt nhiều âm tiết hơn Tiếng Anh rất nhiều.
        # Dùng max_new_tokens thay vỉ max_length (tổng độ dài gốc) để tránh việc model đếm cả các prompt padding dẫn đến ngắt sớm.
        max_new_tokens = max(10, int(dur_sec * 35.0))

        print(f"     → Computed max_new_tokens: {max_new_tokens}")
        import warnings
        with torch.no_grad(), warnings.catch_warnings():
            # Suppress expected warning về model's predefined max_length
            warnings.filterwarnings("ignore", message=".*exceeded the model's predefined maximum length.*")
            generated_ids = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,   # Sử dụng max_new_tokens an toàn hơn
                do_sample=False,
                num_beams=3,
                repetition_penalty=1.1,
                no_repeat_ngram_size=7,          # Ngăn chặn vòng lặp "Dạ đúng rồi. Dạ đúng rồi..."
            )

        return self.processor.batch_decode(
            generated_ids, skip_special_tokens=True
        )[0].strip()

    # ------------------------------------------------------------------
    # Public: transcribe toàn bộ file audio
    # ------------------------------------------------------------------
    def transcribe(self, audio_data: io.BytesIO) -> dict:
        if not self.loaded:
            self.load()

        t_start = time.time()

        # 1. Load audio → 16kHz mono float32
        audio, sr = load_audio_robust(audio_data)
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)
        if sr != 16000:
            import librosa
            audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
        audio = audio.astype(np.float32)

        duration_sec = len(audio) / 16000.0
        print(f"🎵 Moonshine: {duration_sec:.2f}s audio")

        # 2. Audio enhancement D_LITE (RMS normalize + bandpass 80-7500Hz)
        #    Áp dụng TRƯỚC VAD để VAD detect voice chính xác hơn trên audio sạch
        t_enhance = time.time()
        audio = enhance_audio_for_asr(audio, sr=16000)
        print(f"  🔊 Audio enhanced in {(time.time()-t_enhance)*1000:.0f}ms")

        # 3. Silero VAD → lấy các khoảng thời gian có lời (đã smart back và pad 0.3s)
        speech_segs = self._get_speech_segments(audio, duration_sec)
        
        # Danh sách các hallucination phổ biến của Moonshine khi lẫn tạp âm
        HALLUCINATIONS = [
            "hãy subscribe cho kênh",
            "để không bỏ lỡ những video hấp dẫn",
            "ghiền mì gõ",
            "bạn đã xem video",
            "viết phụ đề bởi",
            "người dịch:",
            "cảm ơn các bạn"
        ]

        all_segments: list = []
        full_texts:   list = []
        MAX_CHUNK_SAMPLES = int(self.MAX_CHUNK_SEC * 16000)

        for speech in speech_segs:
            seg_start = speech["start"]
            seg_end   = speech["end"]
            
            s_idx = int(seg_start * 16000)
            e_idx = int(seg_end   * 16000)
            seg_audio = audio[s_idx:e_idx]

            # Với smart packing, đa phần các chunk < 29s. Chỉ khi có 1 đoạn nói LIÊN TỤC KHÔNG NGHỈ >30s
            # thì mới phải chia nhỏ mù.
            for j in range(0, len(seg_audio), MAX_CHUNK_SAMPLES):
                chunk        = seg_audio[j : j + MAX_CHUNK_SAMPLES]
                # THỜI GIAN THỰC GỐC của đoạn audio: seg_start (đầu của cụm VAD) + j (độ dịch chuyển trong file)
                chunk_start  = seg_start + (j / 16000.0)
                chunk_end    = chunk_start + (len(chunk) / 16000.0)
                chunk_dur    = len(chunk) / 16000.0

                if chunk_dur < 0.2:
                    continue  # Bỏ qua mẩu dư quá bé

                print(f"  🔄 Transcribing {chunk_start:.2f}s–{chunk_end:.2f}s ({chunk_dur:.1f}s)...")
                text = self._transcribe_segment(chunk)
                
                # Filter ảo giác (hallucination)
                txt_lower = text.lower()
                is_hallucination = False
                for h in HALLUCINATIONS:
                    # Nếu toàn bộ văn bản CẢ ĐOẠN 10-20 giây chỉ là một dòng ảo giác này (rất hay gặp do AI sinh ra lúc im lặng)
                    if h in txt_lower:
                        is_hallucination = True
                        break
                        
                # Ứng xử với Hallucination: BIẾN MẤT LUÔN vì trong thực tế đoạn này CHỈ CHỨA TIẾNG QUẠT ỒN NHỎ.
                # Bản thân VAD đã lọc nhưng audio này có dải tần nhiễu khiến VAD bỏ lọt, và Model sinh ra lời rác.
                if is_hallucination:
                    print(f"     🗑️  Đã lọc bỏ hallucination (ẩn luôn): {text}")
                    continue

                if text:
                    print(f"     → {len(text)} chars: {text[:80]}")
                    all_segments.append({
                        "start": float(chunk_start),
                        "end":   float(chunk_end),
                        "text":  text,
                    })
                    full_texts.append(text)

        full_text = " ".join(full_texts).strip()

        if not all_segments and duration_sec < 5.0 and full_text:
             all_segments = [{"start": 0.0, "end": duration_sec, "text": full_text}]

        elapsed_ms = (time.time() - t_start) * 1000
        n_speech   = sum(s["end"] - s["start"] for s in speech_segs)
        print(f"⏱️  Moonshine done: {elapsed_ms/1000:.2f}s | "
              f"voice={n_speech:.1f}s/{duration_sec:.1f}s | "
              f"{len(all_segments)} segments")

        return {
            "text":     full_text,
            "segments": all_segments,
            "total_ms": round(elapsed_ms, 1),
            "device":   f"huggingface-{self.device}",
            "model":    "Moonshine-base-vi",
        }

# ==========================================
# 3. SERVER STATE
# ==========================================

# Zipformer and Moonshine engine
engines = {
    "zipformer": ZipformerEngine(),
    "moonshine": MoonshineEngine(),
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

pyannote_pipeline = None

def get_pyannote_pipeline():
    global pyannote_pipeline
    if pyannote_pipeline is None:
        print("🚀 Loading Pyannote 3.1 Pipeline on CUDA...")
        from pyannote.audio import Pipeline
        import torch
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token="YOUR_HF_TOKEN_HERE"
        )
        if torch.cuda.is_available():
            pipeline.to(torch.device("cuda"))
            
        # Optimization: Tăng kích thước gói (batch size) từ 1 mặc định lên 32
        # Giúp GPU xứ lý đa luồng đồng thời -> Tăng tốc độ Diarization gấp 15-20 lần cho file dài
        if hasattr(pipeline, "segmentation_batch_size"):
            pipeline.segmentation_batch_size = 32
        if hasattr(pipeline, "embedding_batch_size"):
            pipeline.embedding_batch_size = 32
            
        pyannote_pipeline = pipeline
        print(f"✅ Pyannote loaded! (Seg batch: {getattr(pipeline, 'segmentation_batch_size', 1)}, Embed batch: {getattr(pipeline, 'embedding_batch_size', 1)})")
    return pyannote_pipeline

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
        
    duration = len(audio) / 16000.0

    # 2. Preprocess (D_LITE pipeline)
    print("🧹 [Pipeline] Step 1: Enhancing...")
    audio = enhance_audio_for_asr(audio)
    
    # 3. Pyannote Diarization (Chuẩn SOTA 2025)
    print("🔍 [Pipeline] Step 2: Pyannote Diarization (16ms frame)...")
    import torch
    
    pipeline = get_pyannote_pipeline()
    
    # Pyannote yêu cầu Tensor dạng (channels, samples)
    waveform = torch.from_numpy(audio.astype(np.float32)).unsqueeze(0)
    
    diarization = pipeline({"waveform": waveform, "sample_rate": 16000})
    
    # Check what pipeline returns, it might be a DiarizeOutput object or an Annotation object.
    # Pyannote version 3.1 returns an Annotation object usually, but in some frameworks it's different.
    # To be perfectly safe, let's dump its attributes if it crashes, or just use it correctly: 
    raw_spk_timeline = []
    
    # Pyannote version 3.1 returns a DiarizeOutput object
    annotation = diarization.speaker_diarization if hasattr(diarization, "speaker_diarization") else diarization
        
    for turn, _, speaker in annotation.itertracks(yield_label=True):
        raw_spk_timeline.append((turn.start, turn.end, speaker))
        
    if not raw_spk_timeline:
        print("⚠️ No speech detected for diarization.")
        return []
        
    print("🔗 [Pipeline] Step 3: Merging Pyannote segments (Smart Per-Speaker Merging)...")
    
    # Gom nhóm segment độc lập cho từng người nói, vì Pyannote trả về Timeline xếp chồng (Overlap)
    spk_to_segs = {}
    for s, e, spk in raw_spk_timeline:
        if spk not in spk_to_segs:
            spk_to_segs[spk] = []
        spk_to_segs[spk].append((s, e))
        
    merged_timeline = []
    for spk, segs in spk_to_segs.items():
        # Sắp xếp segment của người này theo thời gian
        segs.sort(key=lambda x: x[0])
        
        cur_s, cur_e = segs[0]
        for s, e in segs[1:]:
            # Có thể gộp nếu khoảng lặng < 2.0s và tổng độ dài < 25s
            if s - cur_e <= 2.0 and (e - cur_s) < 25.0: 
                cur_e = max(cur_e, e)
            else:
                # Lọc bỏ các tiếng thở dài, tạp âm cực ngắn (<0.4s) bị nhận dạng nhầm nếu đứng bơ vơ
                if cur_e - cur_s >= 0.4:
                    merged_timeline.append((cur_s, cur_e, spk))
                cur_s, cur_e = s, e
                
        if cur_e - cur_s >= 0.4:
            merged_timeline.append((cur_s, cur_e, spk))

    # Sắp xếp lại timeline tổng hợp theo thời gian bắt đầu
    merged_timeline.sort(key=lambda x: x[0])

    # Re-index labels sequentially based on their first appearance
    num_speakers = len(set(lbl for _, _, lbl in merged_timeline))
    label_map = {}
    next_id = 0
    renumbered_timeline = []
    for start, end, lbl in merged_timeline:
        if lbl not in label_map:
            label_map[lbl] = next_id
            next_id += 1
        renumbered_timeline.append((start, end, label_map[lbl]))
    merged_timeline = renumbered_timeline

    print(f"📊 Identified {num_speakers} speakers in {len(merged_timeline)} segments via Pyannote.")

    # 5. Transcribe
    print("📝 [Pipeline] Step 4: Transcribing segments...")
    final_output = []
    
    for i, (start, end, spk) in enumerate(merged_timeline):
        # Dynamic Padding: fix lỗi mất chữ ở đầu/cuối câu nhưng KHÔNG lấy lấn sang giọng của người khác (dính 2 người)
        # Giới hạn padding tối đa 0.3s. Nếu câu tiếp theo bắt đầu quá sát, ta chia đôi khoảng trống.
        s_pad = 0.3
        if i > 0:
            prev_end = merged_timeline[i-1][1]
            if start - prev_end < 0.6:
                s_pad = max(0, (start - prev_end) / 2.0)
                
        e_pad = 0.3
        if i < len(merged_timeline) - 1:
            next_start = merged_timeline[i+1][0]
            if next_start - end < 0.6:
                e_pad = max(0, (next_start - end) / 2.0)
                
        s_idx = max(0, int((start - s_pad) * 16000))
        e_idx = min(len(audio), int((end + e_pad) * 16000))
        seg_audio = audio[s_idx:e_idx]
        
        # Check engine type (Moonshine or Zipformer)
        if hasattr(stt_engine, "_transcribe_segment"):
            # MoonshineEngine has a strict max 30s limit to avoid context truncation (losing audio tail).
            duration_seg = len(seg_audio) / 16000.0
            if hasattr(stt_engine, "_get_speech_segments") and duration_seg > 29.0:
                print(f"  ✂️ Segment too long ({duration_seg:.1f}s), splitting using VAD...")
                # Use Moonshine's built-in VAD packer to safely break > 29s blocks at quiet points
                sub_chunks = stt_engine._get_speech_segments(seg_audio, duration_seg)
                chunk_texts = []
                for sub in sub_chunks:
                    ss_idx = int(sub["start"] * 16000)
                    ee_idx = int(sub["end"] * 16000)
                    sub_audio = seg_audio[ss_idx:ee_idx]
                    if len(sub_audio) / 16000.0 < 0.2: 
                        continue
                    ctext = stt_engine._transcribe_segment(sub_audio)
                    if ctext:
                        chunk_texts.append(ctext)
                text = " ".join(chunk_texts)
            else:
                text = stt_engine._transcribe_segment(seg_audio)
                
        elif hasattr(stt_engine, "recognizer"):
            # ZipformerEngine
            s = stt_engine.recognizer.create_stream()
            s.accept_waveform(16000, seg_audio)
            stt_engine.recognizer.decode_stream(s)
            text = s.result.text.strip()
        else:
            text = "***"
            
        # Thêm regex khử các cụm từ bị lặp vô hạn nếu Moonshine vẫn còn rớt
        import re
        # Tìm cụm từ dài ít nhất 10 ký tự lặp đi lặp lại từ 3 lần trở lên và thay bằng 1 lần
        text = re.sub(r'(.{6,}?)(?:\s*\1){2,}', r'\1', text)
        
        t_lower = text.lower()
        
        # Comprehensive Hallucination Filter 
        hallu_keywords = [
            "ghiền mì", "youtube", "subscribe", "la la school",
            "đăng ký kênh", "để không bỏ lỡ", "những video hấp dẫn",
            "bạn đã xem video", "cảm ơn các bạn", "người dịch:", 
            "subtitles by", "amara.org", "viết phụ đề bởi", "like và share",
            "hẹn gặp lại", "hẹn gặp lạ"
        ]
        
        is_hallucination = any(hk in t_lower for hk in hallu_keywords) or len(text.strip()) < 3
            
        if text and not is_hallucination:
            final_output.append({
                "start": float(start),
                "end": float(end),
                "speaker": f"Speaker {spk+1}",
                "text": text
            })
            print(f"  ✅ [{start:.2f}-{end:.2f}] Speaker {spk+1}: {text[:50]}...")
            
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

# ==========================================
# 5. OPENAI COMPATIBLE ENDPOINT
# ==========================================

@app.post("/v1/audio/transcriptions")
async def openai_transcriptions(
    file: UploadFile = File(...),
    model: str = Form("whisper-1"),
    response_format: str = Form("json"),
    temperature: float = Form(0.0),
    diarization: str = Form("false"),
):
    """
    OpenAI-compatible endpoint for transcriptions.
    """
    try:
        # Load audio data
        audio_data = await file.read()
        audio_file = io.BytesIO(audio_data)
        
        # Choose engine based on request
        # 'diarization' flag true -> this is a full meeting process or final chunk (so use moonshine)
        # 'diarization' flag false -> this is a live processing short chunk (so use zipformer)
        if diarization.lower() == "true":
            engine = engines["moonshine"]
            if not engine.loaded: engine.load()
            
            # Using new optimized diarization-first pipeline
            if not speaker_manager.loaded: speaker_manager.load()
            segments = await run_diarize_first_pipeline(audio_data, speaker_manager, engine)
            text = " ".join([seg["text"] for seg in segments])
            result = {
                "text": text,
                "segments": segments,
                "total_ms": sum((seg["end"] - seg["start"]) * 1000 for seg in segments) if segments else 0,
                "model": "moonshine-diarized"
            }
        else:
            engine = engines["zipformer"]
            if not engine.loaded: engine.load()
            
            # Standard transcribe without diarization
            result = engine.transcribe(audio_file)
            text = result['text']
            
        # Format response based on requests
        if response_format == "json":
            return {"text": text}
        elif response_format == "text":
            return text
        elif response_format == "verbose_json":
            return {
                "task": "transcribe",
                "language": "english", # Zipformer is English/Multilingual? Assuming detected or default
                "duration": result.get('total_ms', 0) / 1000.0,
                "text": text,
                "segments": result.get('segments', []),
                "model": result.get("model", "unknown")
            }
        else:
            return {"text": text}

    except Exception as e:
        print(f"❌ OpenAI Endpoint Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8178)
