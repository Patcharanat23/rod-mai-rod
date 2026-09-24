import app as routing
from conftest import saved
from geo import haversine_km

BKK = routing.Place(lat=13.7563, lng=100.5018)
NSN = routing.Place(lat=15.7047, lng=100.1372)
CNX = routing.Place(lat=18.7883, lng=98.9853)


def straight(km: int) -> list[tuple[float, float]]:
    """เส้นตรงขึ้นเหนือ จุดห่างกัน 1 กม. ใช้ทดสอบค่าที่รู้คำตอบแน่นอน"""
    return [(13.0 + i / 111.195, 100.0) for i in range(km + 1)]


def test_samples_every_step_and_skip_near_stop():
    samples = routing.sample_points(straight(100), [0, 100], [{"duration": 6000}])  # 100 กม. 100 นาที
    assert [round(s["minute"], 3) for s in samples] == [20, 40, 60, 80]  # 100 ห่างปลายไม่ถึง 10 กม. ข้าม
    assert abs(samples[0]["lat"] - (13.0 + 20 / 111.195)) < 1e-6 and samples[0]["lng"] == 100.0


def test_sample_minute_follows_leg_duration_by_distance():
    samples = routing.sample_points(straight(100), [0, 100], [{"duration": 6600}])  # 110 นาที
    assert round(samples[0]["minute"], 3) == 22


def test_short_leg_has_no_samples():
    assert routing.sample_points(straight(25), [0, 25], [{"duration": 1500}]) == []


def test_count_restarts_at_each_stop():
    points = straight(70)
    samples = routing.sample_points(points, [0, 35, 70], [{"duration": 2100}, {"duration": 4200}])
    # leg 2 เริ่มนับใหม่ที่หมุด (35 นาที) จุดแรกที่ 20 กม. ของ leg 2 = 20/35 ของ 70 นาที
    assert [round(s["minute"], 3) for s in samples] == [20, 35 + 40]


def test_leg_bounds_find_waypoint_on_the_road():
    body = saved([BKK, NSN, CNX])
    points = routing.decode_polyline(body["routes"][0]["geometry"])
    bounds = routing.leg_bounds(points, [w["location"] for w in body["waypoints"]])
    assert bounds[0] == 0 and bounds[-1] == len(points) - 1
    lat, lng = points[bounds[1]]
    assert haversine_km({"lat": lat, "lng": lng}, {"lat": NSN.lat, "lng": NSN.lng}) < 1


def test_real_route_samples_about_every_20_km_on_the_road():
    for r in routing.fetch_routes([BKK, CNX]):
        samples = r["samples"]
        assert 30 <= len(samples) <= 36  # 685-713 กม.
        chain = [{"lat": BKK.lat, "lng": BKK.lng}, *samples, {"lat": CNX.lat, "lng": CNX.lng}]
        gaps = [haversine_km(a, b) for a, b in zip(chain, chain[1:])]
        assert max(gaps) <= 31  # เส้นตรงสั้นกว่าระยะถนนเสมอ ช่วงท้ายยาวได้ถึง 1.5 step
        minutes = [s["minute"] for s in samples]
        assert minutes == sorted(minutes) and 0 < minutes[0] and minutes[-1] < r["stop_minutes"][-1]


def test_samples_lie_on_the_road():
    body = saved([BKK, CNX])
    road = routing.decode_polyline(body["routes"][0]["geometry"])
    for s in routing.fetch_routes([BKK, CNX])[0]["samples"]:
        nearest = min(haversine_km(s, {"lat": lat, "lng": lng}) for lat, lng in road[::5])
        assert nearest < 1.5  # ไม่ใช่ลากเส้นตรงระหว่างหมุด


def test_samples_stay_inside_their_leg_with_waypoint():
    (r,) = routing.fetch_routes([BKK, NSN, CNX])
    _, to_nsn, to_cnx = r["stop_minutes"]
    before = [s for s in r["samples"] if s["minute"] < to_nsn]
    after = [s for s in r["samples"] if s["minute"] > to_nsn]
    assert len(before) + len(after) == len(r["samples"])
    assert 10 <= len(before) <= 12 and 20 <= len(after) <= 22  # 241 กม. และ 451 กม.
    nsn = {"lat": NSN.lat, "lng": NSN.lng}
    assert all(haversine_km(s, nsn) > 5 for s in r["samples"])  # ไม่ซ้ำกับหมุด
    assert after[-1]["minute"] < to_cnx


def test_risk_points_mixes_samples_and_stops_in_time_order():
    stops = [BKK, NSN, CNX]
    (r,) = routing.fetch_routes(stops)
    points, idx = routing.risk_points(r, stops, routing.datetime.fromisoformat("2030-01-01T01:00:00+00:00"))
    assert len(points) == len(stops) + len(r["samples"])
    assert [p["eta"] for p in points] == sorted(p["eta"] for p in points)
    assert idx[0] == 0 and idx[-1] == len(points) - 1
    assert (points[idx[1]]["lat"], points[idx[1]]["lng"]) == (NSN.lat, NSN.lng)
    assert all(p["eta"].endswith("Z") for p in points)
