from config import Settings
from live_streams import LiveDataEngine
from mock_streams import MUMBAI_NODES, MockStreamEngine


def test_live_engine_has_explicit_offline_fallback_mode() -> None:
    engine = LiveDataEngine(Settings(live_data_enabled=False), MockStreamEngine(seed=3))
    snapshot = engine.snapshot()

    assert snapshot.data_mode == "fallback"
    assert len(snapshot.telemetry) == len(MUMBAI_NODES)
    assert all(source.status == "fallback" for source in snapshot.data_sources)


def test_live_telemetry_merge_preserves_provider_measurements() -> None:
    settings = Settings(live_data_enabled=True)
    engine = LiveDataEngine(settings, MockStreamEngine(seed=3))
    fallback, _ = engine.fallback_engine.snapshot()
    weather = [
        {"current": {"rain": 2.5, "precipitation": 2.5, "wind_speed_10m": 24}}
        for _ in fallback
    ]
    hydrology = [
        {
            "latitude": 19.07,
            "longitude": 72.88,
            "daily": {"river_discharge": [12.0, 15.0]},
        }
    ]

    merged = engine._merge_telemetry(fallback, weather, hydrology)

    assert merged[0].rainfall_mm_per_hour == 10.0
    assert merged[0].wind_speed_kmh == 24.0
    assert merged[0].river_discharge_m3_s == 12.0
    assert merged[0].gauge_trend == "rising"
    assert "open-meteo-flood-discharge-proxy" in merged[0].source
