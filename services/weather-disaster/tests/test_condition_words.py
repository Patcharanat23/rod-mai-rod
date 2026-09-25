import pytest

import weather


@pytest.mark.parametrize("code,rain,words", [
    (95, 2.5, "ฝนฟ้าคะนอง"),       # thunder with light rain: no "storm"
    (95, 9.9, "ฝนฟ้าคะนอง"),
    (95, 10.0, "พายุฝนฟ้าคะนอง"),
    (99, 40.0, "พายุฝนฟ้าคะนอง"),
    (82, 7.9, "ฝนปานกลาง"),        # "very heavy showers" code with moderate rain
    (63, 40.0, "ฝนหนักมาก"),
    (61, 0.3, "ฝนเล็กน้อย"),
    (65, 2.5, "ฝนปานกลาง"),
    (80, 10.0, "ฝนหนัก"),
    (51, 35.0, "ฝนหนัก"),
    (55, 35.1, "ฝนหนักมาก"),
])
def test_rain_and_thunder_words_follow_the_amount(code, rain, words):
    assert weather.condition_th(code, rain) == words


@pytest.mark.parametrize("code", [0, 1, 2, 3, 45, 48, 71])
def test_other_codes_keep_the_table_words(code):
    assert weather.condition_th(code, 0.0) == weather.WMO_TH[code]


def test_forecast_uses_the_rain_amount():
    hourly = {
        "time": ["2026-09-28T03:00"],
        "precipitation": [2.5],
        "wind_speed_10m": [10.0],
        "temperature_2m": [27.0],
        "weather_code": [95],
    }
    from datetime import datetime, timezone
    fc, warning = weather.pick_hour(hourly, datetime(2026, 9, 28, 3, 30, tzinfo=timezone.utc))
    assert warning is None
    assert fc["condition_th"] == "ฝนฟ้าคะนอง"
    assert fc["rain_mm_per_h"] == 2.5
