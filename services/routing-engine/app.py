"""routing-engine

fetch_routes() หาเส้นทางจริงจาก OSRM ส่งทุกเส้นไป risk-decision ในคำขอเดียว แล้วประกอบ TripPlan (build_plan)
DEMO_MODE=true อ่านคำตอบ OSRM ที่บันทึกไว้ใน fixtures/ ไม่เรียกเน็ตเลย
ได้เส้นเดียวและเสี่ยงสูง ลองสร้างเส้นเลี่ยงเองถ้าเวลายังพอ (plan_routes)
"""
import json
import math
import os
import time
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from envelope import ApiError, call, ok, setup
from geo import haversine_km, in_thailand, to_iso

app = FastAPI(title="routing-engine")
setup(app, "routing-engine")

RISK_TIMEOUT = 30  # วินาที ตาม CONTRACT หัวข้อ 3
OSRM_TIMEOUT = 12  # เวลารวมที่รอ OSRM ต่อคำขอ 12 + 30 ต้องน้อยกว่า 45 ที่ api-backend รอเรา
OSRM_DOWNLOAD_TIMEOUT = 90  # ถ้าเกิน OSRM_TIMEOUT ยังโหลดต่อเบื้องหลังจนเสร็จแล้วเก็บลง cache
# polyline เล็กกว่า geojson ประมาณ 6 เท่า OSRM สาธารณะส่งข้อมูลมาไทยช้ามาก
OSRM_PARAMS = {"alternatives": "3", "overview": "full", "geometries": "polyline"}
MAX_GEOMETRY_POINTS = 500  # CONTRACT หัวข้อ 4
SAMPLE_STEP_KM = 20  # ระยะห่างจุดที่ส่งไปประเมินความเสี่ยง
FIXTURES = Path(__file__).resolve().parent / "fixtures"
DEMO_MATCH_KM = 15  # เท่ากับของ weather-disaster บนเวทีจิ้มแผนที่ให้ตรงระดับ 100 ม. ไม่ได้
# เส้นเลี่ยง (งาน 5.4) ทำเมื่อได้เส้นเดียวและเส้นนั้นอยู่ในระดับเหล่านี้
DETOUR_LEVELS = {"HIGH"}
DETOUR_OFFSET_KM = 50  # ระยะที่ดันจุดผ่านออกข้างเส้นเดิม
HAZARD_RADIUS_KM = 20  # CONTRACT หัวข้อ 4 เส้นเลี่ยงต้องห่างจุดเสี่ยงเกินนี้
MAX_SLOWER_RATIO = 1.5  # ช้ากว่าเส้นหลักเกินนี้ risk-decision ไม่แนะนำอยู่แล้ว
PLAN_BUDGET = 42  # วินาทีต่อคำขอ api-backend รอเรา 45
DETOUR_MIN_LEFT = OSRM_TIMEOUT + 8  # เหลือเวลาน้อยกว่านี้ไม่ลองเส้นเลี่ยง

_cache: dict[tuple, dict] = {}
_pending: dict[tuple, Future] = {}
_pool = ThreadPoolExecutor(max_workers=4)


class Place(BaseModel):
    lat: float
    lng: float
    name: Optional[str] = None


class PlanIn(BaseModel):
    origin: Place
    destination: Place
    departure_time: datetime
    waypoints: list[Place] = []


def route_key(stops: list[Place]) -> tuple:
    """พิกัดทุก stop ปัดทศนิยม 3 ตำแหน่ง (ประมาณ 100 ม.) ใช้เป็น key ของ cache"""
    return tuple((round(s.lat, 3), round(s.lng, 3)) for s in stops)


def fixture_path(key: tuple) -> Path:
    """ชื่อไฟล์คือพิกัดทุก stop ตาม route_key เช่น 13.756_100.502__18.788_98.985.json"""
    return FIXTURES / ("__".join(f"{lat:.3f}_{lng:.3f}" for lat, lng in key) + ".json")


def nearest_fixture(key: tuple) -> Optional[Path]:
    """ทริปที่บันทึกไว้ซึ่งมีจำนวนจุดเท่ากันและทุกจุดห่างไม่เกิน DEMO_MATCH_KM เลือกที่ใกล้รวมน้อยที่สุด"""
    best, best_km = None, None
    for path in FIXTURES.glob("*.json"):
        saved = [tuple(map(float, part.split("_"))) for part in path.stem.split("__")]
        if len(saved) != len(key):
            continue
        dists = [haversine_km({"lat": a[0], "lng": a[1]}, {"lat": b[0], "lng": b[1]}) for a, b in zip(key, saved)]
        if max(dists) <= DEMO_MATCH_KM and (best_km is None or sum(dists) < best_km):
            best, best_km = path, sum(dists)
    return best


def osrm_request(stops: list[Place]) -> dict:
    """คำตอบดิบของ OSRM ผ่าน cache รอไม่เกิน OSRM_TIMEOUT ทริปเดียวกันที่กำลังโหลดอยู่ไม่ยิงซ้ำ"""
    key = route_key(stops)
    if key in _cache:
        return _cache[key]
    if os.getenv("DEMO_MODE", "false").lower() == "true":
        path = fixture_path(key)
        if not path.exists():
            path = nearest_fixture(key)
        if path is None:
            raise ApiError("UPSTREAM_ERROR", "โหมดสาธิตมีเฉพาะทริปตัวอย่าง ลองกรุงเทพ > เชียงใหม่ หรือแวะนครสวรรค์")
        _cache[key] = json.loads(path.read_text())
        return _cache[key]
    base = os.getenv("OSRM_BASE_URL")
    if not base:
        raise ApiError("INTERNAL_ERROR", "ยังไม่ได้ตั้งค่า OSRM_BASE_URL ใน .env")
    job = _pending.get(key)
    if job is None:
        job = _pending[key] = _pool.submit(_download, base, stops, key)
    try:
        return job.result(timeout=OSRM_TIMEOUT)
    except FutureTimeout:
        raise ApiError("UPSTREAM_TIMEOUT", "ระบบหาเส้นทางตอบช้า กำลังโหลดต่อให้ ลองกด Plan อีกครั้งในอีกสักครู่")


def _download(base: str, stops: list[Place], key: tuple) -> dict:
    coords = ";".join(f"{s.lng},{s.lat}" for s in stops)  # OSRM ใช้ lng,lat
    try:
        try:
            res = httpx.get(f"{base.rstrip('/')}/route/v1/driving/{coords}",
                            params=OSRM_PARAMS, timeout=OSRM_DOWNLOAD_TIMEOUT)
        except httpx.TimeoutException:
            raise ApiError("UPSTREAM_TIMEOUT", "ระบบหาเส้นทางตอบไม่ทันเวลา ลองใหม่อีกครั้ง")
        except httpx.HTTPError:
            raise ApiError("UPSTREAM_ERROR", "ติดต่อระบบหาเส้นทางไม่ได้ ลองใหม่อีกครั้ง")
        if res.status_code == 429:
            raise ApiError("RATE_LIMITED", "ระบบหาเส้นทางมีคนใช้เยอะ รอสักครู่แล้วลองใหม่")
        try:
            body = res.json()
        except ValueError:
            raise ApiError("UPSTREAM_ERROR", "ระบบหาเส้นทางตอบผิดรูปแบบ ลองใหม่อีกครั้ง")
        if body.get("code") == "NoRoute":
            raise ApiError("UPSTREAM_ERROR", "หาเส้นทางทางถนนระหว่างจุดเหล่านี้ไม่ได้ ลองเลื่อนหมุดให้อยู่ใกล้ถนน")
        if body.get("code") != "Ok" or not body.get("routes"):
            raise ApiError("UPSTREAM_ERROR", "หาเส้นทางไม่ได้ ลองใหม่อีกครั้ง")
        _cache[key] = body  # เก็บเฉพาะที่สำเร็จ เส้นทางไม่เปลี่ยนจึงไม่ต้องหมดอายุ
        return body
    finally:
        _pending.pop(key, None)


def decode_polyline(text: str) -> list[tuple[float, float]]:
    """ถอด polyline ความละเอียด 5 ตำแหน่งของ OSRM เป็น [(lat, lng)] (ในรหัสเรียง lat ก่อน lng)"""
    points, index, lat, lng = [], 0, 0, 0
    while index < len(text):
        for is_lng in (False, True):
            shift = result = 0
            while True:
                b = ord(text[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if is_lng:
                lng += delta
            else:
                lat += delta
        points.append((lat / 1e5, lng / 1e5))
    return points


def simplify(points: list[tuple[float, float]], limit: int = MAX_GEOMETRY_POINTS) -> list[dict]:
    """(lat, lng) เป็น {lat, lng} และเลือกจุดห่างเท่าๆ กันให้ไม่เกิน limit โดยเก็บจุดแรกและจุดสุดท้ายไว้เสมอ"""
    if len(points) > limit:
        step = (len(points) - 1) / (limit - 1)
        points = [points[round(i * step)] for i in range(limit)]
    return [{"lat": lat, "lng": lng} for lat, lng in points]


def leg_bounds(points: list[tuple[float, float]], snapped: list[list[float]]) -> list[int]:
    """index ใน geometry ของแต่ละ stop จาก waypoints[].location ([lng, lat]) ของ OSRM หาไล่ไปข้างหน้า"""
    bounds, start = [0], 0
    for lng, lat in snapped[1:-1]:
        start = min(range(start, len(points)),
                    key=lambda k: (points[k][0] - lat) ** 2 + (points[k][1] - lng) ** 2)
        bounds.append(start)
    return bounds + [len(points) - 1]


def sample_points(points: list[tuple[float, float]], bounds: list[int], legs: list[dict],
                  step_km: float = SAMPLE_STEP_KM) -> list[dict]:
    """จุดทุก step_km ตาม geometry เต็ม นับใหม่ทุก stop ไม่รวม stop
    เวลาของแต่ละ leg แบ่งตามสัดส่วนระยะ จุดที่ห่าง stop ถัดไปไม่ถึงครึ่ง step ข้ามไป (stop ถูกประเมินอยู่แล้ว)"""
    samples, leg_start_min = [], 0.0
    for leg, a, b in zip(legs, bounds, bounds[1:]):
        seg = [haversine_km({"lat": p[0], "lng": p[1]}, {"lat": q[0], "lng": q[1]})
               for p, q in zip(points[a:b], points[a + 1:b + 1])]
        total, done, mark = sum(seg), 0.0, step_km
        for k, d in enumerate(seg):
            while d > 0 and done + d >= mark and mark <= total - step_km / 2:
                t = (mark - done) / d
                (lat1, lng1), (lat2, lng2) = points[a + k], points[a + k + 1]
                samples.append({"lat": lat1 + (lat2 - lat1) * t, "lng": lng1 + (lng2 - lng1) * t,
                                "minute": leg_start_min + mark / total * leg["duration"] / 60})
                mark += step_km
            done += d
        leg_start_min += leg["duration"] / 60
    return samples


def to_route(route_id: str, r: dict, snapped: list[list[float]], via: Optional[int] = None) -> dict:
    """แปลงเส้นหนึ่งของ OSRM เป็นรูปแบบของเรา via = index ของจุดผ่านที่เราเติมเอง ไม่ใช่หมุดของผู้ใช้"""
    points = decode_polyline(r["geometry"])
    stop_minutes = [0.0]
    for leg in r["legs"]:
        stop_minutes.append(stop_minutes[-1] + leg["duration"] / 60)
    if via is not None:
        del stop_minutes[via]
    return {
        "route_id": route_id,
        "duration_min": round(r["duration"] / 60),
        "distance_km": round(r["distance"] / 1000),
        "geometry": simplify(points),
        "stop_minutes": stop_minutes,
        "samples": sample_points(points, leg_bounds(points, snapped), r["legs"]),
    }


def fetch_routes(stops: list[Place]) -> list[dict]:
    """คืนเส้นทางทั้งหมด เส้นแรกต้องเป็นเส้นหลัก (เร็วที่สุด)

    แต่ละเส้น: {route_id, duration_min, distance_km, geometry: [{lat, lng}],
               stop_minutes: [นาทีสะสมตอนถึงแต่ละ stop เริ่มที่ 0], samples: [{lat, lng, minute}]}
    samples คือจุดตัวอย่างระหว่างทางประมาณทุก 20 กม. พร้อมนาทีสะสม (ไม่รวม stop)
    """
    body = osrm_request(stops)
    snapped = [w["location"] for w in body["waypoints"]]
    return [to_route(f"r{i}", r, snapped) for i, r in enumerate(body["routes"], start=1)]


def risk_points(route: dict, stops: list[Place], depart: datetime) -> tuple[list[dict], list[int]]:
    """รวม stop กับ samples เรียงตามเวลา คืน (จุดที่ส่งไป risk-decision, index ของแต่ละ stop ในจุดพวกนั้น)"""
    items = [(m, s.lat, s.lng, i) for i, (s, m) in enumerate(zip(stops, route["stop_minutes"]))]
    items += [(p["minute"], p["lat"], p["lng"], None) for p in route["samples"]]
    items.sort(key=lambda x: x[0])
    points, stop_idx = [], [0] * len(stops)
    for minute, lat, lng, stop_no in items:
        if stop_no is not None:
            stop_idx[stop_no] = len(points)
        points.append({"lat": lat, "lng": lng, "eta": to_iso(depart + timedelta(minutes=minute))})
    return points, stop_idx


def build_plan(body: PlanIn, stops: list[Place], routes: list[dict], risk: Optional[dict]) -> dict:
    """ประกอบ TripPlan ตาม CONTRACT หัวข้อ 6 (ทุก field ยกเว้น trip_id, trip_no)
    risk = None แปลว่าเรียก risk-decision ไม่สำเร็จ ต้องไม่เดาความเสี่ยงเป็น LOW"""
    warnings = []
    if risk is None:
        warnings.append("WEATHER_UNAVAILABLE")
        risk = {
            "routes": [{"route_id": r["route_id"], "risk_level": None, "risk_score": None,
                        "points": [{**p, "forecast": None, "risk_level": None} for p in r["points"]]}
                       for r in routes],
            "recommended_route_id": routes[0]["route_id"],
            "recommendation": "NORMAL",
            "summary_th": "ตอนนี้ประเมินความเสี่ยงไม่ได้ ข้อมูลสภาพอากาศไม่พร้อม",
            "warnings": [],
        }
    by_id = {r["route_id"]: r for r in risk["routes"]}
    rec_id = risk["recommended_route_id"]

    options = [{
        "route_id": r["route_id"],
        "duration_min": r["duration_min"],
        "distance_km": r["distance_km"],
        "risk_level": by_id[r["route_id"]]["risk_level"],
        "risk_score": by_id[r["route_id"]]["risk_score"],
        "is_recommended": r["route_id"] == rec_id,
        "geometry": r["geometry"],
    } for r in routes]
    best = next(o for o in options if o["is_recommended"])
    best_route = next(r for r in routes if r["route_id"] == rec_id)

    rec_points = by_id[rec_id]["points"]
    waypoints = []
    for i, place in enumerate(stops):
        kind = "ORIGIN" if i == 0 else "DESTINATION" if i == len(stops) - 1 else "STOP"
        pt = rec_points[best_route["stop_idx"][i]]
        waypoints.append({
            "waypoint_id": f"wp-{i}",
            "kind": kind,
            "name": place.name or kind.lower(),
            "lat": place.lat,
            "lng": place.lng,
            "eta": pt["eta"],
            "forecast": pt["forecast"],
            "risk_level": pt["risk_level"],
        })

    warnings += risk.get("warnings", [])
    if len(routes) == 1 and best["risk_level"] in ("MEDIUM", "HIGH"):
        warnings.append("ALTERNATIVE_ROUTES_UNAVAILABLE")

    return {
        "departure_time": to_iso(body.departure_time),
        "arrival_time": to_iso(body.departure_time + timedelta(minutes=best["duration_min"])),
        "duration_min": best["duration_min"],
        "risk_level": best["risk_level"],
        "risk_score": best["risk_score"],
        "recommendation": risk["recommendation"],
        "summary_th": risk["summary_th"],
        "route_options": options,
        "waypoints": waypoints,
        "warnings": sorted(set(warnings)),
    }


def detour_vias(route: dict, risk_points_: list[dict], stops: list[Place]) -> tuple[list[dict], list[tuple[int, Place]]]:
    """จุดเสี่ยงระหว่างทาง (ไม่รวมหมุดของผู้ใช้ ซึ่งเลี่ยงไม่ได้) และจุดผ่านที่ดันออกไปสองข้างของช่วงนั้น
    คืน (จุดเสี่ยง, [(ตำแหน่งที่แทรกใน stops, จุดผ่าน)])"""
    bad = [i for i, p in enumerate(risk_points_)
           if p.get("risk_level") in DETOUR_LEVELS and i not in route["stop_idx"]]
    if not bad:
        return [], []
    risky = [risk_points_[i] for i in bad]
    lat = sum(p["lat"] for p in risky) / len(risky)
    lng = sum(p["lng"] for p in risky) / len(risky)
    before = risk_points_[max(bad[0] - 1, 0)]
    after = risk_points_[min(bad[-1] + 1, len(risk_points_) - 1)]
    # ทิศของเส้นช่วงนั้น แล้วหมุน 90 องศา คิดเป็นกม. ก่อนแปลงกลับเป็นองศา
    kx = 111.32 * math.cos(math.radians(lat))
    dx, dy = (after["lng"] - before["lng"]) * kx, (after["lat"] - before["lat"]) * 110.57
    norm = math.hypot(dx, dy) or 1.0
    px, py = -dy / norm, dx / norm
    leg = sum(1 for idx in route["stop_idx"] if idx < bad[0])  # แทรกก่อน stop ถัดไปหลังจุดเสี่ยง
    vias = []
    for side in (1, -1):
        v_lat = lat + side * py * DETOUR_OFFSET_KM / 110.57
        v_lng = lng + side * px * DETOUR_OFFSET_KM / kx
        if in_thailand(v_lat, v_lng):
            vias.append((leg, Place(lat=round(v_lat, 4), lng=round(v_lng, 4))))
    return risky, vias


def find_detour(main: dict, risky: list[dict], vias: list[tuple[int, Place]], stops: list[Place],
                deadline: float) -> Optional[dict]:
    """ลองทุกจุดผ่านเท่าที่เวลาพอ เลือกเส้นที่เร็วที่สุดที่ห่างจุดเสี่ยงเกิน HAZARD_RADIUS_KM
    และไม่ช้าเกิน MAX_SLOWER_RATIO (ดันออกข้างหนึ่งอาจได้ถนนอ้อมภูเขา อีกข้างได้ทางหลวง)"""
    found = []
    for leg, via in vias:
        if deadline - time.monotonic() < DETOUR_MIN_LEFT:
            break
        try:
            body = osrm_request([*stops[:leg], via, *stops[leg:]])
        except ApiError:
            continue
        route = to_route("r2", body["routes"][0], [w["location"] for w in body["waypoints"]], via=leg)
        if route["duration_min"] > main["duration_min"] * MAX_SLOWER_RATIO:
            continue
        if min(haversine_km(p, g) for p in risky for g in route["geometry"]) > HAZARD_RADIUS_KM:
            found.append(route)
    return min(found, key=lambda r: r["duration_min"], default=None)


def evaluate(routes: list[dict], timeout: float) -> Optional[dict]:
    """ส่งทุกเส้นไป risk-decision ในคำขอเดียว None = ประเมินไม่ได้"""
    try:
        return call("RISK_DECISION_URL", "POST", "/api/v1/risk/evaluate", timeout=timeout, json={
            "routes": [{"route_id": r["route_id"], "duration_min": r["duration_min"], "points": r["points"]}
                       for r in routes],
        })
    except ApiError:
        return None  # ยังส่งเส้นทางกลับได้ แค่ไม่รู้ความเสี่ยง (RUNBOOK หัวข้อ C)


@app.post("/api/v1/routes/plan")
def plan_routes(body: PlanIn):
    deadline = time.monotonic() + PLAN_BUDGET
    if body.departure_time.tzinfo is None:
        raise ApiError("VALIDATION_ERROR", "departure_time ต้องมี timezone")
    stops = [body.origin, *body.waypoints, body.destination]
    routes = fetch_routes(stops)
    for r in routes:
        r["points"], r["stop_idx"] = risk_points(r, stops, body.departure_time)
    risk = evaluate(routes, RISK_TIMEOUT)

    # งาน 5.4: ได้เส้นเดียวและเสี่ยง ลองสร้างเส้นเลี่ยงเอง ถ้าเวลาไม่พอหรือหาไม่ได้ใช้ผลรอบแรก
    # (build_plan ใส่ ALTERNATIVE_ROUTES_UNAVAILABLE ให้) รอบสองรอ risk-decision แค่เวลาที่เหลือ
    if risk and len(routes) == 1 and risk["routes"][0]["risk_level"] in DETOUR_LEVELS:
        risky, vias = detour_vias(routes[0], risk["routes"][0]["points"], stops)
        detour = find_detour(routes[0], risky, vias, stops, deadline) if vias else None
        if detour:
            detour["points"], detour["stop_idx"] = risk_points(detour, stops, body.departure_time)
            left = min(RISK_TIMEOUT, deadline - time.monotonic())  # ไม่เกินที่ CONTRACT ให้ และไม่เกินเวลาที่เหลือ
            second = evaluate([routes[0], detour], left) if left >= 5 else None
            if second:
                routes, risk = [routes[0], detour], second
    return ok(build_plan(body, stops, routes, risk))
