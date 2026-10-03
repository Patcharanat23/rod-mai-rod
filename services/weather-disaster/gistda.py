"""Real flood extent from GISTDA satellite data as FLOOD hazards.

GISTDA publishes flooded H3 cells (about 0.1 km2 each) detected by radar satellites for the last
1/3/7/30 days. We fetch the 3-day set (7-day when the 3-day set is empty) for the whole country
in the background every 30 minutes,
group the cells per tambon, and keep the result in memory. Requests never wait for GISTDA.
"""
import logging
import os
import threading
import time
from collections import defaultdict

import httpx


logger = logging.getLogger("weather-disaster")

GISTDA_URL = "https://api-gateway.gistda.or.th/api/2.0/resources/features/flood/{window}"
# 3 วันล่าสุดก่อน ถ้าดาวเทียมยังไม่มีภาพใหม่ (เช่นเมฆบัง ชุด 1-3 วันว่าง) ใช้ 7 วันแทน
WINDOWS = ("3days", "7days")
PAGE = 2000
TIMEOUT_S = 30  # background only, never in a user request
REFRESH_S = 30 * 60
MAX_CELLS = 150000  # รวมเป็นตำบลทีละหน้า ไม่เก็บช่องดิบ แรมไม่โตตามจำนวนช่อง
RAI_M2 = 1600

# severity from flooded road, the satellite gives extent not depth
HIGH_ROAD_KM = 1.0

_latest: list[dict] = []
_window: str | None = None
_fetched_at: float | None = None
_lock = threading.Lock()


def enabled() -> bool:
    return bool(os.getenv("GISTDA_API_KEY"))


def _centroid(geom: dict) -> tuple[float, float]:
    pts = [pt for poly in geom["coordinates"] for ring in poly[:1] for pt in ring]
    return sum(p[1] for p in pts) / len(pts), sum(p[0] for p in pts) / len(pts)


def severity(road_km: float) -> str:
    """ระดับจากถนนที่ท่วมเท่านั้น (เดิมนับประชากร 500 คน = สูง ทำให้นาท่วมที่ไม่มีถนนท่วมขึ้นสูง)"""
    if road_km >= HIGH_ROAD_KM:
        return "HIGH"
    if road_km > 0:
        return "MEDIUM"
    return "LOW"


def _new_groups() -> dict:
    return defaultdict(lambda: {"n": 0, "lat": 0.0, "lng": 0.0, "area": 0.0, "road": 0.0, "pop": 0.0, "updated": "", "road_cells": []})


def to_hazards(cells: list[dict]) -> list[dict]:
    """Group flooded cells per tambon into one hazard at the cells' mean position."""
    groups = _new_groups()
    _add(groups, cells)
    return _finish(groups)


def _add(groups: dict, cells: list[dict]) -> None:
    for f in cells:
        p = f.get("properties") or {}
        try:
            lat, lng = _centroid(f["geometry"])
        except (KeyError, TypeError, ZeroDivisionError, IndexError):
            continue
        g = groups[(p.get("pv_tn"), p.get("ap_tn"), p.get("tb_tn"))]
        g["n"] += 1
        g["lat"] += lat
        g["lng"] += lng
        g["area"] += p.get("f_area") or 0
        g["road"] += p.get("length_road") or 0
        if (p.get("length_road") or 0) > 0:
            # ช่องที่มีถนนท่วมจริง risk-decision ใช้เช็คว่าเส้นทางวิ่งผ่านถนนที่ท่วมไหม
            g["road_cells"].append([round(lat, 4), round(lng, 4)])
        g["pop"] += p.get("population") or 0
        g["updated"] = max(g["updated"], p.get("_updatedAt") or "")


def _finish(groups: dict) -> list[dict]:
    out = []
    for (pv, ap, tb), g in groups.items():
        rai, road_km = g["area"] / RAI_M2, g["road"] / 1000
        title = f"น้ำท่วม {tb or ''} {ap or ''} ({rai:,.0f} ไร่"
        if road_km >= 0.1:
            title += f" ถนนท่วม {road_km:.1f} กม."
        out.append({
            "hazard_id": f"gistda-{pv}-{ap}-{tb}",
            "hazard_type": "FLOOD",
            "severity": severity(road_km),
            "lat": round(g["lat"] / g["n"], 5),
            "lng": round(g["lng"] / g["n"], 5),
            "province": (pv or "").replace("จ.", "") or None,
            "title_th": " ".join(title.split()) + ")",
            "source": "GISTDA",
            "updated_at": (g["updated"][:19] + "Z") if g["updated"] else None,
            "road_cells": g["road_cells"],
        })
    return out


def fetch_window(client: httpx.Client, window: str) -> list[dict]:
    groups, seen = _new_groups(), 0
    while seen < MAX_CELLS:
        res = client.get(GISTDA_URL.format(window=window), params={"limit": PAGE, "offset": seen})
        res.raise_for_status()
        page = res.json().get("features") or []
        _add(groups, page)
        seen += len(page)
        if len(page) < PAGE:
            break
    return _finish(groups)


def fetch_all() -> tuple[list[dict], str | None]:
    """คืน (หมุดน้ำท่วม, ชุดที่ใช้) ชุดแรกที่มีข้อมูล ว่างทุกชุดคืน ([], None)"""
    headers = {"API-Key": os.environ["GISTDA_API_KEY"]}
    with httpx.Client(timeout=TIMEOUT_S, headers=headers) as client:
        for window in WINDOWS:
            found = fetch_window(client, window)
            if found:
                return found, window
    return [], None


def latest() -> list[dict]:
    with _lock:
        return list(_latest)


def window() -> str | None:
    """ชุดข้อมูลที่ใช้อยู่ ("3days" / "7days") หน้าเว็บใช้เลือกชั้นภาพน้ำท่วมให้ตรงกัน"""
    with _lock:
        return _window


def keep_fresh() -> None:
    global _latest, _window, _fetched_at
    while True:
        started = time.monotonic()
        try:
            result, used = fetch_all()
            with _lock:
                _latest, _window, _fetched_at = result, used, time.monotonic()
            logger.info("gistda flood: %d tambons from %s in %.1f s", len(result), used, time.monotonic() - started)
        except Exception:
            # keep the previous result; an old flood map is better than none
            logger.warning("gistda flood refresh failed", exc_info=True)
        time.sleep(REFRESH_S)
