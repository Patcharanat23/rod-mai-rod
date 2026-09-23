"""routing-engine (stub)

ส่วนที่ต่อไว้จริงแล้ว: ส่งทุกเส้นไป risk-decision ในคำขอเดียว แล้วประกอบ TripPlan จากผลที่ได้ (build_plan)
ส่วนที่ยังเป็น stub: fetch_routes() ต่อจุดเป็นเส้นตรงเส้นเดียว ของจริงเรียก OSRM ดู README
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from envelope import ApiError, call, ok, setup
from geo import haversine_km, to_iso

app = FastAPI(title="routing-engine")
setup(app, "routing-engine")

RISK_TIMEOUT = 30  # วินาที ตาม CONTRACT หัวข้อ 3


class Place(BaseModel):
    lat: float
    lng: float
    name: Optional[str] = None


class PlanIn(BaseModel):
    origin: Place
    destination: Place
    departure_time: datetime
    waypoints: list[Place] = []


def fetch_routes(stops: list[Place]) -> list[dict]:
    """คืนเส้นทางทั้งหมด เส้นแรกต้องเป็นเส้นหลัก (เร็วที่สุด)

    แต่ละเส้น: {route_id, duration_min, distance_km, geometry: [{lat, lng}],
               stop_minutes: [นาทีสะสมตอนถึงแต่ละ stop เริ่มที่ 0], samples: [{lat, lng, minute}]}
    samples คือจุดตัวอย่างระหว่างทางประมาณทุก 20 กม. พร้อมนาทีสะสม (ไม่รวม stop)

    TODO(routing-engine): เรียก OSRM แทนเส้นตรง ดู README หัวข้อ "เริ่มจากตรงไหน"
    """
    stop_minutes, distance_km = [0.0], 0.0
    for a, b in zip(stops, stops[1:]):
        leg = haversine_km(a.model_dump(), b.model_dump()) * 1.25  # ถนนจริงอ้อมกว่าเส้นตรง
        distance_km += leg
        stop_minutes.append(stop_minutes[-1] + leg / 75 * 60)
    return [{
        "route_id": "r1",
        "duration_min": round(stop_minutes[-1]),
        "distance_km": round(distance_km),
        "geometry": [{"lat": s.lat, "lng": s.lng} for s in stops],
        "stop_minutes": stop_minutes,
        "samples": [],
    }]


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
