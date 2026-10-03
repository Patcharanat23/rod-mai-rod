"""Rain and wind pins from the current hour on a grid of land points over Thailand."""
from datetime import datetime, timezone

import weather

GRID_STEP_DEG = 0.6
# rough outline of Thailand (lat, lng), clockwise from Mae Sai; only used to keep grid points on land
THAILAND_OUTLINE = [
    (20.45, 99.90), (20.26, 100.40), (19.60, 101.20), (18.40, 101.10), (17.80, 101.60),
    (17.90, 102.70), (18.30, 103.70), (17.40, 104.80), (16.50, 104.75), (15.30, 105.60),
    (14.35, 105.20), (14.40, 103.00), (14.30, 102.40), (13.70, 102.50), (12.90, 102.70),
    (12.00, 102.90), (11.65, 102.90), (12.20, 102.30), (12.50, 102.10), (12.65, 101.30),
    (12.65, 100.90), (13.35, 100.95), (13.50, 100.50), (13.40, 100.00), (12.70, 100.00),
    (12.50, 99.95), (11.80, 99.80), (10.50, 99.20), (9.30, 99.40), (8.40, 100.00),
    (7.20, 100.60), (6.90, 101.30), (6.40, 101.80), (6.00, 102.10), (5.65, 101.20),
    (6.40, 100.20), (6.60, 100.00), (7.40, 99.40), (8.10, 98.90), (7.90, 98.30),
    (8.90, 98.25), (9.90, 98.50), (10.40, 98.75), (11.50, 99.40), (12.20, 99.10),
    (13.00, 99.15), (14.00, 98.60), (15.30, 98.30), (16.30, 98.60), (16.70, 98.50),
    (17.80, 97.80), (18.50, 97.60), (19.70, 97.80), (20.10, 98.90), (20.35, 99.50),
]

# thresholds from docs/CONTRACT.md
RAIN_MIN = 2.0
RAIN_MEDIUM = 10.0
RAIN_HEAVY = 35.0
WIND_MEDIUM = 40.0
WIND_HIGH = 61.0


def on_land(lat: float, lng: float) -> bool:
    """Ray casting against THAILAND_OUTLINE."""
    inside = False
    pts = THAILAND_OUTLINE
    for (lat1, lng1), (lat2, lng2) in zip(pts, pts[1:] + pts[:1]):
        if (lat1 > lat) != (lat2 > lat):
            cross = lng1 + (lat - lat1) * (lng2 - lng1) / (lat2 - lat1)
            if lng < cross:
                inside = not inside
    return inside


def thailand_grid(step: float = GRID_STEP_DEG) -> list[tuple[float, float]]:
    out = []
    lat = 5.7
    while lat <= 20.5:
        lng = 97.4
        while lng <= 105.7:
            if on_land(lat, lng):
                out.append((round(lat, 2), round(lng, 2)))
            lng += step
        lat += step
    return out


GRID = thailand_grid()


def pins_for(lat: float, lng: float, forecast: dict) -> list[dict]:
    """0, 1 or 2 pins (rain and wind) for one grid point; nothing below the thresholds."""
    base = {"lat": lat, "lng": lng, "province": None, "source": "OPEN_METEO", "updated_at": forecast["time"]}
    key = f"{lat:.2f}_{lng:.2f}"
    rain, wind = forecast["rain_mm_per_h"], forecast["wind_kmh"]
    out = []
    if rain > RAIN_HEAVY:
        out.append({**base, "hazard_id": f"openmeteo-rain-{key}", "hazard_type": "HEAVY_RAIN",
                    "severity": "HIGH", "title_th": f"ฝนตกหนัก {rain:.1f} มม./ชม."})
    elif rain >= RAIN_MIN:
        level = "MEDIUM" if rain >= RAIN_MEDIUM else "LOW"
        out.append({**base, "hazard_id": f"openmeteo-rain-{key}", "hazard_type": "RAIN",
                    "severity": level, "title_th": f"ฝนตก {rain:.1f} มม./ชม."})
    if wind >= WIND_MEDIUM:
        level = "HIGH" if wind > WIND_HIGH else "MEDIUM"
        out.append({**base, "hazard_id": f"openmeteo-wind-{key}", "hazard_type": "STRONG_WIND",
                    "severity": level, "title_th": f"ลมแรง {wind:.0f} กม./ชม."})
    return out


def weather_hazards(box) -> list[dict]:
    min_lat, min_lng, max_lat, max_lng = box
    points = [p for p in GRID if min_lat <= p[0] <= max_lat and min_lng <= p[1] <= max_lng]
    if not points:
        return []
    blocks, _ = weather.hourly_blocks(points)
    if all(b is None for b in blocks):
        raise RuntimeError("no forecast for the grid")

    now = datetime.now(timezone.utc)
    out = []
    for (lat, lng), hourly in zip(points, blocks):
        if hourly is None:
            continue
        forecast, _ = weather.pick_hour(hourly, now)
        if forecast is not None:
            out.extend(pins_for(lat, lng, forecast))
    return out
