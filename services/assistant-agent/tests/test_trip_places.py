"""8.8: ทริปที่ใกล้ที่สุด + สร้างทริป / แก้ต้นทาง ปลายทาง จุดแวะ / แนะนำที่เที่ยว จากแชท"""
from datetime import datetime, timezone

import rules
import tools
from envelope import ApiError
from test_rules import AUTH, FakeBackend, trip

NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)
PLACES = {
    "กรุงเทพ": {"name": "กรุงเทพมหานคร", "lat": 13.75, "lng": 100.5},
    "เชียงใหม่": {"name": "เชียงใหม่", "lat": 18.79, "lng": 98.98},
    "นครสวรรค์": {"name": "นครสวรรค์", "lat": 15.7, "lng": 100.14},
    "ลำปาง": {"name": "ลำปาง", "lat": 18.29, "lng": 99.49},
}
BKK, CNX = PLACES["กรุงเทพ"], PLACES["เชียงใหม่"]


def full(no, departure, **extra):
    return {**trip(no, departure), "origin": BKK, "destination": CNX, "waypoints": [], **extra}


class PlacesBackend(FakeBackend):
    """FakeBackend + ค้นสถานที่ ที่เที่ยวใกล้ตัว และสร้างทริป"""

    def __call__(self, method, path, auth, json=None, params=None):
        if path == "/api/v1/places/search":
            self.calls.append((method, path, params))
            hit = PLACES.get(params["q"])
            return {"places": [hit] if hit else []}
        if path == "/api/v1/places/nearby":
            self.calls.append((method, path, params))
            return {"places": [{"name": "ประตูท่าแพ", "kind_th": "สถานที่ท่องเที่ยว", "lat": 18.78, "lng": 98.99}]}
        if method == "POST" and path == "/api/v1/trips":
            self.calls.append((method, path, json))
            new = {**json, "trip_id": "id-9", "trip_no": 9, "plan_status": "NONE", "plan": None}
            self.trips["id-9"] = new
            return new
        return super().__call__(method, path, auth, json)


def run(name, args, be):
    return tools.run(name, args, be, AUTH)


# ---------- ทริปที่ใกล้ที่สุด ----------

def test_rules_move_nearest_trip_picks_next_upcoming_one():
    # Trip 1 ออกไปแล้ว, Trip 3 ออกทีหลัง Trip 2 > "ทริปที่ใกล้ที่สุด" = Trip 2
    be = FakeBackend([full(1, "2029-12-30T01:00:00Z"), full(2, "2030-01-03T01:00:00Z"), full(3, "2030-01-09T01:00:00Z")])
    out = rules.try_rules("เลื่อนทริปที่ใกล้ที่สุดไปพรุ่งนี้", AUTH, be, now=NOW)
    assert ("PATCH", "/api/v1/trips/id-2", {"departure_time": "2030-01-04T01:00:00Z"}) in be.calls
    assert out["actions"][0]["trip_no"] == 2


def test_without_nearest_word_still_asks_which_trip():
    be = FakeBackend([full(1, "2030-01-03T01:00:00Z"), full(2, "2030-01-09T01:00:00Z")])
    out = rules.try_rules("เลื่อนทริปไปพรุ่งนี้", AUTH, be, now=NOW)
    assert "หมายถึงทริปไหน" in out["reply"] and not be.patched()


def test_context_marks_nearest_trip_and_thai_time():
    text = tools.context_text([full(1, "2029-12-30T01:00:00Z"), full(2, "2030-01-03T01:00:00Z")], now=NOW)
    assert "2030-01-01 07:00" in text  # เวลาไทย
    assert "Trip 02 (ทริปที่ใกล้ที่สุด): กรุงเทพมหานคร > เชียงใหม่ ออก 3 ม.ค. 08:00 น." in text
    assert "Trip 01 (ทริปที่ใกล้ที่สุด)" not in text


# ---------- สร้างทริป ----------

def test_create_trip_resolves_names_then_plans():
    be = PlacesBackend([])
    out, actions = run("create_trip", {"origin": "กรุงเทพ", "destination": "เชียงใหม่", "date": "2099-01-05",
                                       "time": "12:00", "stops": ["นครสวรรค์"]}, be)
    body = next(c[2] for c in be.calls if c[:2] == ("POST", "/api/v1/trips"))
    assert body == {"origin": BKK, "destination": CNX, "departure_time": "2099-01-05T05:00:00Z",
                    "waypoints": [PLACES["นครสวรรค์"]]}
    assert ("POST", "/api/v1/trips/id-9/plan", None) in be.calls
    assert out["created"] and out["route_th"] == "กรุงเทพมหานคร > นครสวรรค์ > เชียงใหม่"
    assert out["plan"]["risk_th"] == "ต่ำ"
    assert actions == [{"type": "TRIP_CREATED", "trip_id": "id-9", "trip_no": 9}]


def test_create_trip_unknown_place_asks_instead_of_creating():
    be = PlacesBackend([])
    out, actions = run("create_trip", {"origin": "กรุงเทพ", "destination": "เมืองลับแล", "date": "2099-01-05", "time": "12:00"}, be)
    assert "ไม่เจอ" in out["error"] and actions == []
    assert not any(c[:2] == ("POST", "/api/v1/trips") for c in be.calls)


def test_create_trip_needs_date_and_time_and_future():
    be = PlacesBackend([])
    out, _ = run("create_trip", {"origin": "กรุงเทพ", "destination": "เชียงใหม่", "date": "2099-01-05"}, be)
    assert "เวลาออก" in out["error"]
    out, _ = run("create_trip", {"origin": "กรุงเทพ", "destination": "เชียงใหม่", "date": "2000-01-05", "time": "09:00"}, be)
    assert "ผ่านไปแล้ว" in out["error"]


# ---------- แก้ต้นทาง ปลายทาง จุดแวะ ----------

def test_update_places_changes_only_given_fields_then_plans():
    be = PlacesBackend([full(1, "2099-01-05T01:00:00Z", waypoints=[PLACES["นครสวรรค์"]])])
    out, actions = run("update_trip_places", {"trip_no": 1, "destination": "ลำปาง", "stops": []}, be)
    assert be.patched() == [{"destination": PLACES["ลำปาง"], "waypoints": []}]
    assert out["route_th"] == "กรุงเทพมหานคร > ลำปาง"
    assert ("POST", "/api/v1/trips/id-1/plan", None) in be.calls
    assert actions == [{"type": "TRIP_UPDATED", "trip_id": "id-1", "trip_no": 1}]


def test_update_places_rejects_more_than_five_stops():
    be = PlacesBackend([full(1, "2099-01-05T01:00:00Z")])
    out, actions = run("update_trip_places", {"trip_no": 1, "stops": ["ลำปาง"] * 6}, be)
    assert "ไม่เกิน 5" in out["error"] and actions == [] and not be.patched()


# ---------- แนะนำที่เที่ยว ----------

def test_nearby_places_returns_real_places_around_named_city():
    out, actions = run("nearby_places", {"place": "เชียงใหม่"}, PlacesBackend([]))
    assert out == {"around": "เชียงใหม่", "places": [{"name": "ประตูท่าแพ", "kind_th": "สถานที่ท่องเที่ยว"}]}
    assert actions == []


def test_nearby_places_asks_again_once_after_first_timeout():
    class SlowOnce(PlacesBackend):
        slow = True

        def __call__(self, method, path, auth, json=None, params=None):
            if path == "/api/v1/places/nearby" and self.slow:
                self.slow = False
                raise ApiError("UPSTREAM_TIMEOUT", "ยังโหลดไม่เสร็จ")
            return super().__call__(method, path, auth, json, params)

    out, _ = run("nearby_places", {"place": "เชียงใหม่"}, SlowOnce([]))
    assert out["places"][0]["name"] == "ประตูท่าแพ"
