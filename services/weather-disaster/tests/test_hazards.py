import httpx
import pytest
from fastapi.testclient import TestClient

import hazard_feeds
import landslide
from app import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def no_landslide(monkeypatch):
    """Landslide estimates have their own tests; keep these about GDACS and USGS."""
    monkeypatch.setattr(landslide, "landslide_hazards", lambda box: [])


THAILAND = {"min_lat": 5.6, "min_lng": 97.3, "max_lat": 20.5, "max_lng": 105.7}


def gdacs_feature(eventtype, eventid, level, lng, lat, current="true", geom_type="Point"):
    return {
        "type": "Feature",
        "geometry": {"type": geom_type, "coordinates": [lng, lat]},
        "properties": {
            "eventtype": eventtype, "eventid": eventid, "alertlevel": level,
            "iscurrent": current, "datemodified": "2026-09-24T02:07:03",
        },
    }


GDACS_BODY = {"features": [
    gdacs_feature("FL", 1, "Orange", 100.13, 15.70),            # Nakhon Sawan
    gdacs_feature("TC", 2, "Red", 99.0, 18.8),                  # Chiang Mai
    gdacs_feature("FL", 3, "Green", 102.8, 16.4),               # Khon Kaen
    gdacs_feature("TC", 4, "Orange", 83.7, 18.1),               # India, outside Thailand
    gdacs_feature("FL", 5, "Red", 100.5, 13.75, current="false"),
    gdacs_feature("EQ", 6, "Red", 100.5, 13.75),                # not a type we take from GDACS
    gdacs_feature("FL", 1, "Orange", 100.13, 15.70),            # duplicate
    gdacs_feature("FL", 7, "Red", 100.5, 13.75, geom_type="Polygon"),
    {"type": "Feature", "geometry": None, "properties": {"eventtype": "FL", "alertlevel": "Red"}},
]}


def quake(qid, mag, lng, lat):
    return {"id": qid, "geometry": {"type": "Point", "coordinates": [lng, lat, 10]},
            "properties": {"mag": mag, "time": 1790220626013, "updated": 1790221910040}}


USGS_BODY = {"features": [
    quake("near-border", 5.2, 97.0, 19.5),   # Myanmar side, inside widened box
    quake("small", 3.5, 99.0, 18.0),
]}


class FakeResponse:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self._body


@pytest.fixture
def feeds(monkeypatch):
    calls = {}

    def fake_get(url, params=None, timeout=None):
        if "gdacs" in url:
            calls["gdacs"] = url
            return FakeResponse(GDACS_BODY)
        calls["usgs"] = params
        return FakeResponse(USGS_BODY)

    monkeypatch.setattr(hazard_feeds.httpx, "get", fake_get)
    return calls


def get(box):
    res = client.get("/api/v1/hazards", params=box)
    return res.status_code, res.json()


def by_id(body):
    return {h["hazard_id"]: h for h in body["data"]["hazards"]}


def test_gdacs_mapped_and_filtered_to_thailand(feeds):
    status, body = get(THAILAND)
    assert status == 200
    gdacs = {k: v for k, v in by_id(body).items() if k.startswith("gdacs-")}
    assert set(gdacs) == {"gdacs-FL-1", "gdacs-TC-2", "gdacs-FL-3"}
    assert gdacs["gdacs-FL-1"]["hazard_type"] == "FLOOD"
    assert gdacs["gdacs-FL-1"]["severity"] == "MEDIUM"
    assert gdacs["gdacs-TC-2"]["hazard_type"] == "STORM"
    assert gdacs["gdacs-TC-2"]["severity"] == "HIGH"
    assert gdacs["gdacs-FL-3"]["severity"] == "LOW"
    assert all(h["source"] == "GDACS" for h in gdacs.values())
    assert gdacs["gdacs-FL-1"]["updated_at"] == "2026-09-24T02:07:03Z"


def test_lng_lat_swapped_to_lat_lng(feeds):
    _, body = get(THAILAND)
    h = by_id(body)["gdacs-FL-1"]
    assert (h["lat"], h["lng"]) == (15.70, 100.13)


def test_requested_box_filters(feeds):
    box = {"min_lat": 15.0, "min_lng": 99.5, "max_lat": 16.5, "max_lng": 101.0}
    _, body = get(box)
    assert list(by_id(body)) == ["gdacs-FL-1"]


def test_usgs_earthquake_near_border(feeds):
    wide = {"min_lat": 3.0, "min_lng": 95.0, "max_lat": 23.0, "max_lng": 108.0}
    _, body = get(wide)
    quakes = {k: v for k, v in by_id(body).items() if k.startswith("usgs-")}
    assert list(quakes) == ["usgs-near-border"]
    q = quakes["usgs-near-border"]
    assert q["hazard_type"] == "EARTHQUAKE"
    assert q["severity"] == "MEDIUM"
    assert q["source"] == "USGS"
    assert "5.2" in q["title_th"]
    assert (q["lat"], q["lng"]) == (19.5, 97.0)
    assert q["updated_at"].endswith("Z")


def test_usgs_query_is_thailand_widened_and_min_mag(feeds):
    get(THAILAND)
    p = feeds["usgs"]
    assert p["minmagnitude"] == 4.0
    assert p["minlongitude"] < 97.3 and p["maxlongitude"] > 105.7


def test_one_source_down_other_still_returns(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        if "gdacs" in url:
            raise httpx.ConnectTimeout("timeout")
        return FakeResponse(USGS_BODY)

    monkeypatch.setattr(hazard_feeds.httpx, "get", fake_get)
    wide = {"min_lat": 3.0, "min_lng": 95.0, "max_lat": 23.0, "max_lng": 108.0}
    status, body = get(wide)
    assert status == 200
    assert body["error"] is None
    assert list(by_id(body)) == ["usgs-near-border"]
    assert body["data"]["warnings"] == ["HAZARD_FEED_UNAVAILABLE"]


def test_all_sources_down_gives_empty_list_and_one_warning(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(hazard_feeds.httpx, "get", boom)
    status, body = get(THAILAND)
    assert status == 200
    assert body["data"] == {"hazards": [], "warnings": ["HAZARD_FEED_UNAVAILABLE"]}


def test_bad_json_from_a_source_is_a_warning_not_a_crash(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        if "gdacs" in url:
            return FakeResponse("not a dict")
        return FakeResponse(USGS_BODY)

    monkeypatch.setattr(hazard_feeds.httpx, "get", fake_get)
    status, body = get(THAILAND)
    assert status == 200
    assert body["data"]["warnings"] == ["HAZARD_FEED_UNAVAILABLE"]


def test_inverted_box_is_rejected(feeds):
    status, body = get({"min_lat": 20, "min_lng": 97, "max_lat": 10, "max_lng": 105})
    assert status == 400
    assert body["error"]["code"] == "VALIDATION_ERROR"
