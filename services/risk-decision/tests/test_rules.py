import pytest

from app import decide, rain_level, score_in_band, wind_level, worst
from geo import score_to_level


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
