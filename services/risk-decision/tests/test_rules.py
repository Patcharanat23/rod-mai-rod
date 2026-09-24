import pytest

from app import (decide, hazard_severity, nearby_hazards, point_level, point_severity, rain_level,
                  rain_severity, score_in_band, wind_level, wind_severity, worst)
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
