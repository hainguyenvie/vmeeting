
import asyncio
import websockets
import requests
import uvicorn
from multiprocessing import Process
import time
import sys

# Define the URI
BASE_URI = "ws://localhost:5167"
HTTP_BASE_URI = "http://localhost:5167"
MEETING_ID = "test-meeting-id"

async def test_ws_connection(path):
    uri = f"{BASE_URI}{path}"
    print(f"Testing WebSocket connection to: {uri}")
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connection successful!")
            await websocket.close()
            return True
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"❌ Connection failed. Status code: {e.status_code}")
        return False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

def test_http_get(path):
    url = f"{HTTP_BASE_URI}{path}"
    print(f"Testing HTTP GET to: {url}")
    try:
        response = requests.get(url)
        print(f"Response status: {response.status_code}")
    except Exception as e:
        print(f"Request failed: {e}")

async def main():
    # 1. Normal Path
    print("\n--- Test 1: Normal Path ---")
    await test_ws_connection(f"/ws/audio/{MEETING_ID}")
    
    # 2. With Prefix /notion-meeting (Should fail currently as user reverted the fix)
    print("\n--- Test 2: With Prefix /notion-meeting ---")
    await test_ws_connection(f"/notion-meeting/ws/audio/{MEETING_ID}")
    
    # 3. HTTP Request (Simulate Nginx missing upgrade headers)
    print("\n--- Test 3: HTTP GET request (simulation of Nginx missing Upgrade header) ---")
    test_http_get(f"/ws/audio/{MEETING_ID}")
    
if __name__ == "__main__":
    asyncio.run(main())
