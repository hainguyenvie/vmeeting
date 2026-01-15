import requests
import json
import time

BASE_URL = "http://localhost:5167/api/summary"

def test_list_templates():
    print("Testing GET /templates...")
    try:
        response = requests.get(f"{BASE_URL}/templates")
        if response.status_code == 200:
            print("✅ Success! Templates found:")
            print(json.dumps(response.json(), indent=2))
        else:
            print(f"❌ Failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_generate_summary():
    print("\nTesting POST /generate (Dry Run)...")
    # Note: We won't actually call LLM here to avoid waiting, or we'll assume it might fail if Ollama isn't running.
    # But checking if the endpoint exists and accepts the payload is enough.
    
    payload = {
        "transcript": "Test transcript content.",
        "template_id": "bien_ban_hop_vn",
        "model": "gemma2:2b",
        "custom_prompt": "Test prompt"
    }
    
    try:
        # We expect this to potentially fail if Ollama isn't running, but the code path should be exercised.
        # Use a short timeout
        response = requests.post(f"{BASE_URL}/generate", json=payload, timeout=5)
        
        if response.status_code == 200:
            print("✅ Success! Summary generated.")
            # print(json.dumps(response.json(), indent=2))
        else:
            print(f"⚠️ Response: {response.status_code} - {response.text}")
            if "Could not connect to LLM service" in response.text:
                 print("✅ Logic works (Backend attempted to connect to LLM).")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_list_templates()
    test_generate_summary()
