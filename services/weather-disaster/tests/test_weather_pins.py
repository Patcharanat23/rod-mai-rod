from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

import hazard_feeds
import weather
import weather_pins
from app import app
from geo import in_thailand

client = TestClient(app)
THAILAND = {"min_lat": 5.6, "min_lng": 97.3, "max_lat": 20.5, "max_lng": 105.7}


def forecast(rain: float, wind: float) -> dict:
    return {"time": "2026-09-25T05:00:00Z", "rain_mm_per_h": rain, "wind_kmh": wind,
            "temp_c": 28.0, "condition_th": "ฝนตก"}


def hourly_now(rain: float, wind: float, hours: int = 48) -> dict:
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=2)
    return {
        "time": [(start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(hours)],
        "precipitation": [rain] * hours,
        "wind_speed_10m": [wind] * hours,
        "temperature_2m": [28.0] * hours,
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
def sky(monkeypatch):
    """Open-Meteo with the same weather everywhere; other hazard sources return nothing."""
    state = {"rain": 0.0, "wind": 0.0, "calls": [], "down": False}

    def fake_get(url, params=None, timeout=None):
        if state["down"]:
            raise httpx.ConnectTimeout("timeout")
        n = len(params["latitude"].split(","))
        state["calls"].append(n)
        blocks = [{"hourly": hourly_now(state["rain"], state["wind"])} for _ in range(n)]
        return FakeResponse(blocks[0] if n == 1 else blocks)

    monkeypatch.setattr(weather.httpx, "get", fake_get)
    monkeypatch.setattr(hazard_feeds, "fetch_gdacs", lambda box: [])
    monkeypatch.setattr(hazard_feeds, "fetch_usgs", lambda box: [])
    monkeypatch.setattr(hazard_feeds, "derived_landslide", lambda box: [])
    return state


def hazards(box=THAILAND):
    return client.get("/api/v1/hazards", params=box).json()["data"]


def test_grid_is_on_land_inside_thailand():
    assert 80 <= len(weather_pins.GRID) <= 200
    assert all(in_thailand(lat, lng) for lat, lng in weather_pins.GRID)
    for lat, lng in [(13.75, 100.5), (18.79, 98.98), (7.0, 100.47), (15.24, 104.85)]:
        assert weather_pins.on_land(lat, lng)
    # gulf, Andaman sea, Laos, Cambodia, Myanmar
    for lat, lng in [(11.0, 101.0), (8.0, 97.5), (19.89, 102.13), (13.36, 103.86), (16.8, 96.15)]:
        assert not weather_pins.on_land(lat, lng)


@pytest.mark.parametrize("rain,kind,level", [
    (2.0, "RAIN", "LOW"), (9.9, "RAIN", "LOW"), (10.0, "RAIN", "MEDIUM"),
    (35.0, "RAIN", "MEDIUM"), (35.1, "HEAVY_RAIN", "HIGH"),
])
def test_rain_levels_follow_contract(rain, kind, level):
    [pin] = weather_pins.pins_for(15.0, 100.0, forecast(rain, 5.0))
    assert (pin["hazard_type"], pin["severity"]) == (kind, level)
    assert pin["source"] == "OPEN_METEO"


@pytest.mark.parametrize("wind,level", [(40.0, "MEDIUM"), (61.0, "MEDIUM"), (61.1, "HIGH")])
def test_wind_levels_follow_contract(wind, level):
    [pin] = weather_pins.pins_for(15.0, 100.0, forecast(0.0, wind))
    assert (pin["hazard_type"], pin["severity"]) == ("STRONG_WIND", level)
    assert "ลมแรง" in pin["title_th"]


def test_below_thresholds_gives_no_pin():
    assert weather_pins.pins_for(15.0, 100.0, forecast(1.9, 39.9)) == []


def test_rain_and_wind_at_one_point_give_two_pins():
    pins = weather_pins.pins_for(15.0, 100.0, forecast(20.0, 50.0))
    assert sorted(p["hazard_type"] for p in pins) == ["RAIN", "STRONG_WIND"]
    assert len({p["hazard_id"] for p in pins}) == 2


def test_rain_now_gives_pins_on_the_map(sky):
    sky["rain"] = 12.0
    data = hazards()
    pins = data["hazards"]
    assert len(pins) == len(weather_pins.GRID)
    assert {(p["hazard_type"], p["severity"], p["source"]) for p in pins} == {("RAIN", "MEDIUM", "OPEN_METEO")}
    now_hour = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:00:00Z")
    assert all(p["updated_at"] == now_hour for p in pins)
    assert data["warnings"] == []


def test_dry_calm_hour_gives_no_pins(sky):
    sky["rain"], sky["wind"] = 0.5, 10.0
    assert hazards()["hazards"] == []


def test_whole_grid_in_one_request(sky):
    hazards()
    assert sky["calls"] == [len(weather_pins.GRID)]


def test_only_pins_inside_the_box(sky):
    sky["rain"] = 5.0
    box = {"min_lat": 13.0, "min_lng": 100.0, "max_lat": 14.5, "max_lng": 101.5}
    pins = hazards(box)["hazards"]
    assert pins
    assert all(13.0 <= p["lat"] <= 14.5 and 100.0 <= p["lng"] <= 101.5 for p in pins)


def test_open_meteo_down_is_a_warning_not_an_error(sky):
    sky["down"] = True
    data = hazards()
    assert data["hazards"] == []
    assert data["warnings"] == ["HAZARD_FEED_UNAVAILABLE"]
