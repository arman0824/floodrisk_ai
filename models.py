"""Validated contracts shared by the mock streams, agents, API, and UI."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


RiskLevel = Literal["Low", "Medium", "High", "Critical"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Coordinate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class TelemetryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(min_length=1)
    location: str = Field(min_length=1)
    city: str = Field(min_length=1)
    coordinates: Coordinate
    timestamp: datetime = Field(default_factory=utc_now)
    rainfall_mm_per_hour: float = Field(ge=0, le=500)
    river_gauge_height_m: float = Field(ge=0, le=20)
    gauge_trend: Literal["rising", "steady", "falling"]
    wind_speed_kmh: float = Field(ge=0, le=250)
    source: str = "mock-weather-gauge"


class SocialPing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ping_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    timestamp: datetime = Field(default_factory=utc_now)
    source: str = "simulated-social-feed"


class TelemetryAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    normalized_score: int = Field(ge=0, le=100)
    node_scores: dict[str, int] = Field(default_factory=dict)
    affected_locations: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    recommended_monitoring: list[str] = Field(default_factory=list)


class SocialAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    normalized_score: int = Field(ge=0, le=100)
    locations: list[str] = Field(default_factory=list)
    stranded_citizens: int = Field(ge=0)
    maximum_severity: RiskLevel
    sentiment: Literal["negative", "mixed", "neutral"]
    severity_by_location: dict[str, str] = Field(default_factory=dict)
    findings: list[str] = Field(default_factory=list)


class DetectedObject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    confidence: float = Field(ge=0, le=1)
    flooded: bool = False
    box: list[int] = Field(min_length=4, max_length=4)


class VisionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flooding_depth_cm: int = Field(ge=0, le=500)
    waterline_px: int = Field(ge=0)
    water_mask_ratio: float = Field(ge=0, le=1)
    detected_objects: list[DetectedObject] = Field(default_factory=list)
    annotated_frame_base64: str = Field(min_length=1)
    frame_width: int = Field(gt=0)
    frame_height: int = Field(gt=0)
    detector_mode: Literal["opencv-simulation", "yolov8n"]
    source: str = "mock-cctv"


class ResourcePriority(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rank: int = Field(gt=0)
    resource: str
    destination: str
    reason: str
    eta_minutes: int = Field(ge=1)


class DispatchSynthesis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_score: int = Field(ge=1, le=100)
    risk_level: RiskLevel
    headline: str
    rationale: str
    evacuation_zones: list[str] = Field(default_factory=list)
    affected_sectors: list[str] = Field(default_factory=list)
    resource_priority: list[ResourcePriority] = Field(default_factory=list)
    emergency_sms: str = Field(min_length=1, max_length=320)
    recommended_actions: list[str] = Field(default_factory=list)
    score_breakdown: dict[str, int] = Field(default_factory=dict)


class AgentTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime = Field(default_factory=utc_now)
    agent: Literal["Telemetry Agent", "Social Listening Agent", "Dispatch Synthesizer"]
    event_type: Literal["observation", "analysis", "handoff", "decision"]
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)


class LiveStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=0)
    generated_at: datetime = Field(default_factory=utc_now)
    city: str
    telemetry: list[TelemetryUpdate]
    social_pings: list[SocialPing]
    telemetry_analysis: TelemetryAnalysis
    social_analysis: SocialAnalysis
    vision: VisionResult
    dispatch: DispatchSynthesis
    traces: list[AgentTrace]


class BroadcastRequest(BaseModel):
    sectors: list[str] = Field(min_length=1)
    message: str = Field(min_length=1, max_length=320)


class BroadcastResponse(BaseModel):
    accepted: bool
    broadcast_id: str
    recipient_sectors: list[str]
    delivery_mode: Literal["simulation"] = "simulation"
    message: str
    created_at: datetime = Field(default_factory=utc_now)
