"""Live public-data adapters with explicit provider health and safe fallback.

Providers used by default:

* Open-Meteo forecast: current precipitation and wind for each Mumbai node.
* Open-Meteo Flood API: modeled river discharge, exposed as a clearly labeled
  hydrology level proxy because Mumbai does not provide a single free public
  gauge-height API suitable for this prototype.
* Google News RSS: live public incident reports matching the configured query.

The adapters are intentionally synchronous because the service creates one
atomic snapshot per cycle. Network failures never stop the demo: each provider
falls back independently and its status is included in the API payload.
"""

from __future__ import annotations

import hashlib
import html
import math
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from config import Settings
from mock_streams import MUMBAI_NODES, MockStreamEngine
from models import DataSourceStatus, SocialPing, TelemetryUpdate


WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
FLOOD_URL = "https://flood-api.open-meteo.com/v1/flood"
NEWS_RSS_URL = "https://news.google.com/rss/search"


@dataclass
class LiveSnapshot:
    telemetry: list[TelemetryUpdate]
    social_pings: list[SocialPing]
    data_sources: list[DataSourceStatus]
    data_mode: str


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def _nearest_hydrology(items: list[dict[str, Any]], latitude: float, longitude: float) -> dict[str, Any] | None:
    if not items:
        return None
    return min(
        items,
        key=lambda item: (_as_float(item.get("latitude")) - latitude) ** 2 + (_as_float(item.get("longitude")) - longitude) ** 2,
    )


class LiveDataEngine:
    def __init__(self, settings: Settings, fallback_engine: MockStreamEngine | None = None) -> None:
        self.settings = settings
        self.fallback_engine = fallback_engine or MockStreamEngine(city=settings.city)

    def snapshot(self) -> LiveSnapshot:
        if not self.settings.live_data_enabled:
            telemetry, social = self.fallback_engine.snapshot()
            return LiveSnapshot(
                telemetry=telemetry,
                social_pings=social,
                data_sources=[
                    DataSourceStatus(name="Local deterministic stream", kind="weather", status="fallback", detail="LIVE_DATA_ENABLED=false"),
                    DataSourceStatus(name="Local deterministic hydrology stream", kind="hydrology", status="fallback", detail="LIVE_DATA_ENABLED=false"),
                    DataSourceStatus(name="Local deterministic incident stream", kind="social", status="fallback", detail="LIVE_DATA_ENABLED=false"),
                ],
                data_mode="fallback",
            )

        fallback_telemetry = self.fallback_engine.telemetry_snapshot()
        sources: list[DataSourceStatus] = []
        try:
            weather, weather_status = self._fetch_weather()
            sources.append(weather_status)
        except Exception as exc:
            weather = None
            sources.append(self._failure_status("Open-Meteo weather", "weather", exc))
        try:
            hydrology, hydro_status = self._fetch_hydrology()
            sources.append(hydro_status)
        except Exception as exc:
            hydrology = None
            sources.append(self._failure_status("Open-Meteo Flood API", "hydrology", exc))
        telemetry = self._merge_telemetry(fallback_telemetry, weather, hydrology)
        try:
            social, social_status = self._fetch_social()
            sources.append(social_status)
        except Exception as exc:
            social = self.fallback_engine.social_snapshot(fallback_telemetry)
            sources.append(self._failure_status("Google News RSS", "social", exc))
        live_count = sum(item.status == "live" for item in sources)
        fallback_count = sum(item.status == "fallback" for item in sources)
        mode = "live" if live_count == len(sources) else ("mixed" if live_count else "fallback")
        if fallback_count and live_count:
            mode = "mixed"
        return LiveSnapshot(telemetry=telemetry, social_pings=social, data_sources=sources, data_mode=mode)

    def _request_json(self, url: str, params: dict[str, Any]) -> tuple[Any, int]:
        started = time.perf_counter()
        with httpx.Client(timeout=self.settings.live_data_timeout_seconds, headers={"User-Agent": "FloodCommandCenter/1.0"}) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
        return payload, int((time.perf_counter() - started) * 1000)

    def _fetch_weather(self) -> tuple[list[dict[str, Any]], DataSourceStatus]:
        params = {
            "latitude": ",".join(str(node["latitude"]) for node in MUMBAI_NODES),
            "longitude": ",".join(str(node["longitude"]) for node in MUMBAI_NODES),
            "current": "precipitation,rain,wind_speed_10m",
            "timezone": "UTC",
        }
        payload, latency = self._request_json(WEATHER_URL, params)
        items = _items(payload)
        if len(items) < len(MUMBAI_NODES):
            raise ValueError(f"weather provider returned {len(items)} nodes; expected {len(MUMBAI_NODES)}")
        return items, DataSourceStatus(name="Open-Meteo weather", kind="weather", status="live", detail="Current precipitation and wind", latency_ms=latency)

    def _fetch_hydrology(self) -> tuple[list[dict[str, Any]], DataSourceStatus]:
        params = {
            "latitude": ",".join(str(node["latitude"]) for node in MUMBAI_NODES),
            "longitude": ",".join(str(node["longitude"]) for node in MUMBAI_NODES),
            "daily": "river_discharge",
            "forecast_days": 2,
            "timezone": "UTC",
        }
        payload, latency = self._request_json(FLOOD_URL, params)
        items = _items(payload)
        if not items or not any(item.get("daily", {}).get("river_discharge") for item in items):
            raise ValueError("flood provider returned no river-discharge series")
        return items, DataSourceStatus(name="Open-Meteo Flood API", kind="hydrology", status="live", detail="Modeled river discharge; converted to a transparent level proxy", latency_ms=latency)

    def _merge_telemetry(
        self,
        fallback: list[TelemetryUpdate],
        weather: list[dict[str, Any]] | None,
        hydrology: list[dict[str, Any]] | None,
    ) -> list[TelemetryUpdate]:
        updates: list[TelemetryUpdate] = []
        timestamp = _now()
        for index, node in enumerate(MUMBAI_NODES):
            fallback_item = fallback[index]
            weather_item = weather[index] if weather and index < len(weather) else {}
            current = weather_item.get("current", {}) if isinstance(weather_item, dict) else {}
            rainfall_15m = max(_as_float(current.get("rain")), _as_float(current.get("precipitation")))
            rainfall_hourly = round(rainfall_15m * 4, 1)
            wind = round(_as_float(current.get("wind_speed_10m"), fallback_item.wind_speed_kmh), 1)
            hydro_item = _nearest_hydrology(hydrology or [], float(node["latitude"]), float(node["longitude"]))
            discharge_values = []
            if hydro_item:
                discharge_values = hydro_item.get("daily", {}).get("river_discharge", []) or []
            discharge = _as_float(discharge_values[0]) if discharge_values else None
            next_discharge = _as_float(discharge_values[1]) if len(discharge_values) > 1 else discharge
            trend = "rising" if discharge is not None and next_discharge > discharge * 1.05 else (
                "falling" if discharge is not None and next_discharge < discharge * 0.95 else fallback_item.gauge_trend
            )
            # The public flood endpoint supplies discharge rather than gauge
            # height. Keep the actual discharge and clearly mark this derived
            # level as a proxy so operators do not mistake it for a gauge.
            proxy_height = max(0.2, min(20.0, 0.55 + math.log1p(discharge or 0) * 0.68))
            source_parts = []
            if weather_item:
                source_parts.append("open-meteo-weather")
            if discharge is not None:
                source_parts.append("open-meteo-flood-discharge-proxy")
            source = " + ".join(source_parts) or fallback_item.source
            updates.append(
                TelemetryUpdate(
                    node_id=str(node["node_id"]),
                    location=str(node["location"]),
                    city=self.settings.city,
                    coordinates={"latitude": float(node["latitude"]), "longitude": float(node["longitude"])},
                    timestamp=timestamp,
                    rainfall_mm_per_hour=rainfall_hourly if weather_item else fallback_item.rainfall_mm_per_hour,
                    river_gauge_height_m=round(proxy_height if discharge is not None else fallback_item.river_gauge_height_m, 2),
                    river_discharge_m3_s=round(discharge, 2) if discharge is not None else None,
                    gauge_trend=trend,
                    wind_speed_kmh=wind if weather_item else fallback_item.wind_speed_kmh,
                    source=source,
                )
            )
        return updates

    def _fetch_social(self) -> tuple[list[SocialPing], DataSourceStatus]:
        started = time.perf_counter()
        with httpx.Client(timeout=self.settings.live_data_timeout_seconds, headers={"User-Agent": "FloodCommandCenter/1.0"}) as client:
            response = client.get(
                NEWS_RSS_URL,
                params={"q": self.settings.social_feed_query, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"},
            )
            response.raise_for_status()
        root = ET.fromstring(response.content)
        pings: list[SocialPing] = []
        for item in root.findall("./channel/item")[:5]:
            raw_title = item.findtext("title", default="").strip()
            title = re.sub(r"\s+", " ", html.unescape(raw_title))
            if not title:
                continue
            pub_date = item.findtext("pubDate", default="")
            try:
                published = parsedate_to_datetime(pub_date).astimezone(timezone.utc)
            except (TypeError, ValueError, OverflowError):
                published = _now()
            digest = hashlib.sha1(f"{title}:{pub_date}".encode("utf-8")).hexdigest()[:12]
            pings.append(SocialPing(ping_id=f"NEWS-{digest}", text=title, timestamp=published, source="google-news-rss-live"))
        if not pings:
            raise ValueError("news RSS returned no incident items")
        latency = int((time.perf_counter() - started) * 1000)
        return pings, DataSourceStatus(name="Google News RSS", kind="social", status="live", detail=f"Live public incident query: {self.settings.social_feed_query}", latency_ms=latency)

    @staticmethod
    def _failure_status(name: str, kind: str, error: Exception) -> DataSourceStatus:
        detail = str(error).replace("\n", " ")[:180]
        return DataSourceStatus(name=name, kind=kind, status="fallback", detail=f"Provider unavailable; deterministic fallback active: {detail}")
