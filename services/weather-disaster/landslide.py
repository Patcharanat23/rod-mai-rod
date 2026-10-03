"""Estimated landslide risk from forecast rain at hilly places. Not an official warning."""
from datetime import datetime, timedelta, timezone

import weather
from geo import to_iso

WINDOW_H = 24
# look this far ahead for the wettest WINDOW_H hours; trips are planned days in advance
LOOKAHEAD_H = 72
# accumulated rain in WINDOW_H hours (mm), highest first; about 100 mm a day is the usual watch level
LEVELS = ((150.0, "HIGH"), (100.0, "MEDIUM"), (50.0, "LOW"))
THAI_TZ = timezone(timedelta(hours=7))
MONTHS_TH = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
             "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]

# hilly places with past landslides: (id, lat, lng, province)
HILL_POINTS = [
    ("mae-chaem", 18.50, 98.36, "เชียงใหม่"),
    ("doi-inthanon", 18.59, 98.49, "เชียงใหม่"),
    ("mae-sai", 20.43, 99.88, "เชียงราย"),
    ("bo-kluea", 19.15, 101.16, "น่าน"),
    ("pai", 19.36, 98.44, "แม่ฮ่องสอน"),
    ("laplae", 17.65, 100.03, "อุตรดิตถ์"),
    ("lom-kao", 16.88, 101.23, "เพชรบูรณ์"),
    ("umphang", 16.02, 98.86, "ตาก"),
    ("thong-pha-phum", 14.74, 98.63, "กาญจนบุรี"),
    ("ranong", 9.97, 98.64, "ระนอง"),
    ("kapong", 8.70, 98.43, "พังงา"),
    ("khiri-rat-nikhom", 9.03, 98.95, "สุราษฎร์ธานี"),
    ("khiri-wong", 8.43, 99.78, "นครศรีธรรมราช"),
    ("khao-phanom", 8.27, 98.92, "กระบี่"),
    ("betong", 5.77, 101.07, "ยะลา"),
]


def peak_rain(hourly: dict, start: datetime) -> tuple[float, datetime] | None:
    """Wettest WINDOW_H hours that begin within LOOKAHEAD_H of start: (mm, window start UTC)."""
    times = hourly.get("time") or []
    rain = hourly.get("precipitation") or []
    key = weather.hour_key(start)
    if key not in times:
        return None
    first = times.index(key)
    best = None
    for i in range(first, first + LOOKAHEAD_H - WINDOW_H + 1):
        window = rain[i:i + WINDOW_H]
        if len(window) < WINDOW_H or any(v is None for v in window):
            continue
        mm = float(sum(window))
        if best is None or mm > best[0]:
            best = (mm, i)
    if best is None:
        return None
    at = datetime.strptime(times[best[1]], "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
    return best[0], at


def severity_for(mm: float) -> str | None:
    for limit, level in LEVELS:
        if mm >= limit:
            return level
    return None


def thai_date(at: datetime) -> str:
    local = at.astimezone(THAI_TZ)
    return f"{local.day} {MONTHS_TH[local.month - 1]}"


def landslide_hazards(box) -> list[dict]:
    min_lat, min_lng, max_lat, max_lng = box
    points = [p for p in HILL_POINTS if min_lat <= p[1] <= max_lat and min_lng <= p[2] <= max_lng]
    if not points:
        return []
    blocks, _ = weather.hourly_blocks([(lat, lng) for _, lat, lng, _ in points])
    if all(b is None for b in blocks):
        raise RuntimeError("no forecast for any hill point")

    now = datetime.now(timezone.utc)
    updated = to_iso(now.replace(minute=0, second=0, microsecond=0))
    out = []
    for (pid, lat, lng, province), hourly in zip(points, blocks):
        peak = peak_rain(hourly, now) if hourly else None
        level = severity_for(peak[0]) if peak else None
        if not level:
            continue
        mm, at = peak
        out.append({
            "hazard_id": f"derived-landslide-{pid}",
            "hazard_type": "LANDSLIDE_RISK",
            "severity": level,
            "lat": lat,
            "lng": lng,
            "province": province,
            "title_th": f"เสี่ยงดินถล่ม (ประเมินจากฝนสะสม 24 ชม. {mm:.0f} มม. ช่วง {thai_date(at)})",
            "source": "DERIVED",
            "updated_at": updated,
        })
    return out
