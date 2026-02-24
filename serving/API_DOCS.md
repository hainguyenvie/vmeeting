# Zipformer STT API Documentation

## Tổng quan
API Transcription sử dụng model Zipformer (ONNX) kết hợp 3D-Speaker (ERes2Net) để cung cấp dịch vụ chuyển đổi giọng nói thành văn bản (STT) và phân biệt người nói (Speaker Diarization).

**Base URL:** `http://localhost:2202` (hoặc IP của server)

**Encoding:** Tất cả request/response đều sử dụng UTF-8

---

## 1. OpenAI Compatible Endpoint (Khuyến nghị)

### `POST /v1/audio/transcriptions`

Endpoint tương thích với OpenAI Whisper API, hỗ trợ 2 chế độ:
- **Live Mode** (`diarization=false`): Transcription nhanh, không phân biệt người nói
- **Final Mode** (`diarization=true`): Transcription chất lượng cao với speaker labels

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file` | File | ✅ | - | File audio (mp3, wav, webm, m4a...) |
| `model` | String | ❌ | "whisper-1" | Tên model (ignored, luôn dùng Zipformer) |
| `response_format` | String | ❌ | "json" | Format trả về: `json`, `text`, `verbose_json` |
| `temperature` | Float | ❌ | 0.0 | Nhiệt độ sampling (không có tác dụng cho Zipformer) |
| `diarization` | String | ❌ | "false" | Bật Speaker Diarization: `"true"` hoặc `"false"` |
| `diarization_threshold` | Float | ❌ | 0.30 | Ngưỡng phân cụm người nói (0.0-1.0). Tăng lên nếu tạo quá nhiều speaker |
| `diarization_window_ms` | Integer | ❌ | 2000 | Độ dài cửa sổ quét (ms). Giảm xuống 1000-1500 nếu hội thoại nhanh |

#### Response Format

**`response_format=json`:**
```json
{
  "text": "CẢM ƠN MỌI NGƯỜI ĐÃ THAM GIA..."
}
```

**`response_format=verbose_json`:**
```json
{
  "task": "transcribe",
  "language": "english",
  "duration": 105.06,
  "text": "CẢM ƠN MỌI NGƯỜI...",
  "segments": [
    {
      "id": 0,
      "start": 0.04,
      "end": 7.30,
      "text": "CẢM ƠN MỌI NGƯỜI ĐÃ THAM GIA CUỘC HỌP NGÀY HÔM NAY",
      "speaker": "Speaker 1"  // Chỉ có khi diarization=true
    },
    {
      "id": 1,
      "start": 58.60,
      "end": 64.22,
      "text": "SAU KHI ĐÃ XEM QUA BẢN BÁO CÁO",
      "speaker": "Speaker 2"
    }
  ]
}
```

#### Request Examples

**cURL (Live Mode - Nhanh):**
```bash
curl -X POST http://localhost:2202/v1/audio/transcriptions \
  -F "file=@meeting.mp3" \
  -F "response_format=verbose_json" \
  -F "diarization=false"
```

**cURL (Final Mode - Có Speaker Labels):**
```bash
curl -X POST http://localhost:2202/v1/audio/transcriptions \
  -F "file=@meeting.mp3" \
  -F "response_format=verbose_json" \
  -F "diarization=true" \
  -F "diarization_threshold=0.35"
```

**JavaScript (Fetch API):**
```javascript
async function transcribeAudio(audioFile, withDiarization = false) {
  const formData = new FormData();
  formData.append('file', audioFile);
  formData.append('response_format', 'verbose_json');
  formData.append('diarization', withDiarization ? 'true' : 'false');
  
  if (withDiarization) {
    formData.append('diarization_threshold', '0.30');
    formData.append('diarization_window_ms', '2000');
  }

  const response = await fetch('http://localhost:2202/v1/audio/transcriptions', {
    method: 'POST',
    body: formData
  });

  return await response.json();
}

// Sử dụng
const audioFile = document.getElementById('audioInput').files[0];
const result = await transcribeAudio(audioFile, true);
console.log('Transcription:', result.text);
console.log('Segments:', result.segments);
```

**TypeScript (với Type Safety):**
```typescript
interface TranscriptionSegment {
  id: number;
  start: number;
  end: number;
  text: string;
  speaker?: string; // Chỉ có khi diarization=true
}

interface TranscriptionResponse {
  task: string;
  language: string;
  duration: number;
  text: string;
  segments: TranscriptionSegment[];
}

async function transcribeAudio(
  audioFile: File,
  options: {
    diarization?: boolean;
    threshold?: number;
    windowMs?: number;
  } = {}
): Promise<TranscriptionResponse> {
  const formData = new FormData();
  formData.append('file', audioFile);
  formData.append('response_format', 'verbose_json');
  formData.append('diarization', options.diarization ? 'true' : 'false');
  
  if (options.diarization) {
    formData.append('diarization_threshold', String(options.threshold ?? 0.30));
    formData.append('diarization_window_ms', String(options.windowMs ?? 2000));
  }

  const response = await fetch('http://localhost:2202/v1/audio/transcriptions', {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Transcription failed: ${response.statusText}`);
  }

  return await response.json();
}
```

**Python (Requests):**
```python
import requests

def transcribe_audio(file_path, diarization=False, threshold=0.30):
    url = "http://localhost:2202/v1/audio/transcriptions"
    
    with open(file_path, 'rb') as f:
        files = {'file': f}
        data = {
            'response_format': 'verbose_json',
            'diarization': 'true' if diarization else 'false',
        }
        
        if diarization:
            data['diarization_threshold'] = threshold
            data['diarization_window_ms'] = 2000
        
        response = requests.post(url, files=files, data=data)
        return response.json()

# Sử dụng
result = transcribe_audio('meeting.mp3', diarization=True)
print(f"Text: {result['text']}")
for seg in result['segments']:
    speaker = seg.get('speaker', 'Unknown')
    print(f"[{speaker}] {seg['start']:.2f}s: {seg['text']}")
```

---

## 2. Speaker Embedding Endpoint

### `POST /v1/audio/speaker_embedding`

Trích xuất vector đặc trưng giọng nói (speaker embedding) của một đoạn audio. Dùng để xây dựng hệ thống Voice Profile / Voice ID.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | File | ✅ | File audio chứa giọng nói cần trích xuất |

#### Response

```json
{
  "embedding": [0.123, -0.456, 0.789, ...], // Vector 192 chiều
  "dimension": 192,
  "model": "3dspeaker_eres2net_base"
}
```

#### Use Case

**So sánh độ tương đồng giọng nói:**
```python
import numpy as np
import requests

def get_speaker_embedding(audio_file):
    url = "http://localhost:2202/v1/audio/speaker_embedding"
    with open(audio_file, 'rb') as f:
        response = requests.post(url, files={'file': f})
    return np.array(response.json()['embedding'])

# Lấy embedding của 2 mẫu giọng
emb1 = get_speaker_embedding('speaker1_sample.wav')
emb2 = get_speaker_embedding('speaker2_sample.wav')

# Tính cosine similarity
similarity = np.dot(emb1, emb2)
print(f"Similarity: {similarity:.3f}")

# Nếu similarity > 0.45: Có thể là cùng người
# Nếu similarity < 0.30: Chắc chắn khác người
```

---

## 3. Legacy Inference Endpoint

### `POST /inference`

Endpoint legacy tương thích với phiên bản cũ. **Khuyến nghị dùng `/v1/audio/transcriptions` thay thế.**

#### Parameters

| Parameter | Type | Required | Default |
|-----------|------|----------|---------|
| `file` | File | ✅ | - |
| `diarize` | String | ❌ | "true" |
| `response_format` | String | ❌ | "json" |

#### Response

Tương tự `/v1/audio/transcriptions` nhưng luôn bật diarization nếu `diarize=true`.

---

## 4. Full Meeting Pipeline

### `POST /process_full_meeting`

Xử lý toàn bộ cuộc họp với pipeline Diarize-First đầy đủ. Tương đương với `/v1/audio/transcriptions` khi `diarization=true`.

#### Parameters

| Parameter | Type | Required |
|-----------|------|----------|
| `file` | File | ✅ |

#### Response

```json
{
  "status": "ok",
  "transcripts": [
    {
      "start": 0.04,
      "end": 7.30,
      "speaker": "Speaker 1",
      "text": "CẢM ƠN MỌI NGƯỜI ĐÃ THAM GIA..."
    },
    {
      "start": 58.60,
      "end": 64.22,
      "speaker": "Speaker 2",
      "text": "SAU KHI ĐÃ XEM QUA BẢN BÁO CÁO"
    }
  ]
}
```

---

## Error Handling

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad Request (file quá nhỏ, format không hợp lệ) |
| 500 | Internal Server Error |

### Error Response Format

```json
{
  "detail": "Audio too short or invalid for speaker extraction"
}
```

### Common Errors

1. **"Audio too short"**: File audio < 0.5s
2. **"Model not loaded"**: Server chưa load xong model (retry sau 5s)
3. **"Invalid audio format"**: Format không được hỗ trợ

---

## Best Practices

### 1. Chọn Mode phù hợp

| Tình huống | Mode | Lý do |
|-----------|------|-------|
| Live transcription (real-time) | `diarization=false` | Nhanh, độ trễ thấp |
| Final transcript (sau cuộc họp) | `diarization=true` | Chính xác cao, có speaker labels |
| Voice ID / Authentication | `/speaker_embedding` | Trả về vector để so sánh |

### 2. Tuning Parameters

**Nếu có quá nhiều speaker (Speaker 1, 2, 3, 4...):**
- Tăng `diarization_threshold` lên **0.35 - 0.45**

**Nếu gộp nhầm 2 người thành 1:**
- Giảm `diarization_threshold` xuống **0.20 - 0.25**

**Nếu hội thoại nhanh, nhiều ngắt lời:**
- Giảm `diarization_window_ms` xuống **1000 - 1500**

### 3. Performance

| Mode | Thời gian xử lý | RAM | CPU |
|------|----------------|-----|-----|
| Live Mode | ~0.3x realtime | ~2GB | 50% |
| Final Mode | ~1.5x realtime | ~3GB | 80% |

*(Với audio 1 phút, Live Mode mất ~18s, Final Mode mất ~90s)*

### 4. Retry Logic

```javascript
async function transcribeWithRetry(audioFile, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await transcribeAudio(audioFile, true);
    } catch (error) {
      if (i === maxRetries - 1) throw error;
      await new Promise(r => setTimeout(r, 2000 * (i + 1))); // Exponential backoff
    }
  }
}
```

---

## Integration Examples

### React Component

```tsx
import { useState } from 'react';

function TranscriptionUploader() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('response_format', 'verbose_json');
      formData.append('diarization', 'true');

      const response = await fetch('http://localhost:2202/v1/audio/transcriptions', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      setResult(data);
    } catch (error) {
      console.error('Transcription failed:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <input type="file" accept="audio/*" onChange={handleUpload} />
      {loading && <p>Đang xử lý...</p>}
      {result && (
        <div>
          <h3>Kết quả:</h3>
          <p>{result.text}</p>
          {result.segments.map((seg, i) => (
            <div key={i}>
              <strong>[{seg.speaker}]</strong> {seg.text}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

### WebSocket Streaming (Future Enhancement)

```javascript
// Hiện tại API chưa support streaming
// Để real-time transcription, gọi API với audio chunks nhỏ (5-10s)
async function streamingTranscribe(mediaRecorder) {
  mediaRecorder.ondataavailable = async (e) => {
    const audioBlob = e.data;
    const result = await transcribeAudio(audioBlob, false); // Live mode
    console.log('Partial result:', result.text);
  };
  
  mediaRecorder.start(5000); // Chunk mỗi 5 giây
}
```

---

## FAQ

**Q: API có giới hạn kích thước file không?**
A: Không có hard limit, nhưng khuyến nghị < 100MB (tương đương ~2 giờ audio). File lớn hơn nên chia nhỏ.

**Q: Làm sao biết model đã load xong?**
A: Gọi thử endpoint `/v1/audio/transcriptions` với file nhỏ. Nếu trả về 200 là model đã sẵn sàng.

**Q: Có cache kết quả không?**
A: Không. Mỗi request đều xử lý từ đầu. Frontend nên implement cache nếu cần.

**Q: API có rate limit không?**
A: Không. Nhưng do CPU-bound, tránh gửi quá 2-3 request đồng thời.

**Q: Hỗ trợ ngôn ngữ nào?**
A: Model Zipformer hỗ trợ chủ yếu tiếng Anh, tiếng Việt có thể chưa tối ưu. Kết quả tiếng Việt phụ thuộc vào data training.

---

## Changelog

**v1.0.0 (2026-01-19)**
- Initial release
- OpenAI compatible endpoint
- Speaker Diarization support
- Tunable parameters for clustering

---

## Support

Nếu gặp vấn đề, check log của Docker container:
```bash
docker logs zipformer_stt_hainh67
```
