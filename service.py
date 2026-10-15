"""Application service that turns each mock cycle into one complete status."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from threading import Lock

from agents import build_graph, run_pipeline, trace_for_state
from config import Settings, get_settings
from live_streams import LiveDataEngine
from mock_streams import MockStreamEngine
from models import (
    BroadcastRequest,
    BroadcastResponse,
    LiveStatus,
    VisionResult,
    utc_now,
)
from vision_processor import analyze_frame


class FloodRiskService:
    def __init__(self, settings: Settings | None = None, engine: MockStreamEngine | None = None) -> None:
        self.settings = settings or get_settings()
        self.engine = engine or MockStreamEngine(city=self.settings.city)
        self.live_data = LiveDataEngine(self.settings, fallback_engine=self.engine)
        self.graph = build_graph()
        self._latest: LiveStatus | None = None
        self._sequence = 0
        self._lock = Lock()

    def refresh(self) -> LiveStatus:
        """Create one atomic snapshot for both the API and dashboard."""

        with self._lock:
            live_snapshot = self.live_data.snapshot()
            telemetry, pings = live_snapshot.telemetry, live_snapshot.social_pings
            vision: VisionResult = analyze_frame(
                cycle=self._sequence,
                use_yolo=self.settings.enable_yolo,
                model_path=self.settings.yolo_model_path,
            )
            state = run_pipeline(telemetry, pings, vision=vision, graph=self.graph)
            self._sequence += 1
            status = LiveStatus(
                sequence=self._sequence,
                generated_at=utc_now(),
                city=self.settings.city,
                data_mode=live_snapshot.data_mode,
                data_sources=live_snapshot.data_sources,
                telemetry=telemetry,
                social_pings=pings,
                telemetry_analysis=state["telemetry_analysis"],
                social_analysis=state["social_analysis"],
                vision=state["vision_result"],
                dispatch=state["dispatch_output"],
                traces=trace_for_state(state),
            )
            self._latest = status
            return status

    def latest(self) -> LiveStatus:
        if self._latest is None:
            return self.refresh()
        age_seconds = (utc_now() - self._latest.generated_at).total_seconds()
        if age_seconds >= max(0.1, self.settings.stream_interval_seconds):
            return self.refresh()
        return self._latest

    async def stream(self) -> AsyncIterator[LiveStatus]:
        """Yield an immediate snapshot followed by five-second live updates."""

        yield self.latest()
        while True:
            await asyncio.sleep(max(0.1, self.settings.stream_interval_seconds))
            yield self.refresh()

    def broadcast(self, request: BroadcastRequest) -> BroadcastResponse:
        # This intentionally models an accepted dispatch without contacting a
        # real carrier. It leaves a stable integration seam for Twilio/SNS.
        return BroadcastResponse(
            accepted=True,
            broadcast_id=f"mock-broadcast-{self.latest().sequence:04d}",
            recipient_sectors=request.sectors,
            message=request.message,
        )
