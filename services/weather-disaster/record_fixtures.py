"""Record real responses for DEMO_MODE. Needs internet.

Reads the demo routes saved by routing-engine, then stores the Open-Meteo forecast for
points every STEP_KM along every route, the 3x3 area around each demo city, and the
current GDACS and USGS feeds, all under fixtures/.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

import hazard_feeds
import weather
from geo import haversine_km, to_iso

HERE = Path(__file__).resolve().parent
ROUTE_FIXTURES = HERE.parent / "routing-engine" / "fixtures"
STEP_KM = 10
BATCH = 50
FEED_TIMEOUT_S = 30
# Bangkok, Nakhon Sawan, Chiang Mai
CITIES = [(13.756, 100.502), (15.705, 100.137), (18.788, 98.985)]


def decode_polyline(text: str, precision: int = 5) -> list[tuple[float, float]]:
    """Google encoded polyline, as OSRM returns with geometries=polyline."""
    coords, index, lat, lng = [], 0, 0, 0
    factor = 10 ** precision
    while index < len(text):
        for is_lng in (False, True):
            shift, result = 0, 0
            while True:
                byte = ord(text[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if is_lng:
                lng += delta
            else:
                lat += delta
        coords.append((lat / factor, lng / factor))
    return coords


def sample(line: list[tuple[float, float]], step_km: float) -> list[tuple[float, float]]:
    """First point, then one point each time the distance along the line passes step_km."""
    if not line:
        return []
    out = [line[0]]
    since = 0.0
    for a, b in zip(line, line[1:]):
        since += haversine_km({"lat": a[0], "lng": a[1]}, {"lat": b[0], "lng": b[1]})
        if since >= step_km:
            out.append(b)
            since = 0.0
    if out[-1] != line[-1]:
        out.append(line[-1])
    return out


def route_lines(data: dict) -> list[list[tuple[float, float]]]:
    lines = []
    for route in data.get("routes") or []:
        geom = route.get("geometry")
        if isinstance(geom, str):
            lines.append(decode_polyline(geom))
        elif isinstance(geom, dict):
            lines.append([(lat, lng) for lng, lat in geom.get("coordinates", [])])
    return lines


def demo_keys() -> list[tuple[float, float]]:
    points = []
    for path in sorted(ROUTE_FIXTURES.glob("*.json")):
        for line in route_lines(json.loads(path.read_text(encoding="utf-8"))):
            points.extend(sample(line, STEP_KM))
    for lat, lng in CITIES:
        points.extend(weather.area_grid(lat, lng))
    return list(dict.fromkeys(weather.cache_key(lat, lng) for lat, lng in points))


def write_json(name: str, data) -> None:
    path = weather.FIXTURES / name
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{name}: {path.stat().st_size // 1024} KB")


def main() -> None:
    keys = demo_keys()
    print(f"route files: {len(list(ROUTE_FIXTURES.glob('*.json')))}, points to record: {len(keys)}")
    weather.FIXTURES.mkdir(exist_ok=True)

    points = {}
    for i in range(0, len(keys), BATCH):
        batch = keys[i:i + BATCH]
        for (lat, lng), hourly in zip(batch, weather.fetch_hourly(batch)):
            points[f"{lat:.2f}_{lng:.2f}"] = hourly
    recorded_at = to_iso(datetime.now(timezone.utc))
    write_json("forecast.json", {"recorded_at": recorded_at, "points": points})

    gdacs = httpx.get(hazard_feeds.GDACS_URL, timeout=FEED_TIMEOUT_S)
    gdacs.raise_for_status()
    write_json("gdacs.json", gdacs.json())

    usgs = httpx.get(hazard_feeds.USGS_URL, params=hazard_feeds.usgs_params(), timeout=FEED_TIMEOUT_S)
    usgs.raise_for_status()
    write_json("usgs.json", usgs.json())


if __name__ == "__main__":
    main()
