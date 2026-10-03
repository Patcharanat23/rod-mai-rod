"""แก้จากทดสอบรวมทั้งระบบ 2026-09-25 (INTEG_risk-decision_2026-09-25.md) และงาน 7.5

1) FORECAST_OUT_OF_RANGE ของจุดเลื่อนเวลา (DELAY +3/+6 ชม.) ไม่ควรรั่วเข้าคำตอบตอนจุดจริงมีพยากรณ์ครบ
   แต่จุดจริงที่ขาดพยากรณ์จริงๆ (เกินช่วงพยากรณ์) ต้องยังเห็น warning นี้ (ข้อ 1)
2) summary_th ต้องไม่บอกว่า "ตลอดเส้นทางปกติ" ถ้ามีบางจุดในเส้นหลักยังไม่มีข้อมูล (risk_level เป็น None) (ข้อ 2)
3) 7.5: หมุดภัย source OPEN_METEO (ฝน/ลม ณ ชั่วโมงนี้ จาก weather-disaster งาน 6.7) ไม่ถูกนับตอนคิด
   ความเสี่ยงรายจุด กันนับซ้ำกับพยากรณ์ ณ เวลาที่ไปถึงที่ใช้อยู่แล้ว
"""
from fastapi.testclient import TestClient

import app as appmod
from envelope import ApiError

BKK = {"lat": 13.7563, "lng": 100.5018}
NAKHON_SAWAN = {"lat": 15.7, "lng": 100.1}
CHIANG_MAI = {"lat": 18.7883, "lng": 98.9853}

T0 = "2026-09-24T00:00:00Z"
T_MID = "2026-09-24T02:00:00Z"
T_END = "2026-09-24T04:00:00Z"


def _single_route_body():
    return {"routes": [{"route_id": "r1", "duration_min": 240, "points": [
        {**BKK, "eta": T0},
        {**NAKHON_SAWAN, "eta": T_MID},
        {**CHIANG_MAI, "eta": T_END},
    ]}]}


def test_forecast_out_of_range_from_delay_points_does_not_leak_onto_real_route(monkeypatch):
    """จุดจริงทุกจุดมีพยากรณ์ครบ แต่จุดเลื่อนเวลา +6 ชม. เกินช่วงพยากรณ์ (weather-disaster เลยตอบ
    warnings รวมมาว่า FORECAST_OUT_OF_RANGE) ต้องไม่เห็น warning นี้เลยในคำตอบ"""
    def fake_call(url_env, method, path, *, timeout, json=None, params=None, headers=None):
        if path == "/api/v1/forecast/points":
            forecasts = [{"rain_mm_per_h": 2, "wind_kmh": 10} for _ in json["points"]]  # ทุกจุดมีข้อมูล
            return {"points": [{"forecast": f} for f in forecasts], "warnings": ["FORECAST_OUT_OF_RANGE"]}
        if path == "/api/v1/hazards":
            return {"hazards": []}
        raise AssertionError(f"unexpected call: {path}")

    monkeypatch.setattr(appmod, "call", fake_call)
    client = TestClient(appmod.app)
    res = client.post("/api/v1/risk/evaluate", json=_single_route_body())
    data = res.json()["data"]

    assert all(p["risk_level"] is not None for p in data["routes"][0]["points"])
    assert data["warnings"] == []


def test_forecast_out_of_range_still_shown_when_a_real_point_is_out_of_range(monkeypatch):
    """จุดจริงกลางทาง (นครสวรรค์) เกินช่วงพยากรณ์จริงๆ ต้องยังเห็น FORECAST_OUT_OF_RANGE"""
    def fake_call(url_env, method, path, *, timeout, json=None, params=None, headers=None):
        if path == "/api/v1/forecast/points":
            forecasts = [None if p["time"] == T_MID else {"rain_mm_per_h": 2, "wind_kmh": 10}
                         for p in json["points"]]
            return {"points": [{"forecast": f} for f in forecasts], "warnings": ["FORECAST_OUT_OF_RANGE"]}
        if path == "/api/v1/hazards":
            return {"hazards": []}
        raise AssertionError(f"unexpected call: {path}")

    monkeypatch.setattr(appmod, "call", fake_call)
    client = TestClient(appmod.app)
    res = client.post("/api/v1/risk/evaluate", json=_single_route_body())
    data = res.json()["data"]

    assert "FORECAST_OUT_OF_RANGE" in data["warnings"]


def test_forecast_out_of_range_not_invented_when_weather_disaster_is_fully_down(monkeypatch):
    """weather-disaster ล่มไปเลย (ApiError) ไม่ใช่วันเดินทางเกินช่วงพยากรณ์ ห้ามใส่ FORECAST_OUT_OF_RANGE
    เดาเอง เพราะ weather-disaster ไม่เคยส่งสัญญาณนี้มาจริง"""
    def fake_call(url_env, method, path, *, timeout, json=None, params=None, headers=None):
        if path == "/api/v1/forecast/points":
            raise ApiError("UPSTREAM_ERROR", "down")
        if path == "/api/v1/hazards":
            return {"hazards": []}
        raise AssertionError(f"unexpected call: {path}")

    monkeypatch.setattr(appmod, "call", fake_call)
    client = TestClient(appmod.app)
    res = client.post("/api/v1/risk/evaluate", json=_single_route_body())
    data = res.json()["data"]

    assert "WEATHER_UNAVAILABLE" in data["warnings"]
    assert "FORECAST_OUT_OF_RANGE" not in data["warnings"]


def test_summary_does_not_claim_whole_route_normal_when_some_points_have_no_data(monkeypatch):
    """เส้นหลัก LOW (จุดที่มีข้อมูล) แต่มีบางจุด null ห้ามบอกว่า 'ตลอดเส้นทางปกติ'"""
    def fake_call(url_env, method, path, *, timeout, json=None, params=None, headers=None):
        if path == "/api/v1/forecast/points":
            forecasts = [None if p["time"] == T_END else {"rain_mm_per_h": 2, "wind_kmh": 10}
                         for p in json["points"]]
            return {"points": [{"forecast": f} for f in forecasts], "warnings": []}
        if path == "/api/v1/hazards":
            return {"hazards": []}
        raise AssertionError(f"unexpected call: {path}")

    monkeypatch.setattr(appmod, "call", fake_call)
    client = TestClient(appmod.app)
    res = client.post("/api/v1/risk/evaluate", json=_single_route_body())
    data = res.json()["data"]

    assert data["recommendation"] == "NORMAL"
    assert data["routes"][0]["risk_level"] == "LOW"
    assert "ตลอดเส้นทางปกติ" not in data["summary_th"]
    assert len(data["summary_th"]) > 0


def test_open_meteo_sourced_hazard_pin_is_skipped_when_scoring(monkeypatch):
    """7.5: หมุด source OPEN_METEO (ฝน/ลม ณ ชั่วโมงนี้) ต้องไม่ถูกนับ จุดฝนลมเบาไม่ควรถูกดันเป็น HIGH
    เพราะหมุดนี้ ไม่งั้นความเสี่ยงจะกลายเป็นของตอนนี้แทนตอนที่ไปถึง"""
    def fake_call(url_env, method, path, *, timeout, json=None, params=None, headers=None):
        if path == "/api/v1/forecast/points":
            forecasts = [{"rain_mm_per_h": 2, "wind_kmh": 10} for _ in json["points"]]  # ฝนลมเบาทุกจุด
            return {"points": [{"forecast": f} for f in forecasts], "warnings": []}
        if path == "/api/v1/hazards":
            return {"hazards": [{"lat": BKK["lat"], "lng": BKK["lng"], "severity": "HIGH",
                                  "hazard_id": "openmeteo-rain-13.76_100.50", "source": "OPEN_METEO"}]}
        raise AssertionError(f"unexpected call: {path}")

    monkeypatch.setattr(appmod, "call", fake_call)
    client = TestClient(appmod.app)
    res = client.post("/api/v1/risk/evaluate", json=_single_route_body())
    data = res.json()["data"]

    assert data["routes"][0]["risk_level"] == "LOW"  # หมุด OPEN_METEO ไม่ถูกนับ ไม่งั้นจะได้ HIGH
    assert all(h.get("source") != "OPEN_METEO" for p in data["routes"][0]["points"] for h in p["hazards"])


def test_non_open_meteo_hazard_still_counts(monkeypatch):
    """หมุดจากแหล่งอื่น (เช่น GDACS) ต้องยังนับตามปกติ ไม่ได้กรองหมุดทุกแหล่งทิ้ง"""
    def fake_call(url_env, method, path, *, timeout, json=None, params=None, headers=None):
        if path == "/api/v1/forecast/points":
            forecasts = [{"rain_mm_per_h": 2, "wind_kmh": 10} for _ in json["points"]]
            return {"points": [{"forecast": f} for f in forecasts], "warnings": []}
        if path == "/api/v1/hazards":
            return {"hazards": [{"lat": BKK["lat"], "lng": BKK["lng"], "severity": "HIGH",
                                  "hazard_id": "gdacs-1", "source": "GDACS"}]}
        raise AssertionError(f"unexpected call: {path}")

    monkeypatch.setattr(appmod, "call", fake_call)
    client = TestClient(appmod.app)
    res = client.post("/api/v1/risk/evaluate", json=_single_route_body())
    data = res.json()["data"]

    assert data["routes"][0]["risk_level"] == "HIGH"
