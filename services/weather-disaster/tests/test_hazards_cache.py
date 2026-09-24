import pytest
from fastapi.testclient import TestClient

import hazard_feeds
from app import app

client = TestClient(app)
THAILAND = {"min_lat": 5.6, "min_lng": 97.3, "max_lat": 20.5, "max_lng": 105.7}
NAKHON_SAWAN = {"min_lat": 15.0, "min_lng": 99.5, "max_lat": 16.5, "max_lng": 101.0}


def pin(hid, lat, lng, source):
    return {"hazard_id": hid, "hazard_type": "FLOOD", "severity": "MEDIUM", "lat": lat, "lng": lng,
            "province": None, "title_th": "น้ำท่วม", "source": source, "updated_at": "2026-09-24T00:00:00Z"}


@pytest.fixture
def sources(monkeypatch):
    """Counts calls per source; a source listed in state["down"] raises."""
    state = {"calls": {"gdacs": 0, "usgs": 0, "landslide": 0}, "down": set(), "boxes": []}

    def make(name, pins):
        def fn(box):
            state["calls"][name] += 1
            state["boxes"].append(box)
            if name in state["down"]:
                raise RuntimeError(f"{name} down")
            return pins
        return fn

    monkeypatch.setattr(hazard_feeds, "fetch_gdacs", make("gdacs", [pin("gdacs-1", 15.7, 100.13, "GDACS")]))
    monkeypatch.setattr(hazard_feeds, "fetch_usgs", make("usgs", [pin("usgs-1", 19.9, 99.8, "USGS")]))
    monkeypatch.setattr(hazard_feeds, "derived_landslide", make("landslide", [pin("ls-1", 14.74, 98.63, "DERIVED")]))
    return state


def get(box):
    return client.get("/api/v1/hazards", params=box).json()["data"]


def ids(data):
    return sorted(h["hazard_id"] for h in data["hazards"])


def test_second_request_is_served_from_cache(sources):
    first = get(THAILAND)
    second = get(THAILAND)
    assert first == second
    assert ids(first) == ["gdacs-1", "ls-1", "usgs-1"]
    assert sources["calls"] == {"gdacs": 1, "usgs": 1, "landslide": 1}


def test_other_box_uses_the_same_cache_and_is_filtered(sources):
    get(THAILAND)
    data = get(NAKHON_SAWAN)
    assert ids(data) == ["gdacs-1"]
    assert sources["calls"] == {"gdacs": 1, "usgs": 1, "landslide": 1}


def test_sources_are_fetched_for_the_whole_area(sources):
    get(NAKHON_SAWAN)
    assert all(box == hazard_feeds.ALL_BOX for box in sources["boxes"])


def test_cache_expires_after_10_minutes(sources, monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(hazard_feeds, "_now", lambda: clock["t"])
    get(THAILAND)
    clock["t"] += 9 * 60
    get(THAILAND)
    assert sources["calls"]["gdacs"] == 1
    clock["t"] += 2 * 60
    get(THAILAND)
    assert sources["calls"]["gdacs"] == 2


def test_failed_source_is_not_cached_as_empty(sources):
    sources["down"].add("gdacs")
    data = get(THAILAND)
    assert ids(data) == ["ls-1", "usgs-1"]
    assert data["warnings"] == ["HAZARD_FEED_UNAVAILABLE"]

    sources["down"].clear()
    data = get(THAILAND)
    assert ids(data) == ["gdacs-1", "ls-1", "usgs-1"]
    assert data["warnings"] == []
    # only the failed source was asked again
    assert sources["calls"] == {"gdacs": 2, "usgs": 1, "landslide": 1}


def test_demo_and_live_results_are_not_mixed(sources, monkeypatch):
    get(THAILAND)
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setattr(hazard_feeds, "demo_gdacs", lambda box: [])
    monkeypatch.setattr(hazard_feeds, "demo_usgs", lambda box: [])
    get(THAILAND)
    assert sources["calls"]["landslide"] == 2
