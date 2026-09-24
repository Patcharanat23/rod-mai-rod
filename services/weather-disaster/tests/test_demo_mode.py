import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import hazard_feeds
import record_fixtures
import weather
from app import app

client = TestClient(app)
RECORDED_DAY = datetime(2026, 1, 10)  # far from today, so the shift is exercised


def recorded_hourly(offset: float = 0.0) -> dict:
    """7 days from 00:00 of the day it was recorded, like Open-Meteo."""
    hours = 7 * 24
    return {
        "time": [(RECORDED_DAY + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(hours)],
        "precipitation": [offset + i for i in range(hours)],
        "wind_speed_10m": [8.0] * hours,
        "temperature_2m": [29.0] * hours,
        "weather_code": [65] * hours,
    }


@pytest.fixture
def demo(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setattr(weather, "FIXTURES", tmp_path)
    monkeypatch.setattr(hazard_feeds, "FIXTURES", tmp_path)

    def no_network(*a, **k):
        raise AssertionError("DEMO_MODE must not touch the network")

    monkeypatch.setattr(weather.httpx, "get", no_network)
    points = {"13.76_100.50": recorded_hourly(0), "18.79_98.98": recorded_hourly(1000)}
    (tmp_path / "forecast.json").write_text(json.dumps({"points": points}), encoding="utf-8")
    gdacs = {"features": [{
        "type": "Feature", "geometry": {"type": "Point", "coordinates": [100.13, 15.70]},
        "properties": {"eventtype": "FL", "eventid": 9, "alertlevel": "Orange",
                       "iscurrent": "true", "datemodified": "2026-09-24T02:00:00"},
    }]}
    usgs = {"features": [{
        "id": "q1", "geometry": {"type": "Point", "coordinates": [99.8, 19.9, 10]},
        "properties": {"mag": 4.6, "time": 1790220626013},
    }]}
    (tmp_path / "gdacs.json").write_text(json.dumps(gdacs), encoding="utf-8")
    (tmp_path / "usgs.json").write_text(json.dumps(usgs), encoding="utf-8")
    return tmp_path


def today_at(hour: int, days: int = 0) -> str:
    d = datetime.now(timezone.utc).replace(hour=hour, minute=20, second=0, microsecond=0) + timedelta(days=days)
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def forecast(points):
    return client.post("/api/v1/forecast/points", json={"points": points}).json()["data"]


def test_forecast_comes_from_fixture_shifted_to_today(demo):
    data = forecast([{"lat": 13.7563, "lng": 100.5018, "time": today_at(5)}])
    fc = data["points"][0]["forecast"]
    assert fc["time"] == today_at(5).replace(":20:00Z", ":00:00Z")
    assert fc["rain_mm_per_h"] == 5
    assert data["warnings"] == []


def test_nearest_recorded_point_is_used(demo):
    # about 8 km from the Chiang Mai point
    data = forecast([{"lat": 18.84, "lng": 99.04, "time": today_at(2, days=1)}])
    assert data["points"][0]["forecast"]["rain_mm_per_h"] == 1000 + 24 + 2


def test_point_far_from_fixtures_is_null_with_warning(demo):
    data = forecast([{"lat": 7.88, "lng": 98.39, "time": today_at(5)}])  # Phuket
    assert data["points"][0]["forecast"] is None
    assert data["warnings"] == ["WEATHER_UNAVAILABLE"]


def test_beyond_recorded_days_is_out_of_range(demo):
    data = forecast([{"lat": 13.75, "lng": 100.50, "time": today_at(5, days=10)}])
    assert data["points"][0]["forecast"] is None
    assert data["warnings"] == ["FORECAST_OUT_OF_RANGE"]


def test_area_works_in_demo(demo):
    res = client.get("/api/v1/area", params={"lat": 18.79, "lng": 98.98}).json()["data"]
    assert 1 <= len(res["cells"]) <= 9
    assert all(c["forecast"] is not None for c in res["cells"])


def test_hazards_come_from_fixtures(demo):
    box = {"min_lat": 5.6, "min_lng": 97.3, "max_lat": 20.5, "max_lng": 105.7}
    data = client.get("/api/v1/hazards", params=box).json()["data"]
    ids = sorted(h["hazard_id"] for h in data["hazards"])
    assert ids == ["gdacs-FL-9", "usgs-q1"]
    assert data["warnings"] == []


def test_missing_hazard_fixture_is_a_warning(demo):
    (demo / "usgs.json").unlink()
    box = {"min_lat": 5.6, "min_lng": 97.3, "max_lat": 20.5, "max_lng": 105.7}
    data = client.get("/api/v1/hazards", params=box).json()["data"]
    assert [h["hazard_id"] for h in data["hazards"]] == ["gdacs-FL-9"]
    assert data["warnings"] == ["HAZARD_FEED_UNAVAILABLE"]


def test_missing_forecast_fixture_is_a_warning(demo):
    (demo / "forecast.json").unlink()
    data = forecast([{"lat": 13.75, "lng": 100.50, "time": today_at(5)}])
    assert data["points"][0]["forecast"] is None
    assert data["warnings"] == ["WEATHER_UNAVAILABLE"]


def test_decode_polyline():
    assert record_fixtures.decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@") == [
        (38.5, -120.2), (40.7, -120.95), (43.252, -126.453),
    ]


def test_sample_keeps_both_ends_and_steps():
    line = [(13.0 + i * 0.01, 100.0) for i in range(101)]  # about 111 km north
    pts = record_fixtures.sample(line, 10)
    assert pts[0] == line[0] and pts[-1] == line[-1]
    assert 11 <= len(pts) <= 13
