"""assistant-agent (stub)

ตอนนี้ตอบข้อความตัวอย่าง ยังไม่แก้ทริปจริง
ของจริง: เรียก LLM ผ่านไลบรารี openai (เปลี่ยนผู้ให้บริการด้วย base_url) ใช้ function calling
แก้ทริปผ่าน backend() เท่านั้น แล้วคืน actions ตาม docs/CONTRACT.md หัวข้อ 6
"""
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Header
from pydantic import BaseModel

from envelope import ApiError, call, ok, setup

app = FastAPI(title="assistant-agent")
setup(app, "assistant-agent")

BACKEND_TIMEOUT = 60  # วินาที ตาม CONTRACT หัวข้อ 3 (PATCH แล้วอาจต้อง /plan ต่อ)
SAFETY_TIMEOUT = 10
BANGKOK = ZoneInfo("Asia/Bangkok")


class ChatIn(BaseModel):
    message: str
    history: list[dict] = []


def backend(method: str, path: str, authorization: str, json=None):
    """เรียก api-backend ด้วยสิทธิ์ของผู้ใช้คนนี้เท่านั้น เช่น backend("GET", "/api/v1/trips", auth)
    ถ้า api-backend ปฏิเสธจะ raise ApiError ห้ามตอบผู้ใช้ว่าสำเร็จในกรณีนั้น"""
    return call("API_BACKEND_URL", method, path, timeout=BACKEND_TIMEOUT, json=json,
                headers={"Authorization": authorization})


def safety_search(query: str, hazard_types: Optional[list[str]] = None) -> list[dict]:
    """คำแนะนำความปลอดภัยจากเอกสารจริง ใช้ตอบคำถามแบบ "น้ำท่วมต้องทำยังไง" แทนให้ LLM แต่งเอง
    คืน [] ถ้าค้นไม่เจอหรือ safety-knowledge ล่ม ส่ง source ไปให้ LLM อ้างอิงด้วย"""
    try:
        data = call("SAFETY_KNOWLEDGE_URL", "POST", "/api/v1/safety/search", timeout=SAFETY_TIMEOUT,
                    json={"query": query, "hazard_types": hazard_types or []})
    except ApiError:
        return []
    return data["results"]


def now_bangkok() -> datetime:
    """คิด "พรุ่งนี้" / "ช่วงบ่าย" จากเวลานี้ แล้วค่อยแปลงเป็น UTC ด้วย .astimezone(timezone.utc)"""
    return datetime.now(BANGKOK)


def try_rules(message: str, authorization: str) -> Optional[dict]:
    """คำสั่งหลัก 3 แบบแบบกฎตายตัว (RUNBOOK หัวข้อ B) ใช้ได้แม้ LLM ล่ม คืน ChatReply หรือ None ถ้าไม่เข้าแบบไหน

    TODO(assistant-agent):
      "เลื่อน Trip NN ไปวันถัดไป"          -> PATCH departure_time + 1 วัน แล้ว POST /plan
      "เลื่อน Trip NN เป็นช่วงเช้า/บ่าย/เย็น" -> 08:00 / 13:00 / 17:00 เวลาไทยของวันเดิม แล้ว POST /plan
      "Trip NN อากาศเป็นยังไง"              -> GET ทริป สรุปจาก plan.waypoints
    หา trip_id จาก trip_no ด้วย backend("GET", "/api/v1/trips", authorization)
    """
    return None


@app.post("/api/v1/chat")
def chat(body: ChatIn, authorization: Optional[str] = Header(None)):
    if not authorization:
        raise ApiError("UNAUTHORIZED", "ต้องส่ง Authorization ของผู้ใช้มาด้วย")
    if not body.message.strip():
        raise ApiError("VALIDATION_ERROR", "ข้อความว่าง")

    reply = try_rules(body.message, authorization)
    if reply is not None:
        return ok(reply)
    # TODO(assistant-agent): เรียก LLM พร้อม tools แล้วถ้าล่มทั้งตัวหลักและตัวสำรอง ตอบพร้อม LLM_UNAVAILABLE
    return ok({
        "reply": "ตอนนี้ยังเป็นระบบตัวอย่างอยู่ ถามเรื่องที่เที่ยวหรือสั่งเลื่อนทริปได้เมื่อเชื่อมของจริงแล้ว",
        "actions": [],
        "warnings": [],
    })
