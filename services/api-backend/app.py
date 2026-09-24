"""api-backend

ผู้ใช้และทริปเก็บใน Postgres, login ด้วย bcrypt + JWT
การส่งต่อไป routing-engine / weather-disaster / assistant-agent / safety-knowledge ต่อไว้จริงแล้ว
ห้ามลบ endpoint ไหนออกก่อนมีของจริงมาแทน และรูปแบบข้อมูลต้องตรงกับ docs/CONTRACT.md หัวข้อ 6
"""
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Header
from pydantic import BaseModel, Field

import auth
import db
from envelope import ApiError, call, ok, setup
from geo import in_thailand


DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo1234"
MAX_WAYPOINTS = 5


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    # scripts/smoke.sh login ด้วยคู่นี้ ถ้ามีอยู่แล้ว create_user ไม่ทำอะไร
    db.create_user(DEMO_EMAIL, auth.hash_password(DEMO_PASSWORD))
    yield
    db.close_db()


app = FastAPI(title="api-backend", lifespan=lifespan)
setup(app, "api-backend", health_check=db.ping)

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
    if not authorization or not authorization.startswith("Bearer "):
        raise ApiError("UNAUTHORIZED", "กรุณาเข้าสู่ระบบก่อน")
    user = db.find_user(auth.read_token(authorization.removeprefix("Bearer ")))
    if user is None:
        # token ถูกต้องแต่ผู้ใช้ไม่อยู่แล้ว เช่น หลัง make reset
        raise ApiError("UNAUTHORIZED", "กรุณาเข้าสู่ระบบก่อน")
    return user


def check_places(places: list[Place]) -> None:
    for p in places:
        if not in_thailand(p.lat, p.lng):
            raise ApiError("OUT_OF_THAILAND", "ตอนนี้รองรับเฉพาะสถานที่ในประเทศไทย")


def check_time(dt: datetime) -> None:
    if dt.tzinfo is None:
        raise ApiError("VALIDATION_ERROR", "departure_time ต้องมี timezone เช่น 2026-09-28T01:00:00Z")


def normalize_email(email: str) -> str:
    email = email.strip().lower()
    if "@" not in email:
        raise ApiError("VALIDATION_ERROR", "รูปแบบอีเมลไม่ถูกต้อง")
    return email


def get_owned_trip(trip_id: str, user: dict) -> dict:
    try:
        uuid.UUID(trip_id)
    except ValueError:
        # id ผิดรูปแบบส่งเข้า Postgres จะ error ถือว่าไม่เจอ
        raise ApiError("NOT_FOUND", "ไม่พบทริปนี้")
    trip = db.get_trip(trip_id)
    if trip is None:
        raise ApiError("NOT_FOUND", "ไม่พบทริปนี้")
    if trip["user_id"] != user["user_id"]:
        raise ApiError("FORBIDDEN", "ทริปนี้ไม่ใช่ของคุณ")
    return trip


# ---------- auth ----------

@app.post("/api/v1/auth/register")
def register(body: Credentials):
    email = normalize_email(body.email)
    # bcrypt อ่านแค่ 72 ไบต์แรก ภาษาไทยตัวละ 3 ไบต์
    if len(body.password.encode()) > 72:
        raise ApiError("VALIDATION_ERROR", "รหัสผ่านยาวเกินไป")
    user = db.create_user(email, auth.hash_password(body.password))
    if user is None:
        raise ApiError("VALIDATION_ERROR", "อีเมลนี้ถูกใช้สมัครแล้ว")
    return ok(user)


@app.post("/api/v1/auth/login")
def login(body: Credentials):
    user = db.find_user_by_email(normalize_email(body.email))
    if user is None or not auth.check_password(body.password, user["password_hash"]):
        raise ApiError("UNAUTHORIZED", "อีเมลหรือรหัสผ่านไม่ถูกต้อง")
    # เลือก field เอง ห้ามส่ง password_hash ออกไป
    return ok({"token": auth.make_token(user["user_id"]),
               "user": {"user_id": user["user_id"], "email": user["email"]}})


@app.get("/api/v1/me")
def me(authorization: Optional[str] = Header(None)):
    return ok(current_user(authorization))


# ---------- trips ----------

@app.get("/api/v1/trips")
def list_trips(authorization: Optional[str] = Header(None)):
    return ok(db.list_trips(current_user(authorization)["user_id"]))


@app.get("/api/v1/trips/upcoming")
def upcoming_trip(authorization: Optional[str] = Header(None)):
    return ok(db.upcoming_trip(current_user(authorization)["user_id"]))


@app.post("/api/v1/trips")
def create_trip(body: TripCreate, authorization: Optional[str] = Header(None)):
    user = current_user(authorization)
    check_time(body.departure_time)
    if len(body.waypoints) > MAX_WAYPOINTS:
        raise ApiError("VALIDATION_ERROR", f"หมุดระหว่างทางได้ไม่เกิน {MAX_WAYPOINTS} จุด")
    check_places([body.origin, body.destination, *body.waypoints])
    return ok(db.create_trip(user["user_id"], body.origin.model_dump(), body.destination.model_dump(),
                             body.departure_time, [w.model_dump() for w in body.waypoints]))


@app.get("/api/v1/trips/{trip_id}")
def get_trip(trip_id: str, authorization: Optional[str] = Header(None)):
    return ok(get_owned_trip(trip_id, current_user(authorization)))


@app.patch("/api/v1/trips/{trip_id}")
def patch_trip(trip_id: str, body: TripPatch, authorization: Optional[str] = Header(None)):
    get_owned_trip(trip_id, current_user(authorization))
    if body.departure_time is not None:
        check_time(body.departure_time)
    if body.waypoints is not None and len(body.waypoints) > MAX_WAYPOINTS:
        raise ApiError("VALIDATION_ERROR", f"หมุดระหว่างทางได้ไม่เกิน {MAX_WAYPOINTS} จุด")
    check_places([p for p in (body.origin, body.destination) if p] + (body.waypoints or []))
    return ok(db.update_trip(
        trip_id,
        origin=body.origin.model_dump() if body.origin else None,
        destination=body.destination.model_dump() if body.destination else None,
        departure_time=body.departure_time,
        waypoints=[w.model_dump() for w in body.waypoints] if body.waypoints is not None else None,
    ))


@app.delete("/api/v1/trips/{trip_id}")
def delete_trip(trip_id: str, authorization: Optional[str] = Header(None)):
    get_owned_trip(trip_id, current_user(authorization))
    db.delete_trip(trip_id)
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
    db.save_plan(trip_id, plan)
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
