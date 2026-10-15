import asyncio

from fastapi.testclient import TestClient

from main import app, live_status


client = TestClient(app)


def test_root_explains_available_interfaces() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["docs"] == "/docs"
    assert response.json()["dashboard"] == "http://localhost:8501"


def test_health_and_latest_endpoints() -> None:
    health = client.get("/api/health")
    latest = client.get("/api/latest")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert latest.status_code == 200
    payload = latest.json()
    assert payload["city"] == "Mumbai"
    assert payload["dispatch"]["risk_score"] >= 1
    assert payload["vision"]["flooding_depth_cm"] > 0


def test_broadcast_is_accepted_as_simulation() -> None:
    response = client.post(
        "/api/broadcast",
        json={"sectors": ["Kurla", "Sion"], "message": "Move to higher ground."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["delivery_mode"] == "simulation"
    assert payload["recipient_sectors"] == ["Kurla", "Sion"]


def test_live_status_route_is_configured_for_sse() -> None:
    response = asyncio.run(live_status())

    assert response.media_type == "text/event-stream"
    assert response.headers["cache-control"] == "no-cache"


def test_cctv_upload_rejects_unsupported_files() -> None:
    response = client.post(
        "/api/cctv/upload",
        files={"file": ("notes.txt", b"not a video", "text/plain")},
    )

    assert response.status_code == 415
