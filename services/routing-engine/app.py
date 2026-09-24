"""routing-engine

fetch_routes() หาเส้นทางจริงจาก OSRM ส่งทุกเส้นไป risk-decision ในคำขอเดียว แล้วประกอบ TripPlan (build_plan)
ยังไม่มี: samples ทุก 20 กม., cache, DEMO_MODE ดู README
"""
import os
from datetime import datetime, timedelta
from typing import Optional

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from envelope import ApiError, call, ok, setup
from geo import to_iso

app = FastAPI(title="routing-engine")
setup(app, "routing-engine")

RISK_TIMEOUT = 30  # วินาที ตาม CONTRACT หัวข้อ 3
OSRM_TIMEOUT = 15  # api-backend รอเรา 45 วิ หักที่รอ risk-decision 30 วิ
OSRM_DEFAULT_URL = "https://router.project-osrm.org"
OSRM_PARAMS = {"alternatives": "3", "overview": "full", "geometries": "geojson",
               "annotations": "duration,distance"}
MAX_GEOMETRY_POINTS = 500  # CONTRACT หัวข้อ 4


class Place(BaseModel):
    lat: float
    lng: float
    name: Optional[str] = None


class PlanIn(BaseModel):
    origin: Place
    destination: Place
    departure_time: datetime
    waypoints: list[Place] = []


def osrm_request(stops: list[Place]) -> dict:
    """คำตอบดิบของ OSRM พิกัดใน URL เป็น lng,lat"""
    coords = ";".join(f"{s.lng},{s.lat}" for s in stops)
    url = f"{os.getenv('OSRM_BASE_URL', OSRM_DEFAULT_URL).rstrip('/')}/route/v1/driving/{coords}"
    try:
        res = httpx.get(url, params=OSRM_PARAMS, timeout=OSRM_TIMEOUT)
        body = res.json()
    except httpx.TimeoutException:
        raise ApiError("UPSTREAM_TIMEOUT", "ระบบหาเส้นทางตอบไม่ทันเวลา ลองใหม่อีกครั้ง")
    except (httpx.HTTPError, ValueError):
        raise ApiError("UPSTREAM_ERROR", "ติดต่อระบบหาเส้นทางไม่ได้ ลองใหม่อีกครั้ง")
    if res.status_code == 429:
        raise ApiError("RATE_LIMITED", "ระบบหาเส้นทางมีคนใช้เยอะ รอสักครู่แล้วลองใหม่")
    if body.get("code") != "Ok" or not body.get("routes"):
        raise ApiError("UPSTREAM_ERROR", "หาเส้นทางไม่ได้ ลองใหม่อีกครั้ง")
    return body


def simplify(coords: list[list[float]], limit: int = MAX_GEOMETRY_POINTS) -> list[dict]:
    """[lng, lat] เป็น {lat, lng} และเลือกจุดห่างเท่าๆ กันให้ไม่เกิน limit โดยเก็บจุดแรกและจุดสุดท้ายไว้เสมอ"""
    if len(coords) > limit:
        step = (len(coords) - 1) / (limit - 1)
        coords = [coords[round(i * step)] for i in range(limit)]
    return [{"lat": lat, "lng": lng} for lng, lat in coords]


def fetch_routes(stops: list[Place]) -> list[dict]:
    """คืนเส้นทางทั้งหมด เส้นแรกต้องเป็นเส้นหลัก (เร็วที่สุด)

    แต่ละเส้น: {route_id, duration_min, distance_km, geometry: [{lat, lng}],
               stop_minutes: [นาทีสะสมตอนถึงแต่ละ stop เริ่มที่ 0], samples: [{lat, lng, minute}]}
    samples คือจุดตัวอย่างระหว่างทางประมาณทุก 20 กม. พร้อมนาทีสะสม (ไม่รวม stop)

    TODO(routing-engine): samples ทุก 20 กม. จาก legs[].annotation
    """
    routes = []
    for i, r in enumerate(osrm_request(stops)["routes"], start=1):
        stop_minutes = [0.0]
        for leg in r["legs"]:
            stop_minutes.append(stop_minutes[-1] + leg["duration"] / 60)
        routes.append({
            "route_id": f"r{i}",
            "duration_min": round(r["duration"] / 60),
            "distance_km": round(r["distance"] / 1000),
            "geometry": simplify(r["geometry"]["coordinates"]),
            "stop_minutes": stop_minutes,
            "samples": [],
        })
    return routes


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


@app.post("/api/v1/routes/plan")
def plan_routes(body: PlanIn):
    if body.departure_time.tzinfo is None:
        raise ApiError("VALIDATION_ERROR", "departure_time ต้องมี timezone")
    stops = [body.origin, *body.waypoints, body.destination]
    routes = fetch_routes(stops)
    for r in routes:
        r["points"], r["stop_idx"] = risk_points(r, stops, body.departure_time)

    try:
        risk = call("RISK_DECISION_URL", "POST", "/api/v1/risk/evaluate", timeout=RISK_TIMEOUT, json={
            "routes": [{"route_id": r["route_id"], "duration_min": r["duration_min"], "points": r["points"]}
                       for r in routes],
        })
    except ApiError:
        risk = None  # ยังส่งเส้นทางกลับได้ แค่ไม่รู้ความเสี่ยง (RUNBOOK หัวข้อ C)
    return ok(build_plan(body, stops, routes, risk))
