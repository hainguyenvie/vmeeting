
import requests
import json
import sys
import os
import time

# Configuration
API_URL = "http://localhost:2202/v1/audio/transcriptions"

def test_live_mode(audio_path):
    print(f"\n--- 1. Testing LIVE Mode (Fast, No Diarization) ---")
    print(f"Endpoint: {API_URL}")
    print("Params: diarization=false")
    
    start_time = time.time()
    try:
        with open(audio_path, "rb") as f:
            response = requests.post(
                API_URL,
                files={"file": f},
                data={
                    "model": "whisper-1", 
                    "response_format": "verbose_json",
                    "diarization": "false" 
                }
            )
            response.raise_for_status()
            data = response.json()
            
            elapsed = time.time() - start_time
            print(f"✅ Status: Success (Took {elapsed:.2f}s)")
            
            # Print FULL Text
            print(f"📝 Full Text:\n{data.get('text', '')}")
            
            # Verify no speaker tags
            segments = data.get('segments', [])
            if segments:
                if 'speaker' not in segments[0]:
                    print("✅ Verified: No speaker labels present (Correct for Live Mode)")
                else:
                    print("⚠️ warning: Speaker labels found? Should not happen in live mode.")
            else:
                 print("⚠️ No segments returned.")
                 
    except Exception as e:
        print(f"❌ Failed: {e}")

def test_final_mode(audio_path):
    print(f"\n--- 2. Testing FINAL Mode (Deep, With Diarization) ---")
    print(f"Endpoint: {API_URL}")
    print("Params: diarization=true")
    
    start_time = time.time()
    try:
        with open(audio_path, "rb") as f:
            response = requests.post(
                API_URL,
                files={"file": f},
                data={
                    "model": "whisper-1", 
                    "response_format": "verbose_json",
                    "diarization": "true" 
                }
            )
            response.raise_for_status()
            data = response.json()
            
            elapsed = time.time() - start_time
            print(f"✅ Status: Success (Took {elapsed:.2f}s)")
            
            # Print FULL Text
            print(f"📝 Full Text:\n{data.get('text', '')}")
            
            # Print Speaker Segments (ALL)
            segments = data.get('segments', [])
            print(f"🗣️ Found {len(segments)} segments with speakers:")
            
            has_speaker = False
            for seg in segments: # NO LIMIT
                spk = seg.get('speaker', 'Unknown')
                if spk and spk != "UNKNOWN": has_speaker = True
                print(f"   [{spk}] {seg['start']:.2f}-{seg['end']:.2f}s: {seg['text']}")
            
            if has_speaker:
                print("✅ Verified: Speaker labels detected!")
            else:
                print("⚠️ Warning: No distinct speakers identified (might be short audio or one speaker).")

            
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Please provide path to audio file.")
        print("Usage: python test_modes.py <path_to_audio.wav>")
        sys.exit(1)
        
    target_file = sys.argv[1]
    
    if not os.path.exists(target_file):
        print(f"❌ Error: Audio file '{target_file}' not found.")
        sys.exit(1)
        
    print(f"Testing with file: {target_file}")
    
    # Run tests
    test_live_mode(target_file)
    test_final_mode(target_file)
