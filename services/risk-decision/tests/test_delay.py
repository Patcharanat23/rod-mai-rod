"""7.4 (เสริม): DELAY แบบ end-to-end ผ่าน /api/v1/risk/evaluate จริง

เส้นทางเดียว (ไม่มีทางเลือกให้ REROUTE) เจอฝนหนักที่จุดกลางทาง ถ้าเลื่อนออกเดินทาง
ฝนจะหายไปแล้ว -> ต้องได้ DELAY ไม่ใช่ AVOID และต้องยิง forecast/points แค่ครั้งเดียว
รวมจุดเลื่อนเวลาไว้ในคำขอเดียวกับชุดแรกตาม README ข้อ 6
"""
from fastapi.testclient import TestClient

import app as appmod

BKK = {"lat": 13.7563, "lng": 100.5018}
NAKHON_SAWAN = {"lat": 15.7, "lng": 100.1}
CHIANG_MAI = {"lat": 18.7883, "lng": 98.9853}

T0 = "2026-09-24T00:00:00Z"
T_TROUBLE = "2026-09-24T02:00:00Z"  # ฝนหนักตอนนี้
T_END = "2026-09-24T04:00:00Z"


def _single_route_body():
    return {"routes": [{"route_id": "r1", "duration_min": 240, "points": [
        {**BKK, "eta": T0},
        {**NAKHON_SAWAN, "eta": T_TROUBLE},
        {**CHIANG_MAI, "eta": T_END},
    ]}]}


def _make_fake_call(rainy_times):
    def fake_call(url_env, method, path, *, timeout, json=None, params=None, headers=None):
        if path == "/api/v1/forecast/points":
            forecasts = [{"rain_mm_per_h": 40 if p["time"] in rainy_times else 2, "wind_kmh": 10}
                         for p in json["points"]]
            return {"points": [{"forecast": f} for f in forecasts], "warnings": []}
        if path == "/api/v1/hazards":
            return {"hazards": []}
        raise AssertionError(f"unexpected call: {path}")
    return fake_call


def test_delay_recommended_when_shifting_avoids_the_rain(monkeypatch):
    # ฝนหนักเฉพาะเวลาปัจจุบัน (T_TROUBLE) เท่านั้น เลื่อน +3 หรือ +6 ชม. แล้วจุดนี้ฝนหายหมด
    monkeypatch.setattr(appmod, "call", _make_fake_call({T_TROUBLE}))
    client = TestClient(appmod.app)
    res = client.post("/api/v1/risk/evaluate", json=_single_route_body())
    data = res.json()["data"]

    assert res.status_code == 200
    assert data["routes"][0]["risk_level"] == "HIGH"
    assert data["recommended_route_id"] == "r1"
    assert data["recommendation"] == "DELAY"
    assert "3 ชม." in data["summary_th"]  # +3 ชม. ก็พอแล้ว ต้องเลือกอันสั้นสุดที่ช่วยได้


def test_avoid_when_delay_does_not_help(monkeypatch):
    # ฝนหนักตลอด ไม่ว่าจะเลื่อนกี่ชม. ก็ไม่ดีขึ้น ไม่มีทางเลือก -> ต้องได้ AVOID เหมือนก่อนมี 7.4
    monkeypatch.setattr(appmod, "call", _make_fake_call({T_TROUBLE, "2026-09-24T05:00:00Z",
                                                          "2026-09-24T08:00:00Z"}))
    client = TestClient(appmod.app)
    res = client.post("/api/v1/risk/evaluate", json=_single_route_body())
    data = res.json()["data"]

    assert data["recommendation"] == "AVOID"
    assert data["recommended_route_id"] == "r1"


def test_forecast_points_requested_in_a_single_batched_call(monkeypatch):
    seen_calls = []

    def counting_call(url_env, method, path, *, timeout, json=None, params=None, headers=None):
        if path == "/api/v1/forecast/points":
            seen_calls.append(len(json["points"]))
            forecasts = [{"rain_mm_per_h": 2, "wind_kmh": 10} for _ in json["points"]]
            return {"points": [{"forecast": f} for f in forecasts], "warnings": []}
        if path == "/api/v1/hazards":
            return {"hazards": []}
        raise AssertionError(f"unexpected call: {path}")

    monkeypatch.setattr(appmod, "call", counting_call)
    client = TestClient(appmod.app)
    client.post("/api/v1/risk/evaluate", json=_single_route_body())

    assert seen_calls == [9]  # 3 จุดเดิม + (3 จุด x 2 ช่วงเวลา +3/+6 ชม.) ยิงครั้งเดียวรวมกัน
