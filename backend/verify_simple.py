
import asyncio
import websockets

async def check_ws():
    uri = "ws://localhost:5167/ws/audio/test-123"
    print(f"Connecting to {uri}")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected successfully!")
            await websocket.close()
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(check_ws())
