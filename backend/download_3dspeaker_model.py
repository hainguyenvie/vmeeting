import os
import urllib.request
import sys
import time
import onnx

# 3D-Speaker ERes2Net (Best performance in sherpa-onnx benchmarks)
# Direct GitHub release link
MODEL_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx"
MODEL_FILENAME = "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx"

# Dest
APP_DATA = os.path.join(os.environ.get("APPDATA", ""), "com.meetily.ai", "models", "speaker-recognition")
DEST_DIR = os.path.join(APP_DATA, "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k")
DEST_FILE = os.path.join(DEST_DIR, MODEL_FILENAME)

def log(msg):
    print(f"[3D-Speaker Downloader] {msg}")

def download_file(url, dest):
    log(f"Downloading from: {url}")
    log(f"Target: {dest}")
    
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    
    try:
        start_time = time.time()
        def report(block_num, block_size, total_size):
            downloaded = block_num * block_size
            if total_size > 0:
                percent = downloaded * 100 / total_size
                sys.stdout.write(f"\rProgress: {percent:.1f}% ({downloaded//1024} KB)")
                sys.stdout.flush()
        
        urllib.request.urlretrieve(url, dest, reporthook=report)
        print() # Newline
        log(f"Download complete in {time.time() - start_time:.1f}s")
        return True
    except Exception as e:
        log(f"ERROR: Download failed - {e}")
        return False

def add_metadata(filename):
    log(f"Injecting metadata into {filename}...")
    try:
        model = onnx.load(filename)
        
        # Metadata for 3D-Speaker ERes2Net
        # Ref: https://github.com/k2-fsa/sherpa-onnx/blob/master/scripts/3d-speaker/add_meta_data.py
        meta_data = {
            "framework": "3d-speaker",
            "model_type": "eres2net",
            "embedding_dim": "512", # ERes2Net base is 512
            "comment": "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k",
            "language": "Chinese", # Originally trained on CN but works generally
            "input_sample_rate": "16000",
            "sample_rate": "16000",
            "normalize_samples": "0", # 3D-Speaker often doesn't need normalization or is handled differently? Let's check docs. 
            # Actually sherpa-onnx example sets normalize_samples=0 for 3d-speaker usually, 
            # but let's stick to defaults or 0.
            "output_dim": "512" 
        }
        
        # Check existing
        for prop in model.metadata_props:
            if prop.key in meta_data:
                prop.value = str(meta_data[prop.key])
                del meta_data[prop.key] # Update done
                
        # Add remaining
        for key, value in meta_data.items():
            meta = model.metadata_props.add()
            meta.key = key
            meta.value = str(value)
            
        onnx.save(model, filename)
        log("SUCCESS: Metadata injected.")
        return True
        
    except Exception as e:
        log(f"ERROR: Metadata injection failed: {e}")
        return False

def main():
    log("Starting 3D-Speaker Model Setup...")
    
    if os.path.exists(DEST_FILE):
        if os.path.getsize(DEST_FILE) > 1000000:
             log("File exists. Skipping download.")
        else:
             download_file(MODEL_URL, DEST_FILE)
    else:
        if not download_file(MODEL_URL, DEST_FILE):
            sys.exit(1)
            
    if add_metadata(DEST_FILE):
        log("DONE. Ready to use.")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
