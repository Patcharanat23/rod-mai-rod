"""api-backend (stub)

การส่งต่อไป routing-engine / weather-disaster / assistant-agent ต่อไว้จริงแล้ว
ที่ยังเป็น stub: ผู้ใช้และทริปเก็บในหน่วยความจำ (หายเมื่อ restart) และ token ปลอม
ของจริงค่อยๆ แทนทีละส่วน: ต่อ Postgres, bcrypt, JWT
ห้ามลบ endpoint ไหนออกก่อนมีของจริงมาแทน และรูปแบบข้อมูลต้องตรงกับ docs/CONTRACT.md หัวข้อ 6
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Header
from pydantic import BaseModel, Field

from envelope import ApiError, call, ok, setup
from geo import in_thailand, to_iso

app = FastAPI(title="api-backend")
setup(app, "api-backend")

DEMO_USER = {"user_id": "u-0001", "email": "demo@example.com"}
TRIPS: dict[str, dict] = {}
MAX_WAYPOINTS = 5

# timeout (วินาที) ตาม CONTRACT หัวข้อ 3
ROUTING_TIMEOUT = 45
WEATHER_TIMEOUT = 10
ASSISTANT_TIMEOUT = 100
SAFETY_TIMEOUT = 10


class Place(BaseModel):
    lat: float
    lng: float
    name: Optional[str] = None


class Credentials(BaseModel):
    email: str
    password: str = Field(min_length=6)


class TripCreate(BaseModel):
    origin: Place
    destination: Place
    departure_time: datetime
    waypoints: list[Place] = []


class TripPatch(BaseModel):
    origin: Optional[Place] = None
    destination: Optional[Place] = None
    departure_time: Optional[datetime] = None
    waypoints: Optional[list[Place]] = None


class ChatIn(BaseModel):
    message: str
    history: list[dict] = []


def current_user(authorization: Optional[str]) -> dict:
    # stub: token อะไรก็ได้ที่ขึ้นต้นด้วย Bearer ถือเป็น demo user
    if not authorization or not authorization.startswith("Bearer "):
        raise ApiError("UNAUTHORIZED", "กรุณาเข้าสู่ระบบก่อน")
    return DEMO_USER


def check_places(places: list[Place]) -> None:
    for p in places:
        if not in_thailand(p.lat, p.lng):
            raise ApiError("OUT_OF_THAILAND", "ตอนนี้รองรับเฉพาะสถานที่ในประเทศไทย")


def check_time(dt: datetime) -> None:
    if dt.tzinfo is None:
        raise ApiError("VALIDATION_ERROR", "departure_time ต้องมี timezone เช่น 2026-09-28T01:00:00Z")


def get_owned_trip(trip_id: str, user: dict) -> dict:
    trip = TRIPS.get(trip_id)
    if trip is None:
        raise ApiError("NOT_FOUND", "ไม่พบทริปนี้")
    if trip["user_id"] != user["user_id"]:
        raise ApiError("FORBIDDEN", "ทริปนี้ไม่ใช่ของคุณ")
    return trip


def next_trip_no(user_id: str) -> int:
    nos = [t["trip_no"] for t in TRIPS.values() if t["user_id"] == user_id]
    return max(nos, default=0) + 1


# ---------- auth ----------

@app.post("/api/v1/auth/register")
def register(body: Credentials):
    return ok({"user_id": DEMO_USER["user_id"], "email": body.email})


@app.post("/api/v1/auth/login")
def login(body: Credentials):
    return ok({"token": "dev-token", "user": DEMO_USER})


@app.get("/api/v1/me")
def me(authorization: Optional[str] = Header(None)):
    return ok(current_user(authorization))


# ---------- trips ----------

@app.get("/api/v1/trips")
def list_trips(authorization: Optional[str] = Header(None)):
    user = current_user(authorization)
    mine = [t for t in TRIPS.values() if t["user_id"] == user["user_id"]]
    return ok(sorted(mine, key=lambda t: t["departure_time"]))


@app.get("/api/v1/trips/upcoming")
def upcoming_trip(authorization: Optional[str] = Header(None)):
    user = current_user(authorization)
    now = to_iso(datetime.now(timezone.utc))
    future = [t for t in TRIPS.values() if t["user_id"] == user["user_id"] and t["departure_time"] >= now]
    return ok(min(future, key=lambda t: t["departure_time"]) if future else None)


@app.post("/api/v1/trips")
def create_trip(body: TripCreate, authorization: Optional[str] = Header(None)):
    user = current_user(authorization)
    check_time(body.departure_time)
    if len(body.waypoints) > MAX_WAYPOINTS:
        raise ApiError("VALIDATION_ERROR", f"หมุดระหว่างทางได้ไม่เกิน {MAX_WAYPOINTS} จุด")
    check_places([body.origin, body.destination, *body.waypoints])
    trip_id = str(uuid.uuid4())
    trip = {
        "trip_id": trip_id,
        "trip_no": next_trip_no(user["user_id"]),
        "user_id": user["user_id"],
        "origin": body.origin.model_dump(),
        "destination": body.destination.model_dump(),
        "departure_time": to_iso(body.departure_time),
        "waypoints": [w.model_dump() for w in body.waypoints],
        "plan_status": "NONE",
        "plan": None,
    }
    TRIPS[trip_id] = trip
    return ok(trip)


@app.get("/api/v1/trips/{trip_id}")
def get_trip(trip_id: str, authorization: Optional[str] = Header(None)):
    return ok(get_owned_trip(trip_id, current_user(authorization)))


@app.patch("/api/v1/trips/{trip_id}")
def patch_trip(trip_id: str, body: TripPatch, authorization: Optional[str] = Header(None)):
    trip = get_owned_trip(trip_id, current_user(authorization))
    changes = body.model_dump(exclude_none=True)
    if "departure_time" in changes:
        check_time(body.departure_time)
        changes["departure_time"] = to_iso(body.departure_time)
    if body.waypoints is not None and len(body.waypoints) > MAX_WAYPOINTS:
        raise ApiError("VALIDATION_ERROR", f"หมุดระหว่างทางได้ไม่เกิน {MAX_WAYPOINTS} จุด")
    check_places([p for p in (body.origin, body.destination) if p] + (body.waypoints or []))
    trip.update(changes)
    if trip["plan"] is not None:
        trip["plan_status"] = "STALE"
    return ok(trip)


@app.delete("/api/v1/trips/{trip_id}")
def delete_trip(trip_id: str, authorization: Optional[str] = Header(None)):
    get_owned_trip(trip_id, current_user(authorization))
    del TRIPS[trip_id]
    return ok({"trip_id": trip_id, "deleted": True})


@app.post("/api/v1/trips/{trip_id}/plan")
def plan_trip(trip_id: str, authorization: Optional[str] = Header(None)):
    trip = get_owned_trip(trip_id, current_user(authorization))
    routes = call("ROUTING_ENGINE_URL", "POST", "/api/v1/routes/plan", timeout=ROUTING_TIMEOUT, json={
        "origin": trip["origin"],
        "destination": trip["destination"],
        "waypoints": trip["waypoints"],
        "departure_time": trip["departure_time"],
    })
    plan = {"trip_id": trip["trip_id"], "trip_no": trip["trip_no"], **routes}
    trip["plan"], trip["plan_status"] = plan, "FRESH"
    return ok(plan)


# ---------- weather / hazards ----------

@app.get("/api/v1/weather/area")
def weather_area(lat: float, lng: float, authorization: Optional[str] = Header(None)):
    current_user(authorization)
    try:
        return ok(call("WEATHER_DISASTER_URL", "GET", "/api/v1/area", timeout=WEATHER_TIMEOUT,
                       params={"lat": lat, "lng": lng}))
    except ApiError:
        # ข้อมูลไม่ครบไม่ใช่ error หน้าเว็บยังแสดงแผนที่ได้ (CONTRACT หัวข้อ 3)
        return ok({"center": {"lat": lat, "lng": lng}, "cells": [], "updated_at": None,
                   "warnings": ["WEATHER_UNAVAILABLE"]})


@app.get("/api/v1/hazards")
def hazards(min_lat: float, min_lng: float, max_lat: float, max_lng: float, authorization: Optional[str] = Header(None)):
    current_user(authorization)
    try:
        return ok(call("WEATHER_DISASTER_URL", "GET", "/api/v1/hazards", timeout=WEATHER_TIMEOUT,
                       params={"min_lat": min_lat, "min_lng": min_lng, "max_lat": max_lat, "max_lng": max_lng}))
    except ApiError:
        return ok({"hazards": [], "warnings": ["HAZARD_FEED_UNAVAILABLE"]})


# ---------- safety ----------

@app.get("/api/v1/safety/emergency")
def safety_emergency(hazard_type: str, authorization: Optional[str] = Header(None)):
    current_user(authorization)
    return ok(call("SAFETY_KNOWLEDGE_URL", "GET", "/api/v1/safety/emergency", timeout=SAFETY_TIMEOUT,
                   params={"hazard_type": hazard_type}))


# ---------- assistant ----------

@app.post("/api/v1/assistant/chat")
def assistant_chat(body: ChatIn, authorization: Optional[str] = Header(None)):
    current_user(authorization)
    # ส่ง token ของผู้ใช้ไปด้วย assistant-agent ต้องใช้เรียกกลับมาแก้ทริป (CONTRACT หัวข้อ 5)
    return ok(call("ASSISTANT_AGENT_URL", "POST", "/api/v1/chat", timeout=ASSISTANT_TIMEOUT,
                   json=body.model_dump(), headers={"Authorization": authorization}))
