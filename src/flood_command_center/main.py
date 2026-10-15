"""FastAPI entry point for the Flood Command Center."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from flood_command_center.config import get_settings
from flood_command_center.models import BroadcastRequest, BroadcastResponse, LiveStatus
from flood_command_center.service import FloodRiskService


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
        "dashboard": "http://localhost:8501",
    }


@app.get("/api/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "flood-command-center",
        "city": settings.city,
        "llm_mode": "openai-optional" if settings.llm_enabled else "deterministic-local",
        "data_mode": "live-configured" if settings.live_data_enabled else "fallback-configured",
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
