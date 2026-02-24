# Meetily AI Model Serving

This directory contains the configuration to deploy the generic Speech-to-Text service as a Docker container.

## Features
- **OpenAI Compatible API**: Drop-in replacement for OpenAI Whisper API (`/v1/audio/transcriptions`).
- **GPU/CPU Support**: Uses Sherpa-ONNX which is optimized for both.
- **Easy Deployment**: Standard `docker-compose` setup.

## Prerequisites
1.  **Docker & Docker Compose** installed.
2.  **Models**: You MUST download the models and place them in a `models` folder inside this directory.

   Structure:
   ```text
   serving/
   ├── models/
   │   ├── zipformer/
   │       ├── encoder-*.onnx
   │       ├── decoder-*.onnx
   │       ├── joiner-*.onnx
   │       └── tokens.txt  <-- IMPORTANT: Copy this from the serving package if missing on server
   │   └── speaker/
   │       └── *.onnx
   ├── docker-compose.yml
   └── tokens.txt (Backup copy provided here)
   └── ...
   ```

## Quick Start

1.  Navigate to this directory:
    ```bash
    cd serving
    ```

2.  Ensure your `models` folder is populated (see Prerequisites).

3.  Build and start the service:
    ```bash
    docker-compose up -d --build
    ```

3.  The service will be available at `http://localhost:2202`.

## API Usage

### OpenAI Compatible Endpoint
`POST /v1/audio/transcriptions`

**Example (Curl):**
```bash
curl http://localhost:2202/v1/audio/transcriptions \
  -F "file=@/path/to/audio.wav" \
  -F "model=whisper-1"
```

**Example (Python OpenAI SDK):**
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:2202/v1",
    api_key="not-needed"
)

audio_file = open("audio.wav", "rb")
transcript = client.audio.transcriptions.create(
  model="whisper-1", 
  file=audio_file,
  response_format="text"
)
print(transcript)
```
