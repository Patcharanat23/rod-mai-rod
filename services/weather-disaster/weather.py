"""Hourly forecast from Open-Meteo for points along a route."""
import math
import threading
import time
from datetime import datetime, timezone

import httpx

from geo import to_iso

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY_VARS = "precipitation,wind_speed_10m,temperature_2m,weather_code"
TIMEOUT_S = 8
CACHE_TTL_S = 30 * 60
CACHE_MAX = 5000
AREA_STEP_KM = 25
KM_PER_DEG_LAT = 111.32

# WMO weather codes used by Open-Meteo
WMO_TH = {
    0: "ท้องฟ้าแจ่มใส",
    1: "ท้องฟ้าโปร่ง",
    2: "มีเมฆบางส่วน",
    3: "เมฆมาก",
    45: "มีหมอก",
    48: "มีหมอกน้ำแข็ง",
    51: "ฝนปรอยเล็กน้อย",
    53: "ฝนปรอย",
    55: "ฝนปรอยหนาแน่น",
    56: "ฝนปรอยเยือกแข็ง",
    57: "ฝนปรอยเยือกแข็ง",
    61: "ฝนตกเล็กน้อย",
    63: "ฝนตกปานกลาง",
    65: "ฝนตกหนัก",
    66: "ฝนเยือกแข็ง",
    67: "ฝนเยือกแข็งหนัก",
    71: "หิมะตกเล็กน้อย",
    73: "หิมะตก",
    75: "หิมะตกหนัก",
    77: "เกล็ดหิมะ",
    80: "ฝนตกเป็นช่วงๆ",
    81: "ฝนตกเป็นช่วงปานกลาง",
    82: "ฝนตกหนักมาก",
    85: "หิมะตกเป็นช่วงๆ",
    86: "หิมะตกหนักเป็นช่วงๆ",
    95: "พายุฝนฟ้าคะนอง",
    96: "พายุฝนฟ้าคะนองมีลูกเห็บ",
    99: "พายุฝนฟ้าคะนองมีลูกเห็บหนัก",
}
UNKNOWN_TH = "ไม่ทราบสภาพอากาศ"


def condition_th(code) -> str:
    if code is None:
        return UNKNOWN_TH
    return WMO_TH.get(int(code), UNKNOWN_TH)


def hour_key(t: datetime) -> str:
    """Floor to the hour in UTC, formatted like Open-Meteo hourly.time with timezone=GMT."""
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:00")


def fetch_hourly(coords: list[tuple[float, float]]) -> list[dict]:
    """One request for all coordinates. Returns hourly blocks in the same order."""
    params = {
        "latitude": ",".join(f"{lat:.4f}" for lat, _ in coords),
        "longitude": ",".join(f"{lng:.4f}" for _, lng in coords),
        "hourly": HOURLY_VARS,
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
        "temperature_unit": "celsius",
        "timezone": "GMT",
    }
    res = httpx.get(OPEN_METEO_URL, params=params, timeout=TIMEOUT_S)
    res.raise_for_status()
    body = res.json()
    # a single location comes back as an object, several as a list
    locations = body if isinstance(body, list) else [body]
    if len(locations) != len(coords):
        raise ValueError("Open-Meteo returned a different number of locations")
    return [loc["hourly"] for loc in locations]


def pick_hour(hourly: dict, t: datetime) -> tuple[dict | None, str | None]:
    """Forecast for the hour containing t. Returns (forecast, warning)."""
    times = hourly.get("time") or []
    key = hour_key(t)
    if key not in times:
        return None, "FORECAST_OUT_OF_RANGE"
    i = times.index(key)
    try:
        rain = hourly["precipitation"][i]
        wind = hourly["wind_speed_10m"][i]
        temp = hourly["temperature_2m"][i]
        code = hourly["weather_code"][i]
    except (KeyError, IndexError, TypeError):
        return None, "WEATHER_UNAVAILABLE"
    if rain is None or wind is None or temp is None:
        return None, "WEATHER_UNAVAILABLE"
    forecast = {
        "time": to_iso(datetime.strptime(key, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)),
        "rain_mm_per_h": round(float(rain), 1),
        "wind_kmh": round(float(wind), 1),
        "temp_c": round(float(temp), 1),
        "condition_th": condition_th(code),
    }
    return forecast, None


# rounded coords -> (stored_at, hourly block). One block holds every forecast hour,
# so a later request for another hour at the same place is still a hit.
_cache: dict[tuple[float, float], tuple[float, dict]] = {}
_lock = threading.Lock()
_now = time.monotonic


def cache_key(lat: float, lng: float) -> tuple[float, float]:
    """2 decimals is about 1 km; nearby points share one forecast."""
    return (round(lat, 2), round(lng, 2))


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def _cache_get(key, now: float) -> dict | None:
    with _lock:
        item = _cache.get(key)
    if item and now - item[0] < CACHE_TTL_S:
        return item[1]
    return None


def _cache_put(key, hourly: dict, now: float) -> None:
    with _lock:
        if len(_cache) >= CACHE_MAX:
            for k in [k for k, (t, _) in _cache.items() if now - t >= CACHE_TTL_S]:
                del _cache[k]
            if len(_cache) >= CACHE_MAX:
                _cache.clear()
        _cache[key] = (now, hourly)


def forecast_points(points: list[tuple[float, float, datetime]]) -> tuple[list[dict | None], list[str]]:
    """Same order and same count as the input. Unknown data is None plus a warning."""
    if not points:
        return [], []
    now = _now()
    keys = [cache_key(lat, lng) for lat, lng, _ in points]
    blocks: dict = {}
    missing = []
    for key in dict.fromkeys(keys):  # unique, order kept
        hourly = _cache_get(key, now)
        if hourly is None:
            missing.append(key)
        else:
            blocks[key] = hourly

    warnings: list[str] = []
    if missing:
        try:
            fetched = fetch_hourly(missing)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            warnings.append("WEATHER_UNAVAILABLE")
        else:
            for key, hourly in zip(missing, fetched):
                _cache_put(key, hourly, now)
                blocks[key] = hourly

    results: list[dict | None] = []
    for (_, _, t), key in zip(points, keys):
        hourly = blocks.get(key)
        if hourly is None:
            results.append(None)
            continue
        forecast, warning = pick_hour(hourly, t)
        results.append(forecast)
        if warning and warning not in warnings:
            warnings.append(warning)
    return results, warnings


def area_grid(lat: float, lng: float) -> list[tuple[float, float]]:
    """3x3 cells about AREA_STEP_KM apart, south-west first, the centre is index 4."""
    dlat = AREA_STEP_KM / KM_PER_DEG_LAT
    # a degree of longitude shrinks towards the poles
    dlng = AREA_STEP_KM / (KM_PER_DEG_LAT * max(math.cos(math.radians(lat)), 0.01))
    return [
        (round(lat + dy * dlat, 4), round(lng + dx * dlng, 4))
        for dy in (-1, 0, 1) for dx in (-1, 0, 1)
    ]
