from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

import hazard_feeds
import landslide
import weather
from app import app

client = TestClient(app)
THAILAND = {"min_lat": 5.6, "min_lng": 97.3, "max_lat": 20.5, "max_lng": 105.7}
NORTH_ONLY = {"min_lat": 18.4, "min_lng": 98.3, "max_lat": 18.6, "max_lng": 98.4}  # Mae Chaem


def hourly_from_now(mm_per_hour: float, hours: int = 72) -> dict:
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=2)
    return {
        "time": [(start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(hours)],
        "precipitation": [mm_per_hour] * hours,
        "wind_speed_10m": [5.0] * hours,
        "temperature_2m": [24.0] * hours,
        "weather_code": [65] * hours,
    }


class FakeResponse:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self._body


@pytest.fixture
def rain(monkeypatch):
    """Open-Meteo with the same rain everywhere; GDACS, USGS and rain pins return nothing."""
    state = {"mm": 0.0, "calls": 0, "down": False}

    def fake_get(url, params=None, timeout=None):
        if state["down"]:
            raise httpx.ConnectTimeout("timeout")
        state["calls"] += 1
        n = len(params["latitude"].split(","))
        blocks = [{"hourly": hourly_from_now(state["mm"])} for _ in range(n)]
        return FakeResponse(blocks[0] if n == 1 else blocks)

    monkeypatch.setattr(weather.httpx, "get", fake_get)
    monkeypatch.setattr(hazard_feeds, "fetch_gdacs", lambda box: [])
    monkeypatch.setattr(hazard_feeds, "fetch_usgs", lambda box: [])
    monkeypatch.setattr(hazard_feeds, "current_weather", lambda box: [])
    return state


def hazards(box):
    return client.get("/api/v1/hazards", params=box).json()["data"]


def test_peak_is_the_wettest_24_hours_within_3_days():
    now = datetime.now(timezone.utc)
    hourly = hourly_from_now(1.0, hours=120)
    first = hourly["time"].index(weather.hour_key(now))
    for i in range(first + 30, first + 54):  # a wet day starting 30 hours from now
        hourly["precipitation"][i] = 5.0
    mm, at = landslide.peak_rain(hourly, now)
    assert mm == 120.0
    assert at.strftime("%Y-%m-%dT%H:%M") == hourly["time"][first + 30]


def test_rain_after_3_days_is_ignored():
    now = datetime.now(timezone.utc)
    hourly = hourly_from_now(0.0, hours=150)
    first = hourly["time"].index(weather.hour_key(now))
    for i in range(first + 80, first + 104):
        hourly["precipitation"][i] = 10.0
    mm, _ = landslide.peak_rain(hourly, now)
    assert mm == 0.0


def test_peak_is_none_when_hours_are_missing():
    hourly = hourly_from_now(2.0, hours=10)
    assert landslide.peak_rain(hourly, datetime.now(timezone.utc)) is None


def test_thai_date_uses_thai_time():
    assert landslide.thai_date(datetime(2026, 9, 25, 21, 0, tzinfo=timezone.utc)) == "26 ก.ย."


def test_severity_levels():
    assert landslide.severity_for(49.9) is None
    assert landslide.severity_for(50) == "LOW"
    assert landslide.severity_for(100) == "MEDIUM"
    assert landslide.severity_for(150) == "HIGH"


def test_heavy_rain_on_hills_gives_estimated_pins(rain):
    rain["mm"] = 6.5  # 156 mm in 24 h
    data = hazards(THAILAND)
    pins = data["hazards"]
    assert len(pins) == len(landslide.HILL_POINTS)
    pin = next(p for p in pins if p["hazard_id"] == "derived-landslide-mae-chaem")
    assert pin["hazard_type"] == "LANDSLIDE_RISK"
    assert pin["source"] == "DERIVED"
    assert pin["severity"] == "HIGH"
    assert "ประเมิน" in pin["title_th"] and "156" in pin["title_th"] and "ช่วง" in pin["title_th"]
    assert pin["province"] == "เชียงใหม่"
    assert pin["updated_at"].endswith(":00:00Z")
    assert data["warnings"] == []


def test_light_rain_gives_no_pins(rain):
    rain["mm"] = 1.0  # 24 mm
    data = hazards(THAILAND)
    assert data["hazards"] == []
    assert data["warnings"] == []


def test_only_hill_points_in_the_box(rain):
    rain["mm"] = 4.5  # 108 mm
    pins = hazards(NORTH_ONLY)["hazards"]
    assert [p["hazard_id"] for p in pins] == ["derived-landslide-mae-chaem"]
    assert pins[0]["severity"] == "MEDIUM"


def test_box_without_hills_makes_no_forecast_request(rain):
    landslide.landslide_hazards((13.5, 100.3, 13.9, 100.7))  # Bangkok
    assert rain["calls"] == 0


def test_one_forecast_request_for_all_hills(rain):
    rain["mm"] = 3.0
    hazards(THAILAND)
    assert rain["calls"] == 1


def test_open_meteo_down_is_a_warning_and_other_feeds_still_return(rain, monkeypatch):
    rain["down"] = True
    flood = {"hazard_id": "gdacs-FL-1", "hazard_type": "FLOOD", "severity": "MEDIUM",
             "lat": 15.7, "lng": 100.13, "province": None, "title_th": "น้ำท่วม",
             "source": "GDACS", "updated_at": "2026-09-24T00:00:00Z"}
    monkeypatch.setattr(hazard_feeds, "fetch_gdacs", lambda box: [flood])
    data = hazards(THAILAND)
    assert [h["hazard_id"] for h in data["hazards"]] == ["gdacs-FL-1"]
    assert data["warnings"] == ["HAZARD_FEED_UNAVAILABLE"]


def test_every_hill_point_is_inside_thailand():
    from geo import in_thailand
    assert all(in_thailand(lat, lng) for _, lat, lng, _ in landslide.HILL_POINTS)
