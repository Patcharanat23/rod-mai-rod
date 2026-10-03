"""ตรวจก่อนขึ้น Render: ทริปย้อนหลัง / ต้นทางซ้ำปลายทาง / กรอบพิกัด / จำกัดจำนวนครั้ง / endpoint ใหม่ของหน้าเว็บ"""
from datetime import datetime, timedelta, timezone

from test_api import TRIP, bare, new_user_header


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_trip_in_the_past_is_rejected_but_just_departed_is_fine(client, auth_header):
    now = datetime.now(timezone.utc)
    res = client.post("/api/v1/trips", headers=auth_header, json={**TRIP, "departure_time": iso(now - timedelta(days=2))})
    assert res.status_code == 400 and "ผ่านไปแล้ว" in res.json()["error"]["message"]
    res = client.post("/api/v1/trips", headers=auth_header, json={**TRIP, "departure_time": iso(now - timedelta(minutes=30))})
    assert res.status_code == 200


def test_same_origin_and_destination_is_rejected_unless_there_are_stops(client, auth_header):
    same = {**TRIP, "destination": {"lat": 13.757, "lng": 100.502}}
    res = client.post("/api/v1/trips", headers=auth_header, json=same)
    assert res.json()["error"]["message"] == "ต้นทางกับปลายทางเป็นที่เดียวกัน"
    loop = {**same, "waypoints": [{"lat": 14.35, "lng": 100.57}]}  # วนกลับที่เดิมได้ถ้ามีจุดแวะ
    assert client.post("/api/v1/trips", headers=auth_header, json=loop).status_code == 200
    trip_id = client.post("/api/v1/trips", headers=auth_header, json=TRIP).json()["data"]["trip_id"]
    res = client.patch(f"/api/v1/trips/{trip_id}", headers=auth_header, json={"destination": TRIP["origin"]})
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_wrong_short_password_is_just_wrong_credentials(client):
    res = client.post("/api/v1/auth/login", json={"email": "demo@example.com", "password": "abc"})
    assert res.status_code == 401 and res.json()["error"]["message"] == "อีเมลหรือรหัสผ่านไม่ถูกต้อง"


def test_login_is_rate_limited_per_ip(client):
    for _ in range(10):
        client.post("/api/v1/auth/login", json={"email": "demo@example.com", "password": "wrong-pass"})
    res = client.post("/api/v1/auth/login", json={"email": "demo@example.com", "password": "demo1234"})
    assert res.status_code == 429 and res.json()["error"]["code"] == "RATE_LIMITED"
    other = client.post("/api/v1/auth/login", headers={"X-Forwarded-For": "203.0.113.9"},
                        json={"email": "demo@example.com", "password": "demo1234"})
    assert other.status_code == 200


def test_chat_is_rate_limited_per_user(client, monkeypatch):
    monkeypatch.setattr("app.call", lambda *a, **k: {"reply": "ok", "actions": [], "warnings": []})
    h = new_user_header(client)
    codes = [client.post("/api/v1/assistant/chat", headers=h, json={"message": "สวัสดี"}).status_code for _ in range(11)]
    assert codes[:10] == [200] * 10 and codes[10] == 429


def test_inverted_hazard_box_is_a_validation_error(client, auth_header, monkeypatch):
    monkeypatch.setattr("app.call", lambda *a, **k: {"hazards": [], "warnings": []})
    res = client.get("/api/v1/hazards", headers=auth_header, params={"min_lat": 20, "min_lng": 105, "max_lat": 5, "max_lng": 97})
    assert res.status_code == 400 and res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_departures_asks_routing_for_plus_3_and_plus_6_hours(client, auth_header, monkeypatch):
    trip_id = client.post("/api/v1/trips", headers=auth_header, json=TRIP).json()["data"]["trip_id"]
    asked = []

    def fake_call(url_env, method, path, **kw):
        asked.append(kw["json"]["departure_time"])
        if kw["json"]["departure_time"].startswith("2030-01-01T07"):
            raise __import__("envelope").ApiError("UPSTREAM_TIMEOUT", "ช้า")  # +6 ชม. พัง ต้องข้ามไป
        return {"risk_level": "LOW", "risk_score": 12, "recommendation": "NORMAL", "route_options": []}

    monkeypatch.setattr("app.call", fake_call)
    data = client.get(f"/api/v1/trips/{trip_id}/departures", headers=auth_header).json()["data"]
    assert sorted(asked) == ["2030-01-01T04:00:00Z", "2030-01-01T07:00:00Z"]
    assert data == {"departures": [{"offset_h": 3, "risk_level": "LOW", "risk_score": 12, "recommendation": "NORMAL"}]}
    assert bare.get(f"/api/v1/trips/{trip_id}/departures").status_code == 401


def test_route_forecast_samples_every_15_km_at_pass_time(client, auth_header, monkeypatch):
    sent = {}

    def fake_call(url_env, method, path, **kw):
        sent.update(url_env=url_env, path=path, points=kw["json"]["points"])
        return {"points": [{**p, "forecast": None} for p in kw["json"]["points"]], "warnings": []}

    monkeypatch.setattr("app.call", fake_call)
    line = [{"lat": 13.0 + i * 0.1, "lng": 100.0} for i in range(5)]  # ~44 กม.
    res = client.post("/api/v1/forecast/route", headers=auth_header,
                      json={"geometry": line, "departure_time": "2030-01-01T01:20:00Z", "duration_min": 120})
    pts = sent["points"]
    assert res.status_code == 200 and sent["path"] == "/api/v1/forecast/points"
    assert len(pts) == 3 and pts[0]["time"] == "2030-01-01T01:00:00Z" and pts[-1]["time"] == "2030-01-01T02:00:00Z"
    assert len(res.json()["data"]["points"]) == 3
    started = client.post("/api/v1/forecast/route", headers=auth_header,  # ทริปที่ออกไปแล้วยังดูได้
                          json={"geometry": line, "departure_time": iso(datetime.now(timezone.utc) - timedelta(hours=3)), "duration_min": 600})
    assert started.status_code == 200
    bad = client.post("/api/v1/forecast/route", headers=auth_header,
                      json={"geometry": line[:1], "departure_time": "2030-01-01T01:00:00Z", "duration_min": 10})
    assert bad.status_code == 400
