from fastapi.testclient import TestClient

import app as routing

client = TestClient(routing.app)
BODY = {
    "origin": {"lat": 13.7563, "lng": 100.5018, "name": "กรุงเทพ"},
    "destination": {"lat": 18.7883, "lng": 98.9853, "name": "เชียงใหม่"},
    "waypoints": [{"lat": 15.7047, "lng": 100.1372, "name": "นครสวรรค์"}],
    "departure_time": "2030-01-01T01:00:00Z",
}


def test_risk_down_still_returns_route_without_guessing_low(monkeypatch):
    monkeypatch.setenv("RISK_DECISION_URL", "http://127.0.0.1:9")  # ไม่มีใครฟังพอร์ตนี้
    res = client.post("/api/v1/routes/plan", json=BODY).json()
    plan = res["data"]
    assert res["error"] is None
    assert "WEATHER_UNAVAILABLE" in plan["warnings"]
    assert plan["risk_level"] is None
    assert all(w["risk_level"] is None for w in plan["waypoints"])
    assert [w["kind"] for w in plan["waypoints"]] == ["ORIGIN", "STOP", "DESTINATION"]


def test_eta_is_cumulative():
    stops = [routing.Place(**BODY["origin"]), routing.Place(**BODY["waypoints"][0]), routing.Place(**BODY["destination"])]
    r = routing.fetch_routes(stops)[0]
    points, idx = routing.risk_points(r, stops, routing.datetime.fromisoformat("2030-01-01T01:00:00+00:00"))
    etas = [points[i]["eta"] for i in idx]
    assert etas == sorted(etas) and etas[0] == "2030-01-01T01:00:00Z"
