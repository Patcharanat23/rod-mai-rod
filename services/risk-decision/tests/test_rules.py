import pytest

from app import (_risk_cause_th, _thai_time_th, _worst_point_and_distance, best_delay_hours, decide,
                  delayed_route_level, hazard_severity, nearby_hazards, point_level, point_severity,
                  rain_level, rain_severity, score_in_band, summary_text, wind_level, wind_severity, worst)
from geo import haversine_km, score_to_level

EARTH_DEG_KM = 111.194926644  # กม.ต่อ 1 องศาละติจูด (R * pi/180, R=6371 กม.)


def _point_north_of(base, km):
    """จุดที่ห่างจาก base ไปทางเหนือ km กม. (ระยะทางตามละติจูดตรงๆ วัดด้วย haversine ได้ตรงตัว)"""
    return {"lat": base["lat"] + km / EARTH_DEG_KM, "lng": base["lng"]}


@pytest.mark.parametrize("mm, level", [(0, "LOW"), (9.9, "LOW"), (10, "MEDIUM"), (35, "MEDIUM"), (35.1, "HIGH")])
def test_rain_edges(mm, level):
    assert rain_level(mm) == level


@pytest.mark.parametrize("kmh, level", [(39.9, "LOW"), (40, "MEDIUM"), (61, "MEDIUM"), (61.1, "HIGH")])
def test_wind_edges(kmh, level):
    assert wind_level(kmh) == level


@pytest.mark.parametrize("level", ["LOW", "MEDIUM", "HIGH"])
@pytest.mark.parametrize("severity", [0, 0.3, 0.5, 1])
def test_score_stays_in_band(level, severity):
    assert score_to_level(score_in_band(level, severity)) == level


def test_worst_ignores_missing_but_never_guesses_low():
    assert worst(["LOW", None, "MEDIUM"]) == "MEDIUM"
    assert worst([None, None]) is None


def route(rid, level, minutes):
    return {"route_id": rid, "risk_level": level, "duration_min": minutes}


def test_low_main_is_normal():
    assert decide([route("r1", "LOW", 100), route("r2", "LOW", 90)]) == ("r1", "NORMAL")


def test_safer_alternative_is_reroute():
    assert decide([route("r1", "HIGH", 100), route("r2", "MEDIUM", 140)]) == ("r2", "REROUTE")


def test_alternative_over_50_percent_slower_is_not_recommended():
    assert decide([route("r1", "HIGH", 100), route("r2", "LOW", 151)]) == ("r1", "AVOID")


def test_medium_without_alternative_is_normal():
    assert decide([route("r1", "MEDIUM", 100)]) == ("r1", "NORMAL")


def test_unknown_main_does_not_crash():
    assert decide([route("r1", None, 100), route("r2", "LOW", 110)]) == ("r1", "NORMAL")


BKK = {"lat": 13.7563, "lng": 100.5018}


def test_hazard_within_20km_counts():
    hazard = {**_point_north_of(BKK, 19), "severity": "MEDIUM", "hazard_id": "h1"}
    assert haversine_km(BKK, hazard) == pytest.approx(19, abs=0.1)
    assert nearby_hazards(BKK, [hazard]) == [hazard]


def test_hazard_beyond_20km_does_not_count():
    hazard = {**_point_north_of(BKK, 21), "severity": "MEDIUM", "hazard_id": "h2"}
    assert haversine_km(BKK, hazard) == pytest.approx(21, abs=0.1)
    assert nearby_hazards(BKK, [hazard]) == []


def test_hazard_medium_raises_point_at_least_medium():
    # ฝนลมเดี่ยวๆ คือ LOW แต่มีหมุด MEDIUM อยู่ใกล้ ต้องได้อย่างน้อย MEDIUM
    forecast = {"rain_mm_per_h": 2, "wind_kmh": 10}
    hazards = nearby_hazards(BKK, [{**_point_north_of(BKK, 5), "severity": "MEDIUM", "hazard_id": "h3"}])
    assert point_level(forecast, hazards) == "MEDIUM"


def test_hazard_high_10km_gives_high():
    # ตรง Definition of Done: จุดที่มีหมุดน้ำท่วม HIGH ห่าง 10 กม. ต้องได้ระดับ HIGH
    forecast = {"rain_mm_per_h": 2, "wind_kmh": 10}
    hazards = nearby_hazards(BKK, [{**_point_north_of(BKK, 10), "severity": "HIGH", "hazard_id": "h4"}])
    assert point_level(forecast, hazards) == "HIGH"


def test_point_level_without_forecast_ignores_hazards():
    # ไม่มีข้อมูลอากาศ = null เสมอ ไม่ว่าหมุดภัยจะมีหรือไม่
    hazards = [{**_point_north_of(BKK, 1), "severity": "HIGH", "hazard_id": "h5"}]
    assert point_level(None, hazards) is None


def test_point_level_no_nearby_hazard_uses_weather_only():
    forecast = {"rain_mm_per_h": 2, "wind_kmh": 10}
    assert point_level(forecast, []) == "LOW"


# --- 7.2: risk_score จากความรุนแรงจริง ---

def test_rain_severity_matches_readme_example():
    # ฝน 20 มม./ชม. อยู่กลางช่วง MEDIUM (10-35) ได้ severity ประมาณ 0.4 ตามตัวอย่างใน spec
    assert rain_severity(20) == pytest.approx(0.4)


def test_rain_severity_low_band_scales_to_top():
    assert rain_severity(0) == 0
    assert rain_severity(9.9) == pytest.approx(0.99)


def test_rain_severity_high_band_saturates_at_one():
    assert rain_severity(60) == pytest.approx(1.0)
    assert rain_severity(1000) == 1.0


def test_wind_severity_matches_own_band():
    assert wind_severity(0) == 0
    assert wind_severity(50.5) == pytest.approx(0.5)  # กลางช่วง MEDIUM (40-61)
    assert wind_severity(82) == pytest.approx(1.0)  # 61 + ความกว้างช่วง MEDIUM (21) = อิ่มตัว


@pytest.mark.parametrize("mm, level", [(0, "LOW"), (9.9, "LOW"), (10, "MEDIUM"), (35, "MEDIUM"), (35.1, "HIGH")])
def test_score_to_level_matches_rain_edges(mm, level):
    severity = rain_severity(mm)
    score = score_in_band(level, severity)
    assert score_to_level(score) == level


def test_hazard_severity_closer_hazard_is_more_severe():
    close = [{**_point_north_of(BKK, 2), "severity": "HIGH", "hazard_id": "hc"}]
    far = [{**_point_north_of(BKK, 19), "severity": "HIGH", "hazard_id": "hf"}]
    assert hazard_severity(BKK, close) > hazard_severity(BKK, far)
    assert hazard_severity(BKK, close) == pytest.approx(0.9, abs=0.01)
    assert hazard_severity(BKK, []) == 0.0


def test_point_severity_uses_worst_factor_not_a_constant():
    # ฝนเบา (LOW) แต่มีหมุด MEDIUM ใกล้ๆ ระดับรวมมาจากหมุด severity ก็ต้องมาจากหมุดด้วย ไม่ใช่ 0.3 ตายตัว
    forecast = {"rain_mm_per_h": 1, "wind_kmh": 5}
    near_hazard = nearby_hazards(BKK, [{**_point_north_of(BKK, 1), "severity": "MEDIUM", "hazard_id": "h6"}])
    far_hazard = nearby_hazards(BKK, [{**_point_north_of(BKK, 18), "severity": "MEDIUM", "hazard_id": "h7"}])
    level = point_level(forecast, near_hazard)
    assert level == "MEDIUM"
    near_severity = point_severity(forecast, near_hazard, BKK, level)
    far_severity = point_severity(forecast, far_hazard, BKK, level)
    assert near_severity > far_severity


def test_point_severity_ties_take_the_higher_value():
    # ฝนกับลมเสมอกันที่ MEDIUM แต่รุนแรงคนละระดับ ต้องได้ severity ของตัวที่รุนแรงกว่า (ปลอดภัยไว้ก่อน)
    forecast = {"rain_mm_per_h": 34, "wind_kmh": 41}  # ฝนเกือบสุดช่วง MEDIUM, ลมเพิ่งเข้าช่วง MEDIUM
    level = point_level(forecast, [])
    assert level == "MEDIUM"
    severity = point_severity(forecast, [], BKK, level)
    assert severity == pytest.approx(max(rain_severity(34), wind_severity(41)))
    assert severity == pytest.approx(rain_severity(34))


# --- 7.3: summary_th ---

def _point(base, km, eta, rain, wind, level, hazards=None):
    return {**_point_north_of(base, km), "eta": eta, "forecast": {"rain_mm_per_h": rain, "wind_kmh": wind},
            "hazards": hazards or [], "risk_level": level, "risk_score": 0}


def test_summary_low_is_reassuring_and_ignores_points():
    main = {"route_id": "r1", "duration_min": 100, "risk_level": "LOW", "points": []}
    assert summary_text(main, main, "NORMAL") == "สภาพอากาศตลอดเส้นทางปกติ เดินทางได้ตามปกติ"


def test_summary_none_when_no_forecast():
    main = {"route_id": "r1", "duration_min": 100, "risk_level": None, "points": []}
    assert summary_text(main, main, "NORMAL") == "ตอนนี้ประเมินความเสี่ยงไม่ได้ ข้อมูลสภาพอากาศไม่พร้อม"


def test_summary_null_route_mentions_forecast_range_when_flagged():
    # แก้จากทดสอบรวม 2026-09-25 ข้อ 2 (ส่วนแนะนำ): level null ทั้งเส้นเพราะเกินช่วงพยากรณ์ ต้องบอกแบบนี้
    # ไม่ใช่ "ข้อมูลสภาพอากาศไม่พร้อม" ซึ่งฟังดูเหมือน weather-disaster ล่ม
    main = {"route_id": "r1", "duration_min": 100, "risk_level": None, "points": []}
    summary = summary_text(main, main, "NORMAL", out_of_range=True)
    assert "เกินช่วงพยากรณ์" in summary
    assert len(summary) > 0


def test_summary_low_but_some_points_missing_does_not_claim_whole_route_normal():
    # แก้จากทดสอบรวม 2026-09-25 ข้อ 2: จุดที่มีข้อมูลเป็น LOW หมด แต่มีบางจุด null ห้ามบอกว่า
    # "ตลอดเส้นทางปกติ" (CONTRACT หัวข้อ 3 ห้ามถือว่าไม่มีข้อมูลเท่ากับปลอดภัย)
    p0 = _point(BKK, 0, "2026-09-24T02:40:00Z", 2, 10, "LOW")
    p1 = {**_point_north_of(BKK, 50), "eta": "2026-09-24T03:00:00Z", "forecast": None,
          "hazards": [], "risk_level": None, "risk_score": None}
    main = {"route_id": "r1", "duration_min": 100, "risk_level": "LOW", "points": [p0, p1]}
    summary = summary_text(main, main, "NORMAL")
    assert "ตลอดเส้นทางปกติ" not in summary
    assert "50 กม." in summary  # ระยะของช่วงแรกที่ไม่มีข้อมูล
    assert len(summary) > 0


def test_thai_time_conversion():
    assert _thai_time_th("2026-09-24T03:00:00Z") == "10:00 น."
    assert _thai_time_th("2026-09-24T20:00:00Z") == "3:00 น."  # ข้ามวัน UTC 20:00 = ไทย 03:00 วันถัดไป


def test_risk_cause_combines_tied_factors():
    point = {"risk_level": "HIGH", "forecast": {"rain_mm_per_h": 40, "wind_kmh": 70}, "hazards": []}
    assert _risk_cause_th(point) == "ฝนตกหนักและลมแรงจัด"


def test_worst_point_and_distance_finds_worst_and_measures_from_start():
    p0 = _point(BKK, 0, "2026-09-24T02:40:00Z", 2, 10, "LOW")
    p1 = _point(BKK, 20, "2026-09-24T03:00:00Z", 40, 10, "HIGH")
    main = {"route_id": "r1", "duration_min": 100, "risk_level": "HIGH", "points": [p0, p1]}
    point, distance = _worst_point_and_distance(main)
    assert point is p1
    assert distance == pytest.approx(20, abs=0.1)


def test_summary_reroute_names_cause_distance_time_and_delay():
    p0 = _point(BKK, 0, "2026-09-24T02:40:00Z", 2, 10, "LOW")
    p1 = _point(BKK, 20, "2026-09-24T03:00:00Z", 40, 10, "HIGH")
    main = {"route_id": "r1", "duration_min": 100, "risk_level": "HIGH", "points": [p0, p1]}
    recommended = {"route_id": "r2", "duration_min": 115, "risk_level": "LOW", "points": []}
    summary = summary_text(main, recommended, "REROUTE")
    assert "ฝนตกหนัก" in summary
    assert "20 กม." in summary
    assert "10:00 น." in summary
    assert "ช้ากว่าเดิม 15 นาที" in summary


def test_summary_avoid_and_delay_say_what_to_do():
    p1 = _point(BKK, 5, "2026-09-24T03:00:00Z", 40, 10, "HIGH")
    main = {"route_id": "r1", "duration_min": 100, "risk_level": "HIGH", "points": [p1]}
    assert "เลี่ยงการเดินทาง" in summary_text(main, main, "AVOID")
    assert "เลื่อนเวลา" in summary_text(main, main, "DELAY")


# --- 7.4: DELAY (เสริม) ---

def test_delayed_route_level_none_if_any_point_missing_forecast():
    # จุดเสี่ยงที่สุดดันเป็นจุดที่ไม่มีพยากรณ์พอดี ห้ามคิดว่าเส้นนี้ปลอดภัย (แก้รีวิว PR #40 ข้อ 1)
    forecasts = [{"rain_mm_per_h": 2, "wind_kmh": 10}, None]
    assert delayed_route_level(forecasts, [[], []]) is None


def test_delayed_route_level_worst_when_every_point_known():
    forecasts = [{"rain_mm_per_h": 2, "wind_kmh": 10}, {"rain_mm_per_h": 40, "wind_kmh": 10}]
    assert delayed_route_level(forecasts, [[], []]) == "HIGH"


def test_best_delay_hours_prefers_earlier_improvement():
    assert best_delay_hours("HIGH", {3: "MEDIUM", 6: "LOW"}) == 3
    assert best_delay_hours("HIGH", {3: "HIGH", 6: "MEDIUM"}) == 6
    assert best_delay_hours("HIGH", {3: "HIGH", 6: "HIGH"}) is None
    assert best_delay_hours("HIGH", {3: None, 6: "LOW"}) == 6


def test_decide_delay_before_avoid_when_no_reroute_and_delay_helps():
    results = [route("r1", "HIGH", 100)]  # เส้นเดียว ไม่มีทางเลือก reroute
    assert decide(results, {3: "MEDIUM", 6: "LOW"}) == ("r1", "DELAY")


def test_decide_falls_back_to_avoid_when_delay_does_not_help():
    results = [route("r1", "HIGH", 100)]
    assert decide(results, {3: "HIGH", 6: "HIGH"}) == ("r1", "AVOID")
    assert decide(results) == ("r1", "AVOID")  # ไม่ใส่ delay_levels เลย พฤติกรรมเดิมต้องเหมือนเดิม (ห้ามพัง)


def test_decide_reroute_still_wins_over_delay():
    results = [route("r1", "HIGH", 100), route("r2", "MEDIUM", 120)]
    # r2 ดีกว่าและช้าไม่เกิน 50% -> REROUTE ต้องชนะ ไม่ไปเช็ค DELAY เลยแม้เลื่อนแล้วจะดีขึ้นก็ตาม
    assert decide(results, {3: "LOW", 6: "LOW"}) == ("r2", "REROUTE")


def test_summary_delay_mentions_hours():
    p1 = _point(BKK, 3, "2026-09-24T03:00:00Z", 40, 10, "HIGH")
    main = {"route_id": "r1", "duration_min": 100, "risk_level": "HIGH", "points": [p1]}
    assert "3 ชม." in summary_text(main, main, "DELAY", delay_hours=3)
    assert len(summary_text(main, main, "DELAY")) > 0  # ไม่ใส่ delay_hours ก็ต้องไม่ว่างเปล่า


def test_summary_is_never_empty():
    cases = [
        {"route_id": "r1", "duration_min": 100, "risk_level": None, "points": []},
        {"route_id": "r1", "duration_min": 100, "risk_level": "LOW", "points": []},
        {"route_id": "r1", "duration_min": 100, "risk_level": "MEDIUM",
         "points": [_point(BKK, 3, "2026-09-24T03:00:00Z", 20, 10, "MEDIUM")]},
        {"route_id": "r1", "duration_min": 100, "risk_level": "HIGH",
         "points": [_point(BKK, 3, "2026-09-24T03:00:00Z", 40, 10, "HIGH")]},
    ]
    for main in cases:
        for recommendation in ["NORMAL", "REROUTE", "DELAY", "AVOID"]:
            assert len(summary_text(main, main, recommendation)) > 0
