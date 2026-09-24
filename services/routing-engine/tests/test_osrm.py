import time

import httpx
import pytest

import app as routing
from conftest import saved
from envelope import ApiError

REAL_OSRM_REQUEST = routing.osrm_request  # เก็บไว้ก่อน conftest แทนด้วยตัวอ่าน fixture
BKK = routing.Place(lat=13.7563, lng=100.5018)
NSN = routing.Place(lat=15.7047, lng=100.1372)
CNX = routing.Place(lat=18.7883, lng=98.9853)


def test_bangkok_chiang_mai_two_real_routes():
    routes = routing.fetch_routes([BKK, CNX])
    assert [r["route_id"] for r in routes] == ["r1", "r2"]
    assert routes[0]["duration_min"] <= routes[1]["duration_min"]
    assert all(480 <= r["duration_min"] <= 570 for r in routes)  # ประมาณ 8-9 ชม.
    assert routes[0]["distance_km"] == 685


def test_coordinates_not_swapped():
    geo = routing.fetch_routes([BKK, CNX])[0]["geometry"]
    # ถ้าสลับ lat/lng จุดแรกจะได้ lat 100.5 ซึ่งไม่มีจริง
    assert abs(geo[0]["lat"] - 13.75) < 0.01 and abs(geo[0]["lng"] - 100.50) < 0.01
    assert abs(geo[-1]["lat"] - 18.79) < 0.01 and abs(geo[-1]["lng"] - 98.99) < 0.01


def test_geometry_at_most_500_points():
    for r in routing.fetch_routes([BKK, CNX]) + routing.fetch_routes([BKK, NSN, CNX]):
        assert 2 <= len(r["geometry"]) <= 500


def test_stop_minutes_cumulative_with_waypoint():
    (r,) = routing.fetch_routes([BKK, NSN, CNX])  # มีหมุดระหว่างทาง OSRM ให้เส้นเดียว
    first, to_nsn, to_cnx = r["stop_minutes"]
    assert first == 0
    assert 150 <= to_nsn <= 200  # นครสวรรค์ประมาณ 3 ชม.
    assert to_cnx > to_nsn
    assert round(to_cnx) == r["duration_min"]


def test_simplify_keeps_endpoints_and_order():
    points = [(13 + i / 1000, 100 + i / 1000) for i in range(1234)]
    out = routing.simplify(points)
    assert len(out) == 500
    assert out[0] == {"lat": 13.0, "lng": 100.0}
    assert out[-1] == {"lat": 13 + 1233 / 1000, "lng": 100 + 1233 / 1000}
    assert [p["lat"] for p in out] == sorted(p["lat"] for p in out)
    assert routing.simplify([(13.75, 100.5)]) == [{"lat": 13.75, "lng": 100.5}]


def test_decode_polyline_reference_example():
    # ตัวอย่างมาตรฐานของรูปแบบ polyline
    assert routing.decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@") == [
        (38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]


def _osrm_replies(monkeypatch, handler):
    calls = []

    def recording(url, params, timeout):
        calls.append(url)
        return handler(url, params, timeout)

    monkeypatch.setattr(routing.httpx, "get", recording)
    return calls


def _ok(*a):
    return httpx.Response(200, json=saved([BKK, CNX]))


def _raise(exc):
    def handler(*a):
        raise exc
    return handler


@pytest.mark.parametrize("handler, code", [
    (_raise(httpx.ReadTimeout("slow")), "UPSTREAM_TIMEOUT"),
    (_raise(httpx.ConnectError("down")), "UPSTREAM_ERROR"),
    (lambda *a: httpx.Response(429, json={"code": "TooManyRequests"}), "RATE_LIMITED"),
    (lambda *a: httpx.Response(429, text="<html>slow down</html>"), "RATE_LIMITED"),
    (lambda *a: httpx.Response(400, json={"code": "InvalidQuery", "message": "x"}), "UPSTREAM_ERROR"),
    (lambda *a: httpx.Response(502, text="<html>bad gateway</html>"), "UPSTREAM_ERROR"),
])
def test_osrm_failures_become_contract_errors(monkeypatch, handler, code):
    _osrm_replies(monkeypatch, handler)
    with pytest.raises(ApiError) as e:
        REAL_OSRM_REQUEST([BKK, CNX])
    assert e.value.code == code


def test_no_route_says_why_instead_of_retry(monkeypatch):
    _osrm_replies(monkeypatch, lambda *a: httpx.Response(400, json={"code": "NoRoute"}))
    with pytest.raises(ApiError) as e:
        REAL_OSRM_REQUEST([BKK, CNX])
    assert "ถนน" in e.value.message and "ลองใหม่" not in e.value.message


def test_osrm_url_is_lng_lat_and_reads_env(monkeypatch):
    seen = {}

    def handler(url, params, timeout):
        seen.update(url=url, params=params)
        return _ok()

    monkeypatch.setenv("OSRM_BASE_URL", "http://osrm.test/")
    _osrm_replies(monkeypatch, handler)
    REAL_OSRM_REQUEST([BKK, CNX])
    assert seen["url"] == "http://osrm.test/route/v1/driving/100.5018,13.7563;98.9853,18.7883"
    assert seen["params"]["alternatives"] == "3" and seen["params"]["geometries"] == "polyline"
    assert "annotations" not in seen["params"]
    assert routing.OSRM_TIMEOUT + routing.RISK_TIMEOUT < 45  # api-backend รอเรา 45 วิ ตัวในต้องสั้นกว่า


def test_missing_base_url_is_config_error(monkeypatch):
    monkeypatch.delenv("OSRM_BASE_URL")
    calls = _osrm_replies(monkeypatch, _ok)
    with pytest.raises(ApiError) as e:
        REAL_OSRM_REQUEST([BKK, CNX])
    assert e.value.code == "INTERNAL_ERROR" and "OSRM_BASE_URL" in e.value.message
    assert calls == []


def test_same_trip_hits_osrm_once(monkeypatch):
    calls = _osrm_replies(monkeypatch, _ok)
    REAL_OSRM_REQUEST([BKK, CNX])
    REAL_OSRM_REQUEST([routing.Place(lat=13.75631, lng=100.50179), CNX])  # ต่างกันไม่ถึงทศนิยม 3 ตำแหน่ง
    assert len(calls) == 1
    REAL_OSRM_REQUEST([BKK, NSN, CNX])
    assert len(calls) == 2


def test_failed_reply_is_not_cached(monkeypatch):
    replies = iter([httpx.Response(502, text="bad"), _ok()])
    calls = _osrm_replies(monkeypatch, lambda *a: next(replies))
    with pytest.raises(ApiError):
        REAL_OSRM_REQUEST([BKK, CNX])
    assert REAL_OSRM_REQUEST([BKK, CNX])["code"] == "Ok"
    assert len(calls) == 2


def test_cached_reply_builds_fresh_routes(monkeypatch):
    """plan_routes() เขียน points/stop_idx ลงใน dict ของเส้น คำขอถัดไปต้องไม่เห็นของคำขอก่อน"""
    _osrm_replies(monkeypatch, _ok)
    monkeypatch.setattr(routing, "osrm_request", REAL_OSRM_REQUEST)
    first = routing.fetch_routes([BKK, CNX])
    first[0]["points"] = ["stale"]
    first[0]["geometry"].clear()
    again = routing.fetch_routes([BKK, CNX])
    assert "points" not in again[0] and len(again[0]["geometry"]) == 500


def test_slow_osrm_times_out_fast_then_next_try_is_cached(monkeypatch):
    monkeypatch.setattr(routing, "OSRM_TIMEOUT", 0.2)

    def slow(*a):
        time.sleep(0.5)
        return _ok()

    calls = _osrm_replies(monkeypatch, slow)
    started = time.monotonic()
    with pytest.raises(ApiError) as e:
        REAL_OSRM_REQUEST([BKK, CNX])
    assert e.value.code == "UPSTREAM_TIMEOUT" and time.monotonic() - started < 0.4
    with pytest.raises(ApiError):
        REAL_OSRM_REQUEST([BKK, CNX])  # ยังโหลดไม่เสร็จ ต้องรอตัวเดิม ไม่ยิงซ้ำ
    time.sleep(0.5)
    assert REAL_OSRM_REQUEST([BKK, CNX])["code"] == "Ok"
    assert len(calls) == 1


def test_osrm_error_reaches_client_as_envelope(monkeypatch):
    def down(stops):
        raise ApiError("UPSTREAM_ERROR", "ติดต่อระบบหาเส้นทางไม่ได้ ลองใหม่อีกครั้ง")

    monkeypatch.setattr(routing, "osrm_request", down)
    from fastapi.testclient import TestClient
    res = TestClient(routing.app).post("/api/v1/routes/plan", json={
        "origin": {"lat": 13.7563, "lng": 100.5018}, "destination": {"lat": 18.7883, "lng": 98.9853},
        "departure_time": "2030-01-01T01:00:00Z"})
    assert res.status_code == 502
    assert res.json() == {"data": None, "error": {"code": "UPSTREAM_ERROR",
                                                  "message": "ติดต่อระบบหาเส้นทางไม่ได้ ลองใหม่อีกครั้ง"}}
