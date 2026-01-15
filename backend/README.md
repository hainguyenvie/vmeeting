# Web Version Backend

Simple backend để test web version ngay.

## Quick Start

```bash
python main.py
```

Backend sẽ:
- Tạo database tự động (`meeting_minutes.db`)
- Start API server trên port 5167
- Enable CORS cho frontend

## Database

Database được tạo tự động tại `backend/meeting_minutes.db` khi lần đầu chạy.

Schema:
- `meetings` table - Meeting info
- `transcripts` table - Transcript segments

## API Endpoints

Xem docs tại: http://localhost:5167/docs
