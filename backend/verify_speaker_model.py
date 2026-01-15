import os
import sys
import numpy as np

try:
    import sherpa_onnx
except ImportError:
    print("sherpa_onnx not installed. Installing...")
    # This might not work if pip is not in path, but usually it is in the env
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "sherpa-onnx"])
    import sherpa_onnx

def main():
    print("Testing Speaker Model Loading...")
    
    appdata = os.getenv('APPDATA')
    model_path = os.path.join(appdata, "com.meetily.ai", "models", "speaker-recognition", "sherpa-onnx-wespeaker-voxceleb-resnet34-2024-03-20", "voxceleb-resnet34-2023.onnx")
    
    if not os.path.exists(model_path):
        print(f"❌ Model not found at {model_path}")
        return

    config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(
        model=model_path,
        num_threads=1,
        debug=True, # Enable debug to see the logs from C++
        provider="cpu"
    )
    
    try:
        extractor = sherpa_onnx.SpeakerEmbeddingExtractor(config)
        print("SUCCESS: Model loaded successfully!")
        
        # Test inference
        print("Running dummy inference...")
        stream = extractor.create_stream()
        # 1 second of silence
        samples = np.zeros(16000, dtype=np.float32)
        stream.accept_waveform(16000, samples)
        stream.input_finished()
        
        if extractor.is_ready(stream):
            embedding = extractor.compute(stream)
            print(f"SUCCESS: Embedding computed! Shape: {len(embedding)}")
        else:
            print("WARNING: Extractor not ready (might need more audio)")
            
    except Exception as e:
        print(f"ERROR: Failed to load/run model: {e}")

if __name__ == "__main__":
    main()
