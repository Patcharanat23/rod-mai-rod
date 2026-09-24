from datetime import datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

import weather
from app import app

client = TestClient(app)
START = datetime(2026, 9, 28, 0, 0)


def fake_hourly(offset: float = 0.0, hours: int = 48) -> dict:
    """Values change every hour so a test can tell which hour was picked."""
    times = [(START + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(hours)]
    return {
        "time": times,
        "precipitation": [offset + i for i in range(hours)],
        "wind_speed_10m": [offset + 100 + i for i in range(hours)],
        "temperature_2m": [offset + 20 + i * 0.1 for i in range(hours)],
        "weather_code": [63] * hours,
    }


class FakeResponse:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self._body


@pytest.fixture
def open_meteo(monkeypatch):
    """Replace the network call. Each location gets offset = 1000 * its index."""
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(params)
        n = len(params["latitude"].split(","))
        blocks = [{"hourly": fake_hourly(offset=1000 * i)} for i in range(n)]
        return FakeResponse(blocks[0] if n == 1 else blocks)

    monkeypatch.setattr(weather.httpx, "get", fake_get)
    return calls


def post(points):
    res = client.post("/api/v1/forecast/points", json={"points": points})
    return res.status_code, res.json()


def test_picks_hour_of_each_point_not_current(open_meteo):
    status, body = post([{"lat": 13.75, "lng": 100.5, "time": "2026-09-28T03:40:00Z"}])
    assert status == 200
    fc = body["data"]["points"][0]["forecast"]
    assert fc["time"] == "2026-09-28T03:00:00Z"
    assert fc["rain_mm_per_h"] == 3
    assert fc["wind_kmh"] == 103
    assert body["data"]["warnings"] == []


def test_local_timezone_is_converted_to_utc(open_meteo):
    # 10:40 in Bangkok is 03:40 UTC
    _, body = post([{"lat": 13.75, "lng": 100.5, "time": "2026-09-28T10:40:00+07:00"}])
    assert body["data"]["points"][0]["forecast"]["time"] == "2026-09-28T03:00:00Z"


def test_order_and_count_preserved_with_one_request(open_meteo):
    pts = [
        {"lat": 13.75, "lng": 100.50, "time": "2026-09-28T01:00:00Z"},
        {"lat": 15.70, "lng": 100.13, "time": "2026-09-28T05:00:00Z"},
        {"lat": 18.79, "lng": 98.98, "time": "2026-09-28T09:00:00Z"},
    ]
    _, body = post(pts)
    out = body["data"]["points"]
    assert len(out) == 3
    assert [(p["lat"], p["lng"]) for p in out] == [(p["lat"], p["lng"]) for p in pts]
    assert [p["forecast"]["rain_mm_per_h"] for p in out] == [1, 1005, 2009]
    assert len(open_meteo) == 1


def test_out_of_range_gives_null_and_warning(open_meteo):
    pts = [
        {"lat": 13.75, "lng": 100.5, "time": "2026-09-28T02:00:00Z"},
        {"lat": 18.79, "lng": 98.98, "time": "2026-10-20T02:00:00Z"},
    ]
    _, body = post(pts)
    out = body["data"]["points"]
    assert out[0]["forecast"] is not None
    assert out[1]["forecast"] is None
    assert body["data"]["warnings"] == ["FORECAST_OUT_OF_RANGE"]


def test_missing_values_give_null_not_fake(monkeypatch):
    hourly = fake_hourly()
    hourly["precipitation"][2] = None
    monkeypatch.setattr(weather.httpx, "get", lambda *a, **k: FakeResponse({"hourly": hourly}))
    _, body = post([{"lat": 13.75, "lng": 100.5, "time": "2026-09-28T02:10:00Z"}])
    assert body["data"]["points"][0]["forecast"] is None
    assert body["data"]["warnings"] == ["WEATHER_UNAVAILABLE"]


def test_open_meteo_down_still_answers(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectTimeout("timeout")

    monkeypatch.setattr(weather.httpx, "get", boom)
    pts = [
        {"lat": 13.75, "lng": 100.5, "time": "2026-09-28T02:00:00Z"},
        {"lat": 18.79, "lng": 98.98, "time": "2026-09-28T08:00:00Z"},
    ]
    status, body = post(pts)
    assert status == 200
    assert body["error"] is None
    assert [p["forecast"] for p in body["data"]["points"]] == [None, None]
    assert body["data"]["warnings"] == ["WEATHER_UNAVAILABLE"]


def test_empty_points_makes_no_request(open_meteo):
    _, body = post([])
    assert body["data"] == {"points": [], "warnings": []}
    assert open_meteo == []


def test_time_without_timezone_is_rejected(open_meteo):
    status, body = post([{"lat": 13.75, "lng": 100.5, "time": "2026-09-28T02:00:00"}])
    assert status == 400
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_request_asks_for_kmh_and_gmt(open_meteo):
    post([{"lat": 13.75, "lng": 100.5, "time": "2026-09-28T02:00:00Z"}])
    params = open_meteo[0]
    assert params["wind_speed_unit"] == "kmh"
    assert params["timezone"] == "GMT"


def test_condition_th():
    assert weather.condition_th(65) == "ฝนตกหนัก"
    assert weather.condition_th(0) == "ท้องฟ้าแจ่มใส"
    assert weather.condition_th(12345) == "ไม่ทราบสภาพอากาศ"
    assert weather.condition_th(None) == "ไม่ทราบสภาพอากาศ"
