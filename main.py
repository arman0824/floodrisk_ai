"""FastAPI entry point for the Flood Command Center."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from config import get_settings
from models import BroadcastRequest, BroadcastResponse, LiveStatus
from service import FloodRiskService


settings = get_settings()
service = FloodRiskService(settings=settings)

app = FastAPI(
    title="Flood Command Center API",
    version="1.0.0",
    description="Streaming multi-agent flood risk and disaster dispatch prototype.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "flood-command-center",
        "status": "ok",
        "docs": "/docs",
        "health": "/api/health",
        "latest_status": "/api/latest",
        "live_stream": "/api/live-status",
        "cctv_upload": "/api/cctv/upload",
        "dashboard": "http://localhost:8501",
    }


@app.get("/api/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "flood-command-center",
        "city": settings.city,
        "llm_mode": "openai-optional" if settings.llm_enabled else "deterministic-local",
        "vision_mode": "yolov8n-optional" if settings.enable_yolo else "opencv-simulation",
    }


@app.get("/api/latest", response_model=LiveStatus)
async def latest_status() -> LiveStatus:
    return service.latest()


async def _sse_events() -> AsyncIterator[str]:
    async for status in service.stream():
        payload = json.dumps(status.model_dump(mode="json"), separators=(",", ":"))
        yield f"event: status\nid: {status.sequence}\ndata: {payload}\n\n"


@app.get("/api/live-status")
async def live_status() -> StreamingResponse:
    return StreamingResponse(
        _sse_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/broadcast", response_model=BroadcastResponse)
async def broadcast_alert(request: BroadcastRequest) -> BroadcastResponse:
    return service.broadcast(request)


@app.post("/api/cctv/upload")
async def upload_cctv(file: UploadFile = File(...)) -> dict[str, object]:
    filename = Path(file.filename or "cctv.mp4").name
    allowed_extensions = {".mp4", ".mov", ".avi", ".m4v", ".mkv"}
    if Path(filename).suffix.lower() not in allowed_extensions:
        raise HTTPException(status_code=415, detail="CCTV file must be mp4, mov, avi, m4v, or mkv")
    contents = await file.read()
    max_bytes = 500 * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(status_code=413, detail="CCTV file must be 500 MB or smaller")
    destination_dir = Path("runtime") / "cctv"
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / filename
    destination.write_bytes(contents)
    service.set_cctv_video_path(str(destination))
    return {
        "accepted": True,
        "filename": filename,
        "path": str(destination),
        "message": "CCTV clip loaded; the next live cycle will display a frame from this video.",
    }
