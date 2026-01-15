import os
import urllib.request
import sys
import time

# Direct ONNX, bypassing the tarball issues
DIRECT_ONNX_URL = "https://huggingface.co/Wespeaker/wespeaker-voxceleb-resnet34/resolve/main/voxceleb_resnet34.onnx"

# The path structure expected by stt_server.py
BASE_DIR = os.path.join(os.environ.get("APPDATA", ""), "com.meetily.ai", "models", "speaker-recognition")
TARGET_DIR = os.path.join(BASE_DIR, "sherpa-onnx-wespeaker-voxceleb-resnet34-2024-03-20")
TARGET_FILE = os.path.join(TARGET_DIR, "voxceleb-resnet34-2023.onnx") # Renaming to match expectation

def log(msg):
    print(f"[SpeakerDownloader] {msg}")

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
        
        # User-Agent is sometimes needed for HF
        opener = urllib.request.build_opener()
        opener.addheaders = [('User-Agent', 'Mozilla/5.0')]
        urllib.request.install_opener(opener)
        
        urllib.request.urlretrieve(url, dest, reporthook=report)
        print() # Newline
        log(f"Download complete in {time.time() - start_time:.1f}s")
        return True
    except Exception as e:
        log(f"ERROR: Download failed - {e}")
        return False

def main():
    log("Starting Speaker Model Download (Direct ONNX fallback)...")
    
    if os.path.exists(TARGET_FILE):
        log("File already exists.")
        if os.path.getsize(TARGET_FILE) > 10000000: # > 10MB (Model is likely ~30-50MB)
             log("File size looks good. Exiting.")
             sys.exit(0)
        else:
             log("File too small, re-downloading.")
    
    if download_file(DIRECT_ONNX_URL, TARGET_FILE):
        log("SUCCESS: Model downloaded and placed correctly.")
    else:
        log("FATAL: Could not download model.")
        sys.exit(1)

if __name__ == "__main__":
    main()
