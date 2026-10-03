import pytest
from fastapi.testclient import TestClient

import app as routing
from geo import haversine_km

TAK = {"lat": 16.87, "lng": 99.13}
BKK = {"lat": 13.7563, "lng": 100.5018, "name": "กรุงเทพ"}
NSN = {"lat": 15.7047, "lng": 100.1372, "name": "นครสวรรค์"}
CNX = {"lat": 18.7883, "lng": 98.9853, "name": "เชียงใหม่"}
VIA_NSN = {"origin": BKK, "waypoints": [NSN], "destination": CNX, "departure_time": "2030-01-01T01:00:00Z"}
DIRECT = {"origin": BKK, "destination": CNX, "departure_time": "2030-01-01T01:00:00Z"}


def fake_risk(level_near_tak="HIGH", fail_on_call=None):
    """risk-decision ปลอม จุดในรัศมี 30 กม. รอบตากได้ level_near_tak ที่เหลือ LOW เลือกเส้นที่ระดับต่ำสุด"""
    calls = []
    order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

    def call(url_env, method, path, *, timeout, json=None, **kw):
        calls.append({"timeout": timeout, "route_ids": [r["route_id"] for r in json["routes"]]})
        if fail_on_call == len(calls):
            raise routing.ApiError("UPSTREAM_TIMEOUT", "x")
        routes = []
        for r in json["routes"]:
            pts = [{**p, "forecast": None, "hazards": [],
                    "risk_level": level_near_tak if haversine_km(p, TAK) < 30 else "LOW"} for p in r["points"]]
            level = max((p["risk_level"] for p in pts), key=order.get)
            routes.append({"route_id": r["route_id"], "risk_level": level, "risk_score": 80 if level == "HIGH" else 10,
                           "points": pts})
        best = min(routes, key=lambda r: order[r["risk_level"]])
        rec = "NORMAL" if routes[0]["risk_level"] == "LOW" else "REROUTE" if best is not routes[0] else "AVOID"
        return {"routes": routes, "recommended_route_id": best["route_id"], "recommendation": rec,
                "summary_th": "x", "warnings": []}

    return call, calls


@pytest.fixture
def plan(monkeypatch):
    def run(body, **risk_kw):
        call, calls = fake_risk(**risk_kw)
        monkeypatch.setattr(routing, "call", call)
        res = TestClient(routing.app).post("/api/v1/routes/plan", json=body).json()
        assert res["error"] is None
        return res["data"], calls
    return run


def test_single_high_route_gets_a_detour_that_avoids_the_risk(plan):
    data, calls = plan(VIA_NSN)
    assert [o["route_id"] for o in data["route_options"]] == ["r1", "r2"]
    r1, r2 = data["route_options"]
    assert r1["risk_level"] == "HIGH" and r2["risk_level"] == "LOW" and r2["is_recommended"]
    assert data["recommendation"] == "REROUTE"
    assert "ALTERNATIVE_ROUTES_UNAVAILABLE" not in data["warnings"]
    assert min(haversine_km(TAK, g) for g in r2["geometry"]) > routing.HAZARD_RADIUS_KM
    assert r2["duration_min"] <= r1["duration_min"] * routing.MAX_SLOWER_RATIO
    assert [c["route_ids"] for c in calls] == [["r1"], ["r1", "r2"]]  # ทุกเส้นในคำขอเดียวทุกรอบ


def test_detour_picks_the_faster_side(plan):
    data, _ = plan(VIA_NSN)
    # ดันไปทางตะวันออก (สุโขทัย) ได้ประมาณ 10 ชม. ทางตะวันตก (ชายแดน) ประมาณ 12.8 ชม.
    assert data["route_options"][1]["duration_min"] < 11 * 60


def test_detour_keeps_user_stops_only(plan):
    data, _ = plan(VIA_NSN)
    assert [w["kind"] for w in data["waypoints"]] == ["ORIGIN", "STOP", "DESTINATION"]
    assert [w["name"] for w in data["waypoints"]] == ["กรุงเทพ", "นครสวรรค์", "เชียงใหม่"]
    eta = [w["eta"] for w in data["waypoints"]]
    assert eta == sorted(eta)
    # จุดผ่านที่เราเติมต้องไม่กินตำแหน่งของหมุด เวลาถึงปลายทางต้องเท่ากับเวลาถึงของทั้งเส้น
    assert eta[-1][:16] == data["arrival_time"][:16]


def test_second_risk_call_only_gets_the_time_left(plan):
    _, calls = plan(VIA_NSN)
    assert calls[0]["timeout"] == routing.RISK_TIMEOUT
    assert 5 <= calls[1]["timeout"] <= routing.RISK_TIMEOUT


def test_medium_route_is_not_detoured(plan):
    data, calls = plan(VIA_NSN, level_near_tak="MEDIUM")
    assert len(data["route_options"]) == 1 and len(calls) == 1
    assert "ALTERNATIVE_ROUTES_UNAVAILABLE" in data["warnings"]


def test_two_routes_already_no_detour(plan):
    data, calls = plan(DIRECT)
    assert len(data["route_options"]) == 2 and len(calls) == 1


def test_no_time_left_returns_first_result(plan, monkeypatch):
    monkeypatch.setattr(routing, "PLAN_BUDGET", 1)
    data, calls = plan(VIA_NSN)
    assert len(data["route_options"]) == 1 and len(calls) == 1
    assert "ALTERNATIVE_ROUTES_UNAVAILABLE" in data["warnings"] and data["risk_level"] == "HIGH"


def test_second_risk_failure_keeps_first_result(plan):
    data, calls = plan(VIA_NSN, fail_on_call=2)
    assert len(calls) == 2 and len(data["route_options"]) == 1
    assert data["risk_level"] == "HIGH" and "WEATHER_UNAVAILABLE" not in data["warnings"]


def test_risk_down_no_detour(plan):
    data, calls = plan(VIA_NSN, fail_on_call=1)
    assert len(calls) == 1 and data["risk_level"] is None and "WEATHER_UNAVAILABLE" in data["warnings"]


def test_high_stop_alone_cannot_be_avoided():
    route = {"stop_idx": [0, 1, 2]}
    pts = [{"lat": 13.0, "lng": 100.0, "risk_level": "LOW"}, {"lat": 14.0, "lng": 100.0, "risk_level": "HIGH"},
           {"lat": 15.0, "lng": 100.0, "risk_level": "LOW"}]
    assert routing.detour_vias(route, pts, []) == ([], [])


def test_via_outside_thailand_is_dropped():
    # เส้นขึ้นเหนือตามลองจิจูด 97.6 ดันไปทางตะวันตก 50 กม. ตกนอกกรอบประเทศไทย
    route = {"stop_idx": [0, 3]}
    pts = [{"lat": 17.0 + i * 0.2, "lng": 97.6, "risk_level": "HIGH" if i in (1, 2) else "LOW"} for i in range(4)]
    risky, vias = routing.detour_vias(route, pts, [])
    assert len(risky) == 2 and len(vias) == 1 and vias[0][1].lng > 97.6


def _stops():
    return [routing.Place(**{k: v for k, v in s.items() if k != "name"}) for s in (BKK, NSN, CNX)]


WEST = (2, routing.Place(lat=16.6534, lng=98.7324))  # ดันไปทางชายแดน ได้ถนนอ้อมภูเขา
EAST = (2, routing.Place(lat=17.0462, lng=99.5778))  # ดันไปทางสุโขทัย


def test_find_detour_prefers_faster_even_if_listed_later():
    (main,) = routing.fetch_routes(_stops())
    far_away = [{"lat": 10.0, "lng": 99.0}]  # จุดเสี่ยงสมมติที่ไม่มีเส้นไหนผ่าน ทั้งสองเส้นจึงผ่านเกณฑ์ระยะ
    got = routing.find_detour(main, far_away, [WEST, EAST], _stops(), routing.time.monotonic() + 40)
    assert got["duration_min"] < 11 * 60


def test_find_detour_rejects_route_through_the_risk():
    (main,) = routing.fetch_routes(_stops())
    west = routing.find_detour(main, [{"lat": 10.0, "lng": 99.0}], [WEST], _stops(), routing.time.monotonic() + 40)
    on_west_road = west["geometry"][len(west["geometry"]) // 2]
    assert routing.find_detour(main, [on_west_road], [WEST], _stops(), routing.time.monotonic() + 40) is None


def test_find_detour_rejects_too_slow(monkeypatch):
    (main,) = routing.fetch_routes(_stops())
    monkeypatch.setattr(routing, "MAX_SLOWER_RATIO", 1.1)  # ตะวันออกช้ากว่า 14%
    assert routing.find_detour(main, [{"lat": 10.0, "lng": 99.0}], [EAST], _stops(),
                               routing.time.monotonic() + 40) is None


def test_find_detour_stops_when_time_runs_out():
    (main,) = routing.fetch_routes(_stops())
    assert routing.find_detour(main, [{"lat": 10.0, "lng": 99.0}], [EAST], _stops(), routing.time.monotonic() + 5) is None
