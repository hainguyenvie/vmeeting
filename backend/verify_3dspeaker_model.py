import os
import sys
import numpy as np

def main():
    print("Testing 3D-Speaker Model Loading...")
    
    try:
        import sherpa_onnx
    except ImportError:
        print("ERROR: sherpa-onnx not installed")
        return

    appdata = os.getenv('APPDATA')
    base_dir = os.path.join(appdata, "com.meetily.ai", "models", "speaker-recognition", "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k")
    model_path = os.path.join(base_dir, "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx")
    
    print(f"Path: {model_path}")
    
    if not os.path.exists(model_path):
        print(f"ERROR: Model file missing at {model_path}")
        return

    config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(
        model=model_path,
        num_threads=1,
        debug=True, 
        provider="cpu"
    )
    
    try:
        extractor = sherpa_onnx.SpeakerEmbeddingExtractor(config)
        print("SUCCESS: Model loaded successfully!")
        
        # Test inference
        stream = extractor.create_stream()
        samples = np.zeros(16000, dtype=np.float32)
        stream.accept_waveform(16000, samples)
        stream.input_finished()
        
        if extractor.is_ready(stream):
            embedding = extractor.compute(stream)
            print(f"SUCCESS: Embedding computed! Shape: {len(embedding)}")
        else:
            print("WARNING: Extractor not ready")
            
    except Exception as e:
        print(f"ERROR: Failed to load/run model: {e}")

if __name__ == "__main__":
    main()
