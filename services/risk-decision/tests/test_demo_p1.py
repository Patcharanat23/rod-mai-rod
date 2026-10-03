"""P.1: ทริปตัวอย่างเจอฝนหนัก กรุงเทพ -> เชียงใหม่ (งานคู่กับ Pitchakorn, routing-engine)

ข้อมูลจุด/เวลาชุดนี้มาจากที่ Pitchakorn เตรียม fixture DEMO_MODE ไว้ให้แล้ว (ยืนยันในห้องทีม):
  r1 ผ่านกำแพงเพชร-ตาก (685 กม.), r2 ผ่านพิษณุโลก (713 กม., ช้ากว่า r1 ประมาณ 7%)
  ช่วงที่มีแค่ r1 ผ่าน: lat 15.5-17.9, lng 99.0-100.2 (เข้าตาก 16.87,99.13)
  เวลาประมาณ +2:45 ถึง +6:45 ชม. หลังออกเดินทาง
ฝั่ง risk-decision ไม่ต้องแก้โค้ดเพิ่มสำหรับงานนี้ (7.1/7.2/7.3 ครอบคลุมแล้ว) เทสต์นี้คือการยืนยัน
end-to-end ว่าเมื่อ routing-engine ส่งจุดชุดนี้เข้ามาจริง จะได้ REROUTE ไปทาง r2 ตามที่ต้องการ
สอง sceanario ที่ Pitchakorn บอกว่าจะใช้ทดสอบ: ฝนหนัก หรือหมุดภัย HIGH ในโซนเดียวกัน ทั้งสองแบบต้องได้ REROUTE
"""
from fastapi.testclient import TestClient

import app as appmod

BKK = {"lat": 13.7563, "lng": 100.5018}
TAK = {"lat": 16.87, "lng": 99.13}
PHITSANULOK = {"lat": 16.8211, "lng": 100.2659}
CHIANG_MAI = {"lat": 18.7883, "lng": 98.9853}

T0 = "2026-09-24T00:00:00Z"  # ออกเดินทาง 07:00 น. ไทย
T_TAK = "2026-09-24T04:00:00Z"  # +4 ชม. อยู่ในช่วง +2:45 ถึง +6:45 ที่ Pitchakorn กำหนด
T_R1_END = "2026-09-24T08:00:00Z"
T_PHITSANULOK = "2026-09-24T04:17:00Z"  # เส้น r2 ช้ากว่าตามสัดส่วน 7%
T_R2_END = "2026-09-24T08:34:00Z"


def _routes_body():
    return {
        "routes": [
            {"route_id": "r1_tak", "duration_min": 480, "points": [
                {**BKK, "eta": T0},
                {**TAK, "eta": T_TAK},
                {**CHIANG_MAI, "eta": T_R1_END},
            ]},
            {"route_id": "r2_phitsanulok", "duration_min": 514, "points": [
                {**BKK, "eta": T0},
                {**PHITSANULOK, "eta": T_PHITSANULOK},
                {**CHIANG_MAI, "eta": T_R2_END},
            ]},
        ]
    }


def _find(routes, route_id):
    return next(r for r in routes if r["route_id"] == route_id)


def test_demo_p1_reroute_via_heavy_rain_at_tak(monkeypatch):
    def fake_call(url_env, method, path, *, timeout, json=None, params=None, headers=None):
        if path == "/api/v1/forecast/points":
            forecasts = []
            for p in json["points"]:
                if abs(p["lat"] - TAK["lat"]) < 0.01 and abs(p["lng"] - TAK["lng"]) < 0.01:
                    forecasts.append({"rain_mm_per_h": 40, "wind_kmh": 10})  # ฝนหนักเฉพาะช่วงตาก
                else:
                    forecasts.append({"rain_mm_per_h": 2, "wind_kmh": 10})
            return {"points": [{"forecast": f} for f in forecasts], "warnings": []}
        if path == "/api/v1/hazards":
            return {"hazards": []}
        raise AssertionError(f"unexpected call: {path}")

    monkeypatch.setattr(appmod, "call", fake_call)
    client = TestClient(appmod.app)
    res = client.post("/api/v1/risk/evaluate", json=_routes_body())
    data = res.json()["data"]

    assert res.status_code == 200
    assert _find(data["routes"], "r1_tak")["risk_level"] == "HIGH"
    assert _find(data["routes"], "r2_phitsanulok")["risk_level"] == "LOW"
    assert data["recommended_route_id"] == "r2_phitsanulok"
    assert data["recommendation"] == "REROUTE"
    assert "เส้นทางสำรอง" in data["summary_th"]
    assert data["warnings"] == []


def test_demo_p1_reroute_via_hazard_marker_at_tak(monkeypatch):
    def fake_call(url_env, method, path, *, timeout, json=None, params=None, headers=None):
        if path == "/api/v1/forecast/points":
            forecasts = [{"rain_mm_per_h": 2, "wind_kmh": 10} for _ in json["points"]]  # อากาศปกติทั้งหมด
            return {"points": [{"forecast": f} for f in forecasts], "warnings": []}
        if path == "/api/v1/hazards":
            # หมุดภัย HIGH ใกล้ตาก (ไม่ใช่ฝน/ลม) ต้องยกระดับจุดเป็น HIGH เหมือนกัน (7.1)
            return {"hazards": [{"lat": 16.85, "lng": 99.10, "severity": "HIGH", "hazard_id": "demo-p1"}]}
        raise AssertionError(f"unexpected call: {path}")

    monkeypatch.setattr(appmod, "call", fake_call)
    client = TestClient(appmod.app)
    res = client.post("/api/v1/risk/evaluate", json=_routes_body())
    data = res.json()["data"]

    assert res.status_code == 200
    assert _find(data["routes"], "r1_tak")["risk_level"] == "HIGH"
    assert _find(data["routes"], "r2_phitsanulok")["risk_level"] == "LOW"
    assert data["recommended_route_id"] == "r2_phitsanulok"
    assert data["recommendation"] == "REROUTE"
    assert "มีหมุดภัย" in data["summary_th"]
