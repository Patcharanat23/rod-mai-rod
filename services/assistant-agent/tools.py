"""tools ที่ LLM เรียกได้ ทุกตัวทำงานผ่าน backend() ด้วย token ของผู้ใช้

LLM ส่งแค่ trip_no และเวลาแบบคน (เลื่อนกี่วัน / กี่โมงตามเวลาไทย) การคิดวันที่และแปลง UTC ทำในโค้ดนี้
ตัวเลขอากาศและระดับความเสี่ยงที่คืนให้ LLM มาจากระบบทั้งหมด
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from envelope import ApiError
from rules import BANGKOK, Backend, find_trip, label, thai_time, to_utc_iso

HHMM = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
MAX_SHIFT_DAYS = 14

SCHEMAS = [
    {"type": "function", "function": {
        "name": "list_trips",
        "description": "รายการทริปทั้งหมดของผู้ใช้ พร้อมเลขทริป ต้นทาง ปลายทาง เวลาออก (เวลาไทย) และสถานะแผน",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "update_trip_time",
        "description": "เปลี่ยนเวลาออกเดินทางของทริปแล้ววางแผนเส้นทางใหม่ให้อัตโนมัติ "
                       "ใช้เมื่อผู้ใช้สั่งเลื่อนทริปชัดเจนเท่านั้น ถ้าไม่รู้ว่าทริปไหนให้ถามก่อน",
        "parameters": {"type": "object", "properties": {
            "trip_no": {"type": "integer", "description": "เลขทริป เช่น Trip 01 คือ 1"},
            "shift_days": {"type": "integer", "description": "เลื่อนจากวันเดิมกี่วัน เช่น วันถัดไป = 1 ไม่เลื่อนวัน = 0"},
            "time": {"type": "string", "description": "เวลาออกใหม่ตามเวลาไทย HH:MM เช่น 13:00 ไม่ส่ง = เวลาเดิม"},
        }, "required": ["trip_no"]},
    }},
    {"type": "function", "function": {
        "name": "plan_trip",
        "description": "คำนวณเส้นทางและความเสี่ยงของทริปใหม่ ใช้เมื่อทริปยังไม่มีแผนหรือแผนเก่า (STALE)",
        "parameters": {"type": "object", "properties": {
            "trip_no": {"type": "integer"},
        }, "required": ["trip_no"]},
    }},
    {"type": "function", "function": {
        "name": "get_trip_weather",
        "description": "พยากรณ์อากาศและความเสี่ยงของแต่ละจุดในทริป ณ เวลาที่คาดว่าจะไปถึง จากแผนล่าสุด",
        "parameters": {"type": "object", "properties": {
            "trip_no": {"type": "integer"},
        }, "required": ["trip_no"]},
    }},
]

# tools ที่แก้ข้อมูล ถ้าเรียกสำเร็จไปแล้วห้ามสลับไปผู้ให้บริการตัวสำรองแล้วเริ่มใหม่ (จะเลื่อนซ้ำ)
MUTATING = {"update_trip_time", "plan_trip"}


def place_name(p: dict) -> str:
    return p.get("name") or f"{p['lat']:.3f}, {p['lng']:.3f}"


def plan_summary(plan: dict) -> dict:
    return {"risk_level": plan.get("risk_level"), "recommendation": plan.get("recommendation"),
            "summary_th": plan.get("summary_th"), "warnings": plan.get("warnings", [])}


def trip_no(args: dict) -> Optional[int]:
    return int(args["trip_no"]) if args.get("trip_no") is not None else None


def list_trips(args: dict, backend: Backend, auth: str) -> tuple[dict, list]:
    trips = backend("GET", "/api/v1/trips", auth)
    return {"trips": [{
        "trip_no": t["trip_no"], "name": label(t["trip_no"]),
        "origin": place_name(t["origin"]), "destination": place_name(t["destination"]),
        "departure_th": thai_time(t["departure_time"]), "plan_status": t.get("plan_status"),
    } for t in trips]}, []


def update_trip_time(args: dict, backend: Backend, auth: str, now: Optional[datetime] = None) -> tuple[dict, list]:
    trip, ask = find_trip(trip_no(args), backend, auth)
    if ask:
        return {"error": ask}, []
    shift = int(args.get("shift_days") or 0)
    if not 0 <= shift <= MAX_SHIFT_DAYS:
        return {"error": f"เลื่อนได้ 0-{MAX_SHIFT_DAYS} วัน"}, []
    new = datetime.fromisoformat(trip["departure_time"].replace("Z", "+00:00")).astimezone(BANGKOK)
    new += timedelta(days=shift)
    if args.get("time"):
        m = HHMM.match(str(args["time"]).strip())
        if not m:
            return {"error": "เวลาต้องเป็นรูปแบบ HH:MM"}, []
        # วันตามเวลาไทย แล้วค่อยแปลงเป็น UTC
        new = new.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
    if new.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M") == trip["departure_time"][:16]:
        return {"error": "เวลาใหม่ตรงกับเวลาเดิม ไม่ได้เปลี่ยนอะไร"}, []
    if new <= (now or datetime.now(timezone.utc)):
        return {"error": f"เวลาใหม่ {thai_time(to_utc_iso(new))} ผ่านไปแล้ว"}, []

    tid = trip["trip_id"]
    backend("PATCH", f"/api/v1/trips/{tid}", auth, json={"departure_time": to_utc_iso(new)})
    actions = [{"type": "TRIP_UPDATED", "trip_id": tid, "trip_no": trip["trip_no"]}]
    result = {"updated": True, "name": label(trip["trip_no"]), "departure_th": thai_time(to_utc_iso(new))}
    try:
        result["plan"] = plan_summary(backend("POST", f"/api/v1/trips/{tid}/plan", auth))
    except ApiError as e:
        result["plan_error"] = f"เลื่อนแล้วแต่วางแผนใหม่ไม่สำเร็จ ({e.message}) ให้ผู้ใช้กด Plan ในหน้า My Trip"
    return result, actions


def plan_trip(args: dict, backend: Backend, auth: str) -> tuple[dict, list]:
    trip, ask = find_trip(trip_no(args), backend, auth)
    if ask:
        return {"error": ask}, []
    plan = backend("POST", f"/api/v1/trips/{trip['trip_id']}/plan", auth)
    actions = [{"type": "TRIP_UPDATED", "trip_id": trip["trip_id"], "trip_no": trip["trip_no"]}]
    return {"planned": True, "name": label(trip["trip_no"]), **plan_summary(plan)}, actions


def get_trip_weather(args: dict, backend: Backend, auth: str) -> tuple[dict, list]:
    trip, ask = find_trip(trip_no(args), backend, auth)
    if ask:
        return {"error": ask}, []
    trip = backend("GET", f"/api/v1/trips/{trip['trip_id']}", auth)
    plan = trip.get("plan")
    if plan is None:
        return {"error": f"{label(trip['trip_no'])} ยังไม่ได้วางแผน เรียก plan_trip ก่อน"}, []
    return {
        "name": label(trip["trip_no"]), "plan_status": trip.get("plan_status"), **plan_summary(plan),
        "waypoints": [{"name": w.get("name"), "eta_th": thai_time(w["eta"]), "forecast": w.get("forecast"),
                       "risk_level": w.get("risk_level")} for w in plan.get("waypoints", [])],
    }, []


HANDLERS = {"list_trips": list_trips, "update_trip_time": update_trip_time,
            "plan_trip": plan_trip, "get_trip_weather": get_trip_weather}


def run(name: str, args: dict, backend: Backend, auth: str) -> tuple[dict, list]:
    """คืน (ผลที่ส่งกลับให้ LLM, actions) actions มีเฉพาะเมื่อ api-backend ตอบสำเร็จแล้ว"""
    handler = HANDLERS.get(name)
    if handler is None:
        return {"error": f"ไม่มี tool ชื่อ {name}"}, []
    if not isinstance(args, dict):
        return {"error": "arguments ต้องเป็น object"}, []
    try:
        return handler(args, backend, auth)
    except ApiError as e:
        return {"error": e.message, "code": e.code}, []
    except (TypeError, ValueError):
        return {"error": "arguments ไม่ถูกต้อง"}, []
