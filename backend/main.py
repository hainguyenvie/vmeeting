"""
FastAPI Backend for Web Version
Extends existing backend with web-specific endpoints
"""

from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import os
from pathlib import Path

# Initialize FastAPI app
app = FastAPI(
    title="Meeting Minutes Web API",
    description="Backend API for web version of Meeting Minutes",
    version="0.1.0"
)

# Configure CORS for web frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins for mobile access
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import routers
from app import audio, diarization, websocket_routes, meetings, transcripts

# Include routers
app.include_router(audio.router, prefix="/api/audio", tags=["Audio"])
app.include_router(diarization.router, prefix="/api/diarization", tags=["Diarization"])
app.include_router(websocket_routes.router, tags=["WebSocket"])
app.include_router(meetings.router, tags=["Meetings"])
app.include_router(transcripts.router, tags=["Transcripts"])

# Import here to avoid circular imports if any
from app import summary
app.include_router(summary.router, prefix="/api/summary", tags=["Summary"])

# Health check endpoint
@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Meeting Minutes Web API",
        "version": "0.1.0"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=5167,
        reload=True,
        log_level="info"
    )
