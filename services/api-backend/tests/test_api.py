from fastapi.testclient import TestClient

from app import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer dev-token"}
TRIP = {
    "origin": {"lat": 13.7563, "lng": 100.5018},
    "destination": {"lat": 18.7883, "lng": 98.9853},
    "departure_time": "2030-01-01T01:00:00Z",
}


def test_no_token_is_unauthorized():
    res = client.get("/api/v1/trips")
    assert res.status_code == 401
    assert res.json() == {"data": None, "error": {"code": "UNAUTHORIZED", "message": res.json()["error"]["message"]}}


def test_time_without_timezone_is_rejected():
    res = client.post("/api/v1/trips", headers=AUTH, json={**TRIP, "departure_time": "2030-01-01T08:00"})
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_outside_thailand_is_rejected():
    res = client.post("/api/v1/trips", headers=AUTH, json={**TRIP, "origin": {"lat": 35.68, "lng": 139.76}})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "OUT_OF_THAILAND"


def test_upcoming_is_not_treated_as_trip_id():
    res = client.get("/api/v1/trips/upcoming", headers=AUTH)
    assert res.json()["error"] is None


def test_request_id_is_echoed():
    res = client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert res.headers["X-Request-ID"] == "abc-123"


def test_routing_down_is_upstream_error_not_crash(monkeypatch):
    monkeypatch.setenv("ROUTING_ENGINE_URL", "http://127.0.0.1:9")
    trip_id = client.post("/api/v1/trips", headers=AUTH, json=TRIP).json()["data"]["trip_id"]
    res = client.post(f"/api/v1/trips/{trip_id}/plan", headers=AUTH)
    assert res.status_code == 502
    assert res.json()["error"]["code"] == "UPSTREAM_ERROR"
