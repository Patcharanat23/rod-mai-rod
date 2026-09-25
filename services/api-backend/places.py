"""ค้นสถานที่ในไทยผ่าน Photon (CONTRACT หัวข้อ 6 GET /places/search)"""
from time import monotonic
from typing import Optional

import httpx

from envelope import ApiError
from geo import THAILAND_BOUNDS, in_thailand

PHOTON_URL = "https://photon.komoot.io/api/"
PHOTON_TIMEOUT = 5  # วินาที ตาม CONTRACT หัวข้อ 3
USER_AGENT = "rod-mai-rod/1.0 (university course project)"
ASK = 8  # ขอเกินไว้ เพราะ bbox คลุมประเทศเพื่อนบ้านด้วย ต้องคัดทิ้ง
LIMIT = 5
MIN_CHARS = 2
CACHE_SECONDS = 600

_min_lat, _min_lng, _max_lat, _max_lng = THAILAND_BOUNDS
BBOX = f"{_min_lng},{_min_lat},{_max_lng},{_max_lat}"  # Photon ใช้ลำดับ lng,lat

# คำย่อที่คนไทยพิมพ์บ่อย แปลงทีละคำ (คั่นด้วยช่องว่าง) ไม่แทนกลางคำ
ABBREVIATIONS = {
    "กทม": "กรุงเทพมหานคร",
    "กรุงเทพ": "กรุงเทพมหานคร",
    "กรุงเทพฯ": "กรุงเทพมหานคร",
    "บางกอก": "กรุงเทพมหานคร",
    "โคราช": "นครราชสีมา",
    "อยุธยา": "พระนครศรีอยุธยา",
    "แปดริ้ว": "ฉะเชิงเทรา",
    "นครศรี": "นครศรีธรรมราช",
    "นครศรีฯ": "นครศรีธรรมราช",
    "สุราษฎร์": "สุราษฎร์ธานี",
    "สุราษฎร์ฯ": "สุราษฎร์ธานี",
    "อุบล": "อุบลราชธานี",
    "อุดร": "อุดรธานี",
    "ประจวบ": "ประจวบคีรีขันธ์",
    "สุพรรณ": "สุพรรณบุรี",
    "กาญ": "กาญจนบุรี",
}

_cache: dict[str, tuple[float, list[dict]]] = {}


def expand(q: str) -> str:
    return " ".join(ABBREVIATIONS.get(word.rstrip("."), word) for word in q.split())


def _detail(p: dict) -> Optional[str]:
    """อำเภอ, จังหวัด เท่าที่มี"""
    parts = []
    for value in (p.get("county") or p.get("city"), p.get("state")):
        if value and value not in parts:
            parts.append(value)
    return ", ".join(parts) or None


def _to_place(feature: dict) -> Optional[dict]:
    p = feature.get("properties") or {}
    lng, lat = feature["geometry"]["coordinates"]  # GeoJSON ส่ง [lng, lat] ต้องสลับ (CONTRACT หัวข้อ 4)
    if p.get("countrycode") != "TH" or not p.get("name") or not in_thailand(lat, lng):
        return None
    return {"name": p["name"], "detail": _detail(p), "lat": lat, "lng": lng}


def search(q: str) -> list[dict]:
    q = q.strip()
    if len(q) < MIN_CHARS:
        raise ApiError("VALIDATION_ERROR", f"พิมพ์ชื่อสถานที่อย่างน้อย {MIN_CHARS} ตัวอักษร")
    query = expand(q)
    key = query.lower()
    hit = _cache.get(key)
    if hit and hit[0] > monotonic():
        return hit[1]
    try:
        res = httpx.get(PHOTON_URL, params={"q": query, "limit": ASK, "bbox": BBOX},
                        headers={"User-Agent": USER_AGENT}, timeout=PHOTON_TIMEOUT)
        res.raise_for_status()
        features = res.json().get("features", [])
    except httpx.TimeoutException:
        raise ApiError("UPSTREAM_TIMEOUT", "ค้นหาสถานที่ไม่ทันเวลา ลองใหม่หรือปักหมุดบนแผนที่แทน")
    except (httpx.HTTPError, ValueError):
        raise ApiError("UPSTREAM_ERROR", "ค้นหาสถานที่ไม่ได้ตอนนี้ ลองใหม่หรือปักหมุดบนแผนที่แทน")

    found, seen = [], set()
    for feature in features:
        place = _to_place(feature)
        # Photon มักส่งที่เดียวกันซ้ำ (จุดกับขอบเขต) ตัดด้วยชื่อ + รายละเอียด
        if place and (place["name"], place["detail"]) not in seen:
            seen.add((place["name"], place["detail"]))
            found.append(place)
        if len(found) == LIMIT:
            break
    if len(_cache) > 1000:
        _cache.clear()
    _cache[key] = (monotonic() + CACHE_SECONDS, found)
    return found