import uuid

from fastapi.testclient import TestClient

from app import app

# ไม่รัน lifespan ใช้กับเทสต์ที่ไม่ต้องแตะฐานข้อมูล
bare = TestClient(app)
TRIP = {
    "origin": {"lat": 13.7563, "lng": 100.5018},
    "destination": {"lat": 18.7883, "lng": 98.9853},
    "departure_time": "2030-01-01T01:00:00Z",
}


def test_no_token_is_unauthorized():
    res = bare.get("/api/v1/trips")
    assert res.status_code == 401
    assert res.json() == {"data": None, "error": {"code": "UNAUTHORIZED", "message": res.json()["error"]["message"]}}


def test_request_id_is_echoed():
    res = bare.get("/health", headers={"X-Request-ID": "abc-123"})
    assert res.headers["X-Request-ID"] == "abc-123"


def test_time_without_timezone_is_rejected(client, auth_header):
    res = client.post("/api/v1/trips", headers=auth_header, json={**TRIP, "departure_time": "2030-01-01T08:00"})
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_outside_thailand_is_rejected(client, auth_header):
    res = client.post("/api/v1/trips", headers=auth_header, json={**TRIP, "origin": {"lat": 35.68, "lng": 139.76}})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "OUT_OF_THAILAND"


def test_upcoming_is_not_treated_as_trip_id(client, auth_header):
    res = client.get("/api/v1/trips/upcoming", headers=auth_header)
    assert res.json()["error"] is None


def test_routing_down_is_upstream_error_not_crash(client, auth_header, monkeypatch):
    monkeypatch.setenv("ROUTING_ENGINE_URL", "http://127.0.0.1:9")
    trip_id = client.post("/api/v1/trips", headers=auth_header, json=TRIP).json()["data"]["trip_id"]
    res = client.post(f"/api/v1/trips/{trip_id}/plan", headers=auth_header)
    assert res.status_code == 502
    assert res.json()["error"]["code"] == "UPSTREAM_ERROR"


# ---------- auth ----------

def test_register_then_login_without_password_hash(client):
    email = f"user-{uuid.uuid4()}@example.com"
    reg = client.post("/api/v1/auth/register", json={"email": email, "password": "secret123"})
    assert reg.json()["error"] is None
    assert "password_hash" not in reg.text
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert res.json()["data"]["user"] == reg.json()["data"]
    assert "password_hash" not in res.text
    me = client.get("/api/v1/me", headers={"Authorization": f"Bearer {res.json()['data']['token']}"})
    assert me.json()["data"] == reg.json()["data"]


def test_duplicate_email_is_validation_error(client):
    res = client.post("/api/v1/auth/register", json={"email": "demo@example.com", "password": "whatever1"})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_wrong_password_is_unauthorized(client):
    res = client.post("/api/v1/auth/login", json={"email": "demo@example.com", "password": "wrong-pass"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


def test_fake_token_is_unauthorized(client):
    res = client.get("/api/v1/me", headers={"Authorization": "Bearer dev-token"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"