import pytest
from fastapi.testclient import TestClient

import app as routing
from envelope import ApiError

REAL_OSRM_REQUEST = routing.osrm_request  # เก็บไว้ก่อน conftest แทนด้วยตัวอ่าน fixture
BKK = routing.Place(lat=13.7563, lng=100.5018)
NSN = routing.Place(lat=15.7047, lng=100.1372)
CNX = routing.Place(lat=18.7883, lng=98.9853)
BODY = {"origin": {"lat": 13.7563, "lng": 100.5018, "name": "กรุงเทพ"},
        "destination": {"lat": 18.7883, "lng": 98.9853, "name": "เชียงใหม่"},
        "departure_time": "2030-01-01T01:00:00Z"}


@pytest.fixture
def demo_offline(monkeypatch):
    """DEMO_MODE=true และตัดเน็ตทุกทาง ถ้ามีการยิงออกไปเทสต์ต้องพัง"""
    def no_network(*a, **k):
        raise AssertionError("DEMO_MODE ต้องไม่เรียกเน็ต")

    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setattr(routing.httpx, "get", no_network)
    monkeypatch.setattr(routing, "osrm_request", REAL_OSRM_REQUEST)


def test_demo_mode_plans_sample_trips_without_network(demo_offline):
    assert [r["duration_min"] for r in routing.fetch_routes([BKK, CNX])] == [516, 554]
    (r,) = routing.fetch_routes([BKK, NSN, CNX])
    assert 150 <= r["stop_minutes"][1] <= 200 and len(r["samples"]) > 30


def test_demo_mode_works_even_without_osrm_url(demo_offline, monkeypatch):
    monkeypatch.delenv("OSRM_BASE_URL")
    assert len(routing.fetch_routes([BKK, CNX])) == 2


def test_demo_mode_unknown_trip_is_clear_error(demo_offline):
    res = TestClient(routing.app).post("/api/v1/routes/plan", json={
        **BODY, "destination": {"lat": 7.8804, "lng": 98.3923}}).json()  # ภูเก็ต ไม่มี fixture
    assert res["data"] is None and res["error"]["code"] == "UPSTREAM_ERROR"
    assert "โหมดสาธิต" in res["error"]["message"]


def test_demo_mode_full_plan_same_as_live(demo_offline, monkeypatch):
    client = TestClient(routing.app)
    demo = client.post("/api/v1/routes/plan", json=BODY).json()["data"]
    monkeypatch.setenv("DEMO_MODE", "false")
    routing._cache.clear()
    from conftest import saved
    monkeypatch.setattr(routing, "osrm_request", saved)
    live = client.post("/api/v1/routes/plan", json=BODY).json()["data"]
    assert demo["route_options"] == live["route_options"] and demo["waypoints"] == live["waypoints"]


def test_demo_mode_off_never_reads_fixtures(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setattr(routing, "osrm_request", REAL_OSRM_REQUEST)
    calls = []

    def down(*a, **k):
        calls.append(1)
        raise routing.httpx.ConnectError("down")

    monkeypatch.setattr(routing.httpx, "get", down)
    with pytest.raises(ApiError):
        routing.fetch_routes([BKK, CNX])
    assert calls == [1]


def test_every_fixture_is_named_by_its_stops_and_valid():
    files = sorted(routing.FIXTURES.glob("*.json"))
    assert len(files) >= 2
    for f in files:
        stops = [routing.Place(lat=float(a), lng=float(b)) for a, b in (p.split("_") for p in f.stem.split("__"))]
        assert routing.fixture_path(routing.route_key(stops)) == f
        body = routing.json.loads(f.read_text())
        assert body["code"] == "Ok" and isinstance(body["routes"][0]["geometry"], str)  # polyline
        assert len(body["waypoints"]) == len(stops)


def test_demo_mode_accepts_a_tap_near_the_sample_trip(demo_offline):
    # จิ้มแผนที่บนเวทีคลาดไปหลายกิโล (แถวบางซื่อ, ใต้ตัวเมืองเชียงใหม่) ยังได้ทริปตัวอย่าง
    tapped = [routing.Place(lat=13.80, lng=100.54), routing.Place(lat=18.74, lng=98.96)]
    assert all(routing.haversine_km(t.model_dump(), s.model_dump()) > 5 for t, s in zip(tapped, [BKK, CNX]))
    assert [r["duration_min"] for r in routing.fetch_routes(tapped)] == [516, 554]
    (r,) = routing.fetch_routes([tapped[0], routing.Place(lat=15.69, lng=100.12), tapped[1]])
    assert 150 <= r["stop_minutes"][1] <= 200


def test_demo_mode_too_far_or_different_stops_is_still_an_error(demo_offline):
    with pytest.raises(ApiError):
        routing.fetch_routes([BKK, routing.Place(lat=18.5, lng=98.9)])  # ห่างเชียงใหม่ประมาณ 32 กม.
    with pytest.raises(ApiError):
        routing.fetch_routes([BKK, routing.Place(lat=16.0, lng=100.0), CNX])  # หมุดกลางไม่ใช่นครสวรรค์


def test_nearest_fixture_matches_same_stop_count_only():
    key = routing.route_key([BKK, CNX])
    assert routing.nearest_fixture(key) == routing.fixture_path(key)
    assert routing.nearest_fixture(((13.8, 100.5), (18.8, 99.0))).stem.count("__") == 1
    # กรุงเทพ > นครสวรรค์ ตรงกับครึ่งแรกของทริปแวะนครสวรรค์ แต่เป็นคนละทริป ต้องไม่หยิบมาใช้
    assert routing.nearest_fixture(routing.route_key([BKK, NSN])) is None
