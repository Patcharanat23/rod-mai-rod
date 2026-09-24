"""weather-disaster (stub)

ตอนนี้ตอบข้อมูลตัวอย่าง ให้คนอื่นต่อได้ก่อน
ของจริง: Open-Meteo (พยากรณ์), GDACS + USGS (ภัยพิบัติ), Thaiwater / TMD (ถ้าได้ key)
แปลงหน่วยให้ตรง docs/CONTRACT.md หัวข้อ 4 และ cache ทุกคำขอ
DEMO_MODE=true ต้องตอบจากข้อมูลที่บันทึกไว้ ไม่เรียกเน็ตเลย
"""
import os
from datetime import datetime, timezone

from fastapi import FastAPI
from pydantic import BaseModel

import hazard_feeds
import weather
from envelope import ApiError, ok, setup
from geo import to_iso

app = FastAPI(title="weather-disaster")
setup(app, "weather-disaster")

DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"


class TimedPoint(BaseModel):
    lat: float
    lng: float
    time: datetime


class PointsIn(BaseModel):
    points: list[TimedPoint]


def sample_forecast(time_iso: str) -> dict:
    return {"time": time_iso, "rain_mm_per_h": 0.2, "wind_kmh": 9, "temp_c": 29, "condition_th": "มีเมฆบางส่วน"}


@app.post("/api/v1/forecast/points")
def forecast_points(body: PointsIn):
    for p in body.points:
        if p.time.tzinfo is None:
            raise ApiError("VALIDATION_ERROR", "time ต้องมี timezone")
    forecasts, warnings = weather.forecast_points([(p.lat, p.lng, p.time) for p in body.points])
    out = [{"lat": p.lat, "lng": p.lng, "forecast": fc} for p, fc in zip(body.points, forecasts)]
    return ok({"points": out, "warnings": warnings})


@app.get("/api/v1/area")
def area(lat: float, lng: float):
    now = to_iso(datetime.now(timezone.utc))
    cells = [
        {"lat": round(lat + dy * 0.22, 4), "lng": round(lng + dx * 0.22, 4), "forecast": sample_forecast(now)}
        for dy in (-1, 0, 1) for dx in (-1, 0, 1)
    ]
    return ok({"center": {"lat": lat, "lng": lng}, "cells": cells, "updated_at": now, "warnings": []})


@app.get("/api/v1/hazards")
def hazards(min_lat: float, min_lng: float, max_lat: float, max_lng: float):
    if min_lat > max_lat or min_lng > max_lng:
        raise ApiError("VALIDATION_ERROR", "กรอบพิกัดไม่ถูกต้อง ค่า min ต้องไม่มากกว่า max")
    found, warnings = hazard_feeds.get_hazards((min_lat, min_lng, max_lat, max_lng))
    return ok({"hazards": found, "warnings": warnings})
