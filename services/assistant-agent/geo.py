"""ฟังก์ชันพิกัดและเวลาที่ stub ใช้ ใช้ต่อในของจริงได้"""
import math
from datetime import datetime, timezone

# กรอบคร่าวๆ ของประเทศไทย: min_lat, min_lng, max_lat, max_lng
THAILAND_BOUNDS = (5.6, 97.3, 20.5, 105.7)


def in_thailand(lat: float, lng: float) -> bool:
    min_lat, min_lng, max_lat, max_lng = THAILAND_BOUNDS
    return min_lat <= lat <= max_lat and min_lng <= lng <= max_lng


def haversine_km(a: dict, b: dict) -> float:
    r = 6371.0
    lat1, lat2 = math.radians(a["lat"]), math.radians(b["lat"])
    dlat = lat2 - lat1
    dlng = math.radians(b["lng"] - a["lng"])
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def to_iso(dt: datetime) -> str:
    """เวลาในระบบต้องเป็น UTC ลงท้าย Z เสมอ"""
    if dt.tzinfo is None:
        raise ValueError("datetime ต้องมี timezone")
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def score_to_level(score: int) -> str:
    if score <= 33:
        return "LOW"
    if score <= 66:
        return "MEDIUM"
    return "HIGH"
