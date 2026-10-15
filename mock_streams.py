"""Deterministic, realistic-enough telemetry and social feeds for the demo."""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator

from models import SocialPing, TelemetryUpdate


MUMBAI_NODES: tuple[dict[str, object], ...] = (
    {"node_id": "MUM-KUR", "location": "Kurla", "latitude": 19.0728, "longitude": 72.8826, "base": 1.25},
    {"node_id": "MUM-SIO", "location": "Sion", "latitude": 19.0460, "longitude": 72.8630, "base": 1.10},
    {"node_id": "MUM-DHA", "location": "Dharavi", "latitude": 19.0380, "longitude": 72.8538, "base": 1.18},
    {"node_id": "MUM-HIN", "location": "Hindmata", "latitude": 19.0183, "longitude": 72.8429, "base": 1.08},
    {"node_id": "MUM-WAD", "location": "Wadala", "latitude": 19.0178, "longitude": 72.8584, "base": 1.02},
    {"node_id": "MUM-PAR", "location": "Parel", "latitude": 18.9988, "longitude": 72.8435, "base": 0.98},
    {"node_id": "MUM-CHE", "location": "Chembur", "latitude": 19.0626, "longitude": 72.8946, "base": 1.04},
    {"node_id": "MUM-GHA", "location": "Ghatkopar", "latitude": 19.0790, "longitude": 72.9080, "base": 1.12},
    {"node_id": "MUM-VIK", "location": "Vikhroli", "latitude": 19.1111, "longitude": 72.9278, "base": 0.94},
    {"node_id": "MUM-BHA", "location": "Bhandup", "latitude": 19.1450, "longitude": 72.9370, "base": 1.00},
    {"node_id": "MUM-MUL", "location": "Mulund", "latitude": 19.1726, "longitude": 72.9425, "base": 0.82},
    {"node_id": "MUM-POW", "location": "Powai", "latitude": 19.1176, "longitude": 72.9060, "base": 0.88},
    {"node_id": "MUM-AND", "location": "Andheri East", "latitude": 19.1197, "longitude": 72.8468, "base": 0.95},
    {"node_id": "MUM-JOG", "location": "Jogeshwari East", "latitude": 19.1366, "longitude": 72.8538, "base": 0.91},
    {"node_id": "MUM-GOR", "location": "Goregaon East", "latitude": 19.1663, "longitude": 72.8526, "base": 0.86},
    {"node_id": "MUM-MAL", "location": "Malad West", "latitude": 19.1860, "longitude": 72.8480, "base": 0.84},
    {"node_id": "MUM-KAN", "location": "Kandivali East", "latitude": 19.2050, "longitude": 72.8730, "base": 0.78},
    {"node_id": "MUM-BOR", "location": "Borivali West", "latitude": 19.2307, "longitude": 72.8567, "base": 0.72},
    {"node_id": "MUM-SAN", "location": "Santacruz East", "latitude": 19.0818, "longitude": 72.8410, "base": 0.93},
    {"node_id": "MUM-VIL", "location": "Vile Parle East", "latitude": 19.0952, "longitude": 72.8498, "base": 0.83},
    {"node_id": "MUM-BAN", "location": "Bandra West", "latitude": 19.0607, "longitude": 72.8362, "base": 0.80},
    {"node_id": "MUM-GOV", "location": "Govandi", "latitude": 19.0550, "longitude": 72.9150, "base": 1.06},
    {"node_id": "MUM-MAN", "location": "Mankhurd", "latitude": 19.0486, "longitude": 72.9321, "base": 1.01},
)

_NUMBER_WORDS = ("one", "two", "three", "four", "five", "six", "seven", "eight")


class MockStreamEngine:
    """Produce repeatable updates while still varying every live cycle."""

    def __init__(self, seed: int = 42, city: str = "Mumbai") -> None:
        self._rng = random.Random(seed)
        self.city = city
        self.cycle = 0

    def _timestamp(self) -> datetime:
        # A stable relative clock makes serialized fixtures easy to inspect.
        return datetime.now(timezone.utc).replace(microsecond=0)

    def telemetry_snapshot(self) -> list[TelemetryUpdate]:
        self.cycle += 1
        timestamp = self._timestamp()
        updates: list[TelemetryUpdate] = []
        for index, node in enumerate(MUMBAI_NODES):
            baseline = float(node["base"])
            # The first two nodes are deliberately more exposed to show the
            # escalation path during a short demo.
            storm_bias = 18 if str(node["location"]) in {"Kurla", "Sion", "Dharavi", "Hindmata"} else 7
            rainfall = max(0.0, 28 + storm_bias + self._rng.uniform(-12, 38))
            gauge = max(0.2, baseline + rainfall / 120 + self._rng.uniform(0.10, 0.75))
            wind = max(4.0, 12 + self._rng.uniform(-3, 22))
            trend = "rising" if gauge >= baseline + 0.6 else ("steady" if gauge >= baseline + 0.3 else "falling")
            updates.append(
                TelemetryUpdate(
                    node_id=str(node["node_id"]),
                    location=str(node["location"]),
                    city=self.city,
                    coordinates={"latitude": float(node["latitude"]), "longitude": float(node["longitude"])},
                    timestamp=timestamp,
                    rainfall_mm_per_hour=round(rainfall, 1),
                    river_gauge_height_m=round(gauge, 2),
                    gauge_trend=trend,
                    wind_speed_kmh=round(wind, 1),
                )
            )
        return updates

    def social_snapshot(self, telemetry: list[TelemetryUpdate]) -> list[SocialPing]:
        timestamp = self._timestamp()
        ranked = sorted(telemetry, key=lambda item: item.river_gauge_height_m, reverse=True)
        selected = ranked[: self._rng.randint(3, 5)]
        templates = (
            "SOS near {location}: {count} people stranded beside the flooded underpass, need rescue boats now.",
            "Water rising fast at {location}; {count} residents trapped in ground-floor homes. Please send help.",
            "Road blocked around {location}. Families reporting waist-deep water and no power.",
            "Emergency crews requested in {location}; children and elderly citizens need evacuation.",
            "Update from {location}: water is receding slowly, but commuters remain stranded.",
        )
        pings: list[SocialPing] = []
        for index, telemetry_item in enumerate(selected):
            count = self._rng.randint(2, 8)
            text = self._rng.choice(templates).format(location=telemetry_item.location, count=count)
            if index == 0 and self.cycle % 2 == 0:
                text = f"CRITICAL {text}"
            pings.append(
                SocialPing(
                    ping_id=f"SOS-{self.cycle:04d}-{index + 1}",
                    text=text,
                    timestamp=timestamp - timedelta(seconds=index * 17),
                )
            )
        return pings

    def snapshot(self) -> tuple[list[TelemetryUpdate], list[SocialPing]]:
        telemetry = self.telemetry_snapshot()
        return telemetry, self.social_snapshot(telemetry)

    async def stream(self, interval_seconds: float = 5.0) -> AsyncIterator[tuple[list[TelemetryUpdate], list[SocialPing]]]:
        while True:
            yield self.snapshot()
            await asyncio.sleep(max(0.1, interval_seconds))


def create_demo_snapshot(seed: int = 42) -> tuple[list[TelemetryUpdate], list[SocialPing]]:
    """Convenience function used by tests and the dashboard fallback."""

    return MockStreamEngine(seed=seed).snapshot()
