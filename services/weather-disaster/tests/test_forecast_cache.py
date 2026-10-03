from datetime import datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

import weather
from app import app

client = TestClient(app)
START = datetime(2026, 9, 28, 0, 0)


def hourly(offset: float = 0.0, hours: int = 48) -> dict:
    return {
        "time": [(START + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(hours)],
        "precipitation": [offset + i for i in range(hours)],
        "wind_speed_10m": [10.0] * hours,
        "temperature_2m": [30.0] * hours,
        "weather_code": [3] * hours,
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
    """Records the latitudes of every request. Location i gets offset 1000 * i."""
    state = {"calls": [], "down": False}

    def fake_get(url, params=None, timeout=None):
        if state["down"]:
            raise httpx.ConnectTimeout("timeout")
        lats = params["latitude"].split(",")
        state["calls"].append(lats)
        blocks = [{"hourly": hourly(1000 * i)} for i in range(len(lats))]
        return FakeResponse(blocks[0] if len(lats) == 1 else blocks)

    monkeypatch.setattr(weather.httpx, "get", fake_get)
    return state


def post(points):
    return client.post("/api/v1/forecast/points", json={"points": points}).json()["data"]


BKK = {"lat": 13.75, "lng": 100.50, "time": "2026-09-28T01:00:00Z"}
NSN = {"lat": 15.70, "lng": 100.13, "time": "2026-09-28T05:00:00Z"}


def test_second_request_is_served_from_cache(open_meteo):
    first = post([BKK, NSN])
    second = post([BKK, NSN])
    assert len(open_meteo["calls"]) == 1
    assert first == second


def test_other_hour_at_same_place_is_a_hit(open_meteo):
    post([BKK])
    data = post([{**BKK, "time": "2026-09-28T09:00:00Z"}])
    assert len(open_meteo["calls"]) == 1
    assert data["points"][0]["forecast"]["time"] == "2026-09-28T09:00:00Z"


def test_nearby_points_are_requested_once(open_meteo):
    near = {"lat": 13.7512, "lng": 100.4991, "time": "2026-09-28T02:00:00Z"}
    data = post([BKK, NSN, near])
    assert open_meteo["calls"] == [["13.7500", "15.7000"]]
    out = data["points"]
    assert len(out) == 3
    assert (out[2]["lat"], out[2]["lng"]) == (13.7512, 100.4991)
    assert out[2]["forecast"]["rain_mm_per_h"] == 2


def test_only_missing_points_are_fetched(open_meteo):
    post([BKK])
    post([BKK, NSN])
    assert open_meteo["calls"] == [["13.7500"], ["15.7000"]]


def test_cache_expires_after_30_minutes(open_meteo, monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(weather, "_now", lambda: clock["t"])
    post([BKK])
    clock["t"] += 29 * 60
    post([BKK])
    assert len(open_meteo["calls"]) == 1
    clock["t"] += 2 * 60
    post([BKK])
    assert len(open_meteo["calls"]) == 2


def test_failure_is_not_cached(open_meteo):
    open_meteo["down"] = True
    data = post([BKK])
    assert data["points"][0]["forecast"] is None
    assert data["warnings"] == ["WEATHER_UNAVAILABLE"]
    open_meteo["down"] = False
    data = post([BKK])
    assert data["points"][0]["forecast"] is not None
    assert data["warnings"] == []


def test_cached_points_survive_when_open_meteo_is_down(open_meteo):
    post([BKK])
    open_meteo["down"] = True
    data = post([BKK, NSN])
    assert data["points"][0]["forecast"] is not None
    assert data["points"][1]["forecast"] is None
    assert data["warnings"] == ["WEATHER_UNAVAILABLE"]
