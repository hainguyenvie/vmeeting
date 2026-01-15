import os
import urllib.request
import sys
import numpy as np
import sherpa_onnx
import time
# Generate synthetic audio for testing
FILES = ["test_spk1.wav", "test_spk2.wav"]

def generate_tone(filename, freq=440, duration=2.0, sr=16000):
    import wave
    import struct
    import numpy as np
    
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    # Speaker 1: Pure Tone 440Hz
    audio = 0.5 * np.sin(2 * np.pi * freq * t)
    
    # Write to WAV
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sr)
        # Convert to int16
        data = (audio * 32767).astype(np.int16)
        wav_file.writeframes(data.tobytes())

def download_test_files():
    print("Generating synthetic test files...")
    # Spk 1: Low-pitch voice simulation (Tone 150Hz)
    generate_tone(FILES[0], freq=150)
    # Spk 2: High-pitch voice simulation (Tone 300Hz)
    generate_tone(FILES[1], freq=300)

def get_extractor():
    appdata = os.getenv('APPDATA')
    base_dir = os.path.join(appdata, "com.meetily.ai", "models", "speaker-recognition", "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k")
    model_path = os.path.join(base_dir, "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx")
    
    if not os.path.exists(model_path):
        print(f"Model not found: {model_path}")
        sys.exit(1)
        
    config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(
        model=model_path,
        num_threads=1,
        debug=False, 
        provider="cpu"
    )
    return sherpa_onnx.SpeakerEmbeddingExtractor(config)

def compute_embedding(extractor, wav_file):
    import wave
    with wave.open(wav_file, 'rb') as wf:
        sr = wf.getframerate()
        samples = wf.readframes(wf.getnframes())
        samples = np.frombuffer(samples, dtype=np.int16).astype(np.float32) / 32768.0
        
        # 3D-Speaker expects 16k. The test files ARE 16k.
        # But let's verify logic if we were to split it.
        
        stream = extractor.create_stream()
        stream.accept_waveform(sr, samples)
        stream.input_finished()
        
        if extractor.is_ready(stream):
            emb = np.array(extractor.compute(stream))
            # Normalize
            norm = np.linalg.norm(emb)
            if norm > 0: emb /= norm
            return emb
    return None

def compute_embedding_from_samples(extractor, samples, sr=16000):
    stream = extractor.create_stream()
    stream.accept_waveform(sr, samples)
    stream.input_finished()
    if extractor.is_ready(stream):
        emb = np.array(extractor.compute(stream))
        norm = np.linalg.norm(emb)
        if norm > 0: emb /= norm
        return emb
    return None

def main():
    download_test_files()
    extractor = get_extractor()
    print("Model Loaded.")
    
    # Load spk1
    import wave
    with wave.open(FILES[0], 'rb') as wf:
        full_samples = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0

    print(f"Full Audio Duration: {len(full_samples)/16000:.2f}s")
    
    durations = [0.1, 0.3, 0.5, 1.0, 2.0]
    
    for d in durations:
        num_samples = int(d * 16000)
        if num_samples > len(full_samples): break
        
        seg_a = full_samples[:num_samples]
        # Use a DIFFERENT segment for part B to test stability (e.g. from end)
        seg_b = full_samples[-num_samples:] 
        
        emb_a = compute_embedding_from_samples(extractor, seg_a)
        emb_b = compute_embedding_from_samples(extractor, seg_b)
        
        if emb_a is None or emb_b is None:
            print(f"Duration {d}s: Failed to extract")
            continue
            
        score = np.dot(emb_a, emb_b)
        print(f"Duration {d}s Similarity: {score:.4f}")

    # Different Speaker Test (Full length)
    with wave.open(FILES[1], 'rb') as wf:
        samples2 = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    
    emb1 = compute_embedding_from_samples(extractor, full_samples)
    emb2 = compute_embedding_from_samples(extractor, samples2)
    diff_score = np.dot(emb1, emb2)
    print(f"Different Speaker (Full): {diff_score:.4f}")

if __name__ == "__main__":
    main()
