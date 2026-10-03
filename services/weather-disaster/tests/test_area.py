from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

import weather
from app import app
from geo import haversine_km

client = TestClient(app)


def hourly_around_now(offset: float = 0.0) -> dict:
    """Hourly series from 2 hours ago to 2 days ahead, like Open-Meteo with timezone=GMT."""
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=2)
    hours = 50
    return {
        "time": [(start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(hours)],
        "precipitation": [offset + i for i in range(hours)],
        "wind_speed_10m": [12.0] * hours,
        "temperature_2m": [31.0] * hours,
        "weather_code": [61] * hours,
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
    state = {"calls": [], "down": False}

    def fake_get(url, params=None, timeout=None):
        if state["down"]:
            raise httpx.ConnectTimeout("timeout")
        n = len(params["latitude"].split(","))
        state["calls"].append(n)
        blocks = [{"hourly": hourly_around_now(1000 * i)} for i in range(n)]
        return FakeResponse(blocks[0] if n == 1 else blocks)

    monkeypatch.setattr(weather.httpx, "get", fake_get)
    return state


def get_area(lat=18.79, lng=98.98):
    res = client.get("/api/v1/area", params={"lat": lat, "lng": lng})
    return res.status_code, res.json()


def test_nine_cells_about_25_km_apart(open_meteo):
    status, body = get_area()
    assert status == 200
    cells = body["data"]["cells"]
    assert len(cells) == 9
    assert (cells[4]["lat"], cells[4]["lng"]) == (18.79, 98.98)
    for a, b in [(3, 4), (4, 5), (1, 4), (4, 7)]:
        assert 24 <= haversine_km(cells[a], cells[b]) <= 26


def test_one_request_for_all_nine_cells(open_meteo):
    get_area()
    assert open_meteo["calls"] == [9]


def test_second_call_is_served_from_cache(open_meteo):
    get_area()
    get_area()
    assert open_meteo["calls"] == [9]


def test_values_are_for_the_current_hour(open_meteo):
    _, body = get_area()
    data = body["data"]
    updated = datetime.strptime(data["updated_at"], "%Y-%m-%dT%H:%M:%SZ")
    expected_hour = updated.strftime("%Y-%m-%dT%H:00:00Z")
    for cell in data["cells"]:
        assert cell["forecast"]["time"] == expected_hour
        assert cell["forecast"]["condition_th"] == weather.condition_th(61, cell["forecast"]["rain_mm_per_h"])
    assert data["warnings"] == []
    assert data["center"] == {"lat": 18.79, "lng": 98.98}


def test_open_meteo_down_gives_empty_cells_not_error(open_meteo):
    open_meteo["down"] = True
    status, body = get_area()
    assert status == 200
    assert body["error"] is None
    assert body["data"]["cells"] == []
    assert body["data"]["warnings"] == ["WEATHER_UNAVAILABLE"]


def test_only_cells_with_data_are_returned(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        n = len(params["latitude"].split(","))
        blocks = [{"hourly": hourly_around_now(1000 * i)} for i in range(n)]
        blocks[0]["hourly"]["precipitation"] = [None] * len(blocks[0]["hourly"]["time"])
        return FakeResponse(blocks)

    monkeypatch.setattr(weather.httpx, "get", fake_get)
    _, body = get_area()
    cells = body["data"]["cells"]
    assert len(cells) == 8
    assert all(c["forecast"] is not None for c in cells)
    assert (cells[3]["lat"], cells[3]["lng"]) == (18.79, 98.98)
    assert body["data"]["warnings"] == ["WEATHER_UNAVAILABLE"]


def test_missing_lng_is_rejected(open_meteo):
    res = client.get("/api/v1/area", params={"lat": 13.75})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_grid_spacing_holds_in_the_south():
    cells = [{"lat": la, "lng": ln} for la, ln in weather.area_grid(6.5, 101.3)]
    assert 24 <= haversine_km(cells[3], cells[4]) <= 26
    assert 24 <= haversine_km(cells[1], cells[4]) <= 26
