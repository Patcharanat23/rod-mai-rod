"""สถานที่ในไทย (CONTRACT หัวข้อ 6): ค้นจากชื่อผ่าน Photon และที่เที่ยวใกล้ตัวผ่าน Overpass

DEMO_MODE=true อ่านคำตอบที่บันทึกไว้ใน fixtures/ ไม่เรียกเน็ตเลย (บันทึกด้วย record_fixtures.py)
"""
import json
import os
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from pathlib import Path
from time import monotonic
from typing import Optional

import httpx

from envelope import ApiError
from geo import THAILAND_BOUNDS, haversine_km, in_thailand

PHOTON_URL = "https://photon.komoot.io/api/"
PHOTON_TIMEOUT = 5  # วินาที ตาม CONTRACT หัวข้อ 3
USER_AGENT = "rod-mai-rod/1.0 (university course project)"
ASK = 8  # ขอเกินไว้ เพราะ bbox คลุมประเทศเพื่อนบ้านด้วย ต้องคัดทิ้ง
LIMIT = 5
MIN_CHARS = 2
CACHE_SECONDS = 600

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SEARCH_FIXTURE = FIXTURES / "places_search.json"
NEARBY_FIXTURE = FIXTURES / "places_nearby.json"
DEMO_MATCH_KM = 15  # เท่ากับของ routing-engine บนเวทีตำแหน่งไม่ตรงกับตอนบันทึก

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


def demo_mode() -> bool:
    return os.getenv("DEMO_MODE", "false").lower() == "true"


def _fixture(path: Path, section: str) -> dict:
    """คำตอบที่บันทึกไว้ ไม่มีไฟล์ถือว่าว่าง"""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get(section, {})


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


def fetch_search(query: str) -> list[dict]:
    """ยิง Photon จริง คืนไม่เกิน LIMIT ตัวที่อยู่ในไทย"""
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
    return found


def search(q: str) -> list[dict]:
    q = q.strip()
    if len(q) < MIN_CHARS:
        raise ApiError("VALIDATION_ERROR", f"พิมพ์ชื่อสถานที่อย่างน้อย {MIN_CHARS} ตัวอักษร")
    query = expand(q)
    key = query.lower()
    if demo_mode():
        # คำที่ไม่ได้บันทึกไว้ตอบว่างเหมือนค้นไม่เจอ ไม่ใช่ error
        return _fixture(SEARCH_FIXTURE, "queries").get(key, [])
    hit = _cache.get(key)
    if hit and hit[0] > monotonic():
        return hit[1]
    found = fetch_search(query)
    if len(_cache) > 1000:
        _cache.clear()
    _cache[key] = (monotonic() + CACHE_SECONDS, found)
    return found


# ---------- สถานที่เที่ยวใกล้ตัว (GET /places/nearby) ----------

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_TIMEOUT = 8  # วินาทีที่คำขอรอ ตาม CONTRACT หัวข้อ 3
OVERPASS_DOWNLOAD_TIMEOUT = 30  # ไม่ทัน OVERPASS_TIMEOUT ยังโหลดต่อเบื้องหลังจนเสร็จแล้วเก็บลง cache
NEARBY_RADIUS_KM = 5
NEARBY_LIMIT = 8
NEARBY_CACHE_SECONDS = 24 * 60 * 60

# node ที่มีชื่อ และเป็นที่เที่ยวตาม CONTRACT หัวข้อ 6
OVERPASS_QUERY = (
    "[out:json][timeout:{timeout}];("
    'node(around:{radius},{lat},{lng})["name"]["tourism"~"^(attraction|viewpoint|museum|zoo|theme_park)$"];'
    'node(around:{radius},{lat},{lng})["name"]["historic"~"^(monument|temple|ruins)$"];'
    ");out body;"
)

KIND_TH = {
    "attraction": "สถานที่ท่องเที่ยว",
    "viewpoint": "จุดชมวิว",
    "museum": "พิพิธภัณฑ์",
    "zoo": "สวนสัตว์",
    "theme_park": "สวนสนุก",
    "monument": "อนุสาวรีย์",
    "temple": "วัด",
    "ruins": "โบราณสถาน",
}

_nearby_cache: dict[tuple[float, float], tuple[float, list[dict]]] = {}
# ช่องที่กำลังโหลดอยู่ คำขอช่องเดียวกันรองานเดิม ไม่ยิงซ้ำ (แบบ _pending ของ routing-engine)
_nearby_pending: dict[tuple[float, float], Future] = {}
_pending_lock = threading.Lock()  # ถือแค่ตอนเช็คและสั่งโหลด ไม่ได้ถือตลอดการโหลด
_nearby_pool = ThreadPoolExecutor(max_workers=2)  # Overpass ให้แต่ละ IP ยิงพร้อมกันได้ไม่กี่คำขอ


def _addr_detail(tags: dict) -> Optional[str]:
    """อำเภอ, จังหวัด จากแท็ก addr:* เท่าที่มี"""
    parts = []
    for value in (tags.get("addr:district") or tags.get("addr:city"), tags.get("addr:province")):
        if value and value not in parts:
            parts.append(value)
    return ", ".join(parts) or None


def _to_nearby(element: dict) -> Optional[dict]:
    tags = element.get("tags") or {}
    name = tags.get("name:th") or tags.get("name")
    kind = next((KIND_TH[tags[k]] for k in ("tourism", "historic") if tags.get(k) in KIND_TH), None)
    if not name or not kind or "lat" not in element:
        return None
    # Overpass ใช้ชื่อ lon ของเราใช้ lng (CONTRACT หัวข้อ 4)
    return {"name": name, "detail": _addr_detail(tags), "lat": element["lat"], "lng": element["lon"], "kind_th": kind}


def fetch_nearby(lat: float, lng: float, timeout: float = OVERPASS_DOWNLOAD_TIMEOUT) -> list[dict]:
    """ยิง Overpass จริง คืนที่เที่ยวทุกตัวในรัศมี ยังไม่เรียงและไม่ตัดจำนวน"""
    query = OVERPASS_QUERY.format(timeout=timeout, radius=NEARBY_RADIUS_KM * 1000, lat=lat, lng=lng)
    try:
        res = httpx.post(OVERPASS_URL, data={"data": query},
                         headers={"User-Agent": USER_AGENT}, timeout=timeout)
        res.raise_for_status()
        elements = res.json().get("elements", [])
    except httpx.TimeoutException:
        raise ApiError("UPSTREAM_TIMEOUT", "ดึงสถานที่เที่ยวใกล้ๆ ไม่ทันเวลา ลองใหม่อีกครั้ง")
    except (httpx.HTTPError, ValueError):
        raise ApiError("UPSTREAM_ERROR", "ดึงสถานที่เที่ยวใกล้ๆ ไม่ได้ตอนนี้ ลองใหม่อีกครั้ง")
    return [p for p in map(_to_nearby, elements) if p]


def _download(cell: tuple[float, float]) -> list[dict]:
    """รันเบื้องหลัง เก็บลง cache เฉพาะที่สำเร็จ แล้วเอาช่องออกจากรายการที่กำลังโหลด"""
    try:
        candidates = fetch_nearby(*cell)
        if len(_nearby_cache) > 1000:
            _nearby_cache.clear()
        _nearby_cache[cell] = (monotonic() + NEARBY_CACHE_SECONDS, candidates)
        return candidates
    finally:
        with _pending_lock:
            _nearby_pending.pop(cell, None)


def _cached_candidates(cell: tuple[float, float]) -> list[dict]:
    """รอไม่เกิน OVERPASS_TIMEOUT ไม่ทันตอบ UPSTREAM_TIMEOUT แต่ให้โหลดต่อ คำขอถัดไปจะได้จาก cache"""
    with _pending_lock:
        hit = _nearby_cache.get(cell)
        if hit and hit[0] > monotonic():
            return hit[1]
        job = _nearby_pending.get(cell)
        if job is None:
            job = _nearby_pending[cell] = _nearby_pool.submit(_download, cell)
    try:
        return job.result(timeout=OVERPASS_TIMEOUT)
    except FutureTimeout:
        raise ApiError("UPSTREAM_TIMEOUT", "สถานที่เที่ยวใกล้ๆ ยังโหลดไม่เสร็จ กำลังโหลดต่อให้ ลองใหม่ในอีกสักครู่")


def _demo_cell(lat: float, lng: float) -> tuple[dict, list[dict]]:
    """ช่องที่บันทึกไว้ที่ใกล้ที่สุดไม่เกิน DEMO_MATCH_KM คืน (จุดกลางช่อง, ที่เที่ยว) ไม่มีเลยคืน (จุดที่ขอ, [])"""
    here = {"lat": lat, "lng": lng}
    best_center, best_places, best_km = here, [], None
    for key, candidates in _fixture(NEARBY_FIXTURE, "cells").items():
        c_lat, c_lng = map(float, key.split("_"))
        center = {"lat": c_lat, "lng": c_lng}
        km = haversine_km(here, center)
        if km <= DEMO_MATCH_KM and (best_km is None or km < best_km):
            best_center, best_places, best_km = center, candidates, km
    return best_center, best_places


def nearby(lat: float, lng: float) -> list[dict]:
    if not in_thailand(lat, lng):
        raise ApiError("OUT_OF_THAILAND", "ตอนนี้รองรับเฉพาะสถานที่ในประเทศไทย")
    here = {"lat": lat, "lng": lng}
    if demo_mode():
        # บนเวทีอยู่คนละที่กับตอนบันทึก ใช้จุดกลางช่องที่บันทึกไว้ ไม่งั้นรัศมี 5 กม. ตัดทิ้งหมด
        here, candidates = _demo_cell(lat, lng)
    else:
        # ปัดทศนิยม 2 ตำแหน่ง (~1 กม.) คนที่อยู่ช่องเดียวกันใช้ข้อมูลชุดเดียว ประหยัดโควตา Overpass
        candidates = _cached_candidates((round(lat, 2), round(lng, 2)))

    found, seen = [], set()
    for place in sorted(candidates, key=lambda p: haversine_km(here, p)):
        if haversine_km(here, place) > NEARBY_RADIUS_KM:
            break
        # OpenStreetMap มักมีที่เดียวกันหลายจุด เก็บจุดที่ใกล้สุด
        if place["name"] not in seen:
            seen.add(place["name"])
            found.append(place)
        if len(found) == NEARBY_LIMIT:
            break
    return found