"""tools ที่ LLM เรียกได้ ทุกตัวทำงานผ่าน backend() ด้วย token ของผู้ใช้

LLM ส่งแค่ trip_no และเวลาแบบคน (เลื่อนกี่วัน / กี่ชั่วโมง / กี่โมงตามเวลาไทย) การคิดวันที่และแปลง UTC ทำในโค้ดนี้
ตัวเลขอากาศและระดับความเสี่ยงที่คืนให้ LLM มาจากระบบทั้งหมด
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from envelope import ApiError
from rules import BANGKOK, RISK_TH, Backend, departs, find_trip, label, nearest_trip, thai_time, to_utc_iso

HHMM = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
YMD = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
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
            "date": {"type": "string",
                     "description": "วันออกใหม่ตามเวลาไทย YYYY-MM-DD ใช้เมื่อผู้ใช้บอกวันที่ตรงๆ เช่น 29 ก.ย. ไม่ส่ง = วันเดิม"},
            "shift_hours": {"type": "integer",
                            "description": "เลื่อนจากเวลาเดิมกี่ชั่วโมง เช่น ออกไป 3 ชม. = 3 เร็วขึ้น 2 ชม. = -2 "
                                           "ไม่ต้องรู้เวลาเดิม ระบบคิดให้"},
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
    {"type": "function", "function": {
        "name": "nearby_places",
        "description": "สถานที่เที่ยวจริงรอบสถานที่หนึ่ง (รัศมี 5 กม.) ใช้ตอนผู้ใช้ขอให้แนะนำที่เที่ยว แนะนำจากผลนี้",
        "parameters": {"type": "object", "properties": {
            "place": {"type": "string", "description": "ชื่อสถานที่หรือเมือง เช่น เชียงใหม่"},
        }, "required": ["place"]},
    }},
    {"type": "function", "function": {
        "name": "create_trip",
        "description": "สร้างทริปใหม่แล้ววางแผนเส้นทางให้ทันที ต้องรู้ต้นทาง ปลายทาง วันและเวลาออก ขาดข้อไหนให้ถามก่อน",
        "parameters": {"type": "object", "properties": {
            "origin": {"type": "string", "description": "ชื่อต้นทาง เช่น กรุงเทพ"},
            "destination": {"type": "string", "description": "ชื่อปลายทาง"},
            "date": {"type": "string", "description": "วันออกตามเวลาไทย YYYY-MM-DD"},
            "time": {"type": "string", "description": "เวลาออกตามเวลาไทย HH:MM"},
            "stops": {"type": "array", "items": {"type": "string"}, "description": "จุดแวะตามลำดับ ไม่เกิน 5 จุด"},
        }, "required": ["origin", "destination", "date", "time"]},
    }},
    {"type": "function", "function": {
        "name": "update_trip_places",
        "description": "แก้ต้นทาง ปลายทาง หรือจุดแวะของทริป แล้ววางแผนใหม่ให้ ส่งเฉพาะช่องที่เปลี่ยน",
        "parameters": {"type": "object", "properties": {
            "trip_no": {"type": "integer"},
            "origin": {"type": "string", "description": "ต้นทางใหม่"},
            "destination": {"type": "string", "description": "ปลายทางใหม่"},
            "stops": {"type": "array", "items": {"type": "string"},
                      "description": "จุดแวะชุดใหม่ทั้งหมดตามลำดับ (แทนของเดิม) [] = ไม่แวะ"},
        }, "required": ["trip_no"]},
    }},
]

# tools ที่แก้ข้อมูล ถ้าเรียกสำเร็จไปแล้วห้ามสลับไปผู้ให้บริการตัวสำรองแล้วเริ่มใหม่ (จะเลื่อนซ้ำ)
MUTATING = {"update_trip_time", "plan_trip", "create_trip", "update_trip_places"}
MAX_STOPS = 5  # CONTRACT หัวข้อ 4


def place_name(p: dict) -> str:
    return p.get("name") or f"{p['lat']:.3f}, {p['lng']:.3f}"


PLAN_STATUS_TH = {"FRESH": "วางแผนแล้ว", "STALE": "แผนเก่า ต้องกด Plan ใหม่", "NONE": "ยังไม่ได้วางแผน"}


# ส่งคำไทยให้ LLM ใช้ตอบ ไม่อย่างนั้นจะพิมพ์รหัสอย่าง LOW / FRESH ให้ผู้ใช้เห็น
def plan_summary(plan: dict) -> dict:
    return {"risk_th": RISK_TH.get(plan.get("risk_level"), "ไม่ทราบ"), "recommendation": plan.get("recommendation"),
            "summary_th": plan.get("summary_th"), "warnings": plan.get("warnings", [])}


def context_text(trips: list[dict], now: Optional[datetime] = None) -> str:
    """เวลาตอนนี้ + ทริปของผู้ใช้ ให้ LLM รู้ว่า "ทริปที่ใกล้ที่สุด" หรือ "ทริปไปเชียงใหม่" คือเลขอะไร (ไม่เกิน 10 ทริป)"""
    now = now or datetime.now(timezone.utc)
    lines = [f"ข้อมูลบริบท: ตอนนี้ {now.astimezone(BANGKOK):%Y-%m-%d %H:%M} น. เวลาไทย"]
    near = nearest_trip(trips, now)
    for t in sorted(trips, key=departs)[:10]:
        mark = " (ทริปที่ใกล้ที่สุด)" if near and t["trip_no"] == near["trip_no"] else ""
        lines.append(f"- {label(t['trip_no'])}{mark}: {route_th(t)} ออก {thai_time(t['departure_time'])}")
    if not trips:
        lines.append("ผู้ใช้ยังไม่มีทริป")
    return "\n".join(lines)


def trip_no(args: dict) -> Optional[int]:
    return int(args["trip_no"]) if args.get("trip_no") is not None else None


def list_trips(args: dict, backend: Backend, auth: str) -> tuple[dict, list]:
    trips = backend("GET", "/api/v1/trips", auth)
    return {"trips": [{
        "trip_no": t["trip_no"], "name": label(t["trip_no"]),
        "origin": place_name(t["origin"]), "destination": place_name(t["destination"]),
        "departure_th": thai_time(t["departure_time"]),
        "plan_th": PLAN_STATUS_TH.get(t.get("plan_status"), "ไม่ทราบ"),
    } for t in trips]}, []


def update_trip_time(args: dict, backend: Backend, auth: str, now: Optional[datetime] = None) -> tuple[dict, list]:
    trip, ask = find_trip(trip_no(args), backend, auth)
    if ask:
        return {"error": ask}, []
    shift = int(args.get("shift_days") or 0)
    if not 0 <= shift <= MAX_SHIFT_DAYS:
        return {"error": f"เลื่อนได้ 0-{MAX_SHIFT_DAYS} วัน"}, []
    shift_hours = int(args.get("shift_hours") or 0)
    if abs(shift_hours) > MAX_SHIFT_DAYS * 24:
        return {"error": f"เลื่อนได้ไม่เกิน {MAX_SHIFT_DAYS * 24} ชั่วโมง"}, []
    new = datetime.fromisoformat(trip["departure_time"].replace("Z", "+00:00")).astimezone(BANGKOK)
    new += timedelta(days=shift)
    if args.get("date"):
        d = YMD.match(str(args["date"]).strip())
        if not d:
            return {"error": "วันที่ต้องเป็นรูปแบบ YYYY-MM-DD"}, []
        new = new.replace(year=int(d.group(1)), month=int(d.group(2)), day=int(d.group(3)))
    if args.get("time"):
        m = HHMM.match(str(args["time"]).strip())
        if not m:
            return {"error": "เวลาต้องเป็นรูปแบบ HH:MM"}, []
        # วันตามเวลาไทย แล้วค่อยแปลงเป็น UTC
        new = new.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
    new += timedelta(hours=shift_hours)
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
        "name": label(trip["trip_no"]), "plan_th": PLAN_STATUS_TH.get(trip.get("plan_status"), "ไม่ทราบ"),
        **plan_summary(plan),
        "waypoints": [{"name": w.get("name"), "eta_th": thai_time(w["eta"]), "forecast": w.get("forecast"),
                       "risk_th": RISK_TH.get(w.get("risk_level"), "ไม่ทราบ")} for w in plan.get("waypoints", [])],
    }, []


def resolve_place(query, backend: Backend, auth: str) -> tuple[Optional[dict], Optional[str]]:
    """ชื่อที่ผู้ใช้พิมพ์ > ผลแรกของ /places/search คืน (สถานที่, None) หรือ (None, เหตุผลให้ถามผู้ใช้)"""
    q = str(query or "").strip()
    found = backend("GET", "/api/v1/places/search", auth, params={"q": q})["places"] if len(q) >= 2 else []
    if not found:
        return None, f"หาสถานที่ \"{q}\" ไม่เจอ ให้ถามผู้ใช้ชื่อที่ชัดขึ้น เช่น ใส่อำเภอหรือจังหวัด"
    return {"lat": found[0]["lat"], "lng": found[0]["lng"], "name": found[0]["name"]}, None


def resolve_stops(names: list, backend: Backend, auth: str) -> tuple[list[dict], Optional[str]]:
    if len(names) > MAX_STOPS:
        return [], f"จุดแวะได้ไม่เกิน {MAX_STOPS} จุด"
    stops = []
    for n in names:
        place, err = resolve_place(n, backend, auth)
        if err:
            return [], err
        stops.append(place)
    return stops, None


def route_th(trip: dict) -> str:
    return " > ".join(place_name(p) for p in [trip["origin"], *(trip.get("waypoints") or []), trip["destination"]])


def saved_and_planned(trip: dict, backend: Backend, auth: str, result: dict) -> dict:
    """บันทึกแล้ววางแผนต่อ แผนพังก็ยังบอกผู้ใช้ได้ว่าบันทึกแล้ว"""
    result.update({"name": label(trip["trip_no"]), "route_th": route_th(trip), "departure_th": thai_time(trip["departure_time"])})
    try:
        result["plan"] = plan_summary(backend("POST", f"/api/v1/trips/{trip['trip_id']}/plan", auth))
    except ApiError as e:
        result["plan_error"] = f"บันทึกแล้วแต่วางแผนเส้นทางไม่สำเร็จ ({e.message}) ให้ผู้ใช้กด Plan ในหน้า My Trip"
    return result


def nearby_places(args: dict, backend: Backend, auth: str) -> tuple[dict, list]:
    place, err = resolve_place(args.get("place"), backend, auth)
    if err:
        return {"error": err}, []
    params = {"lat": place["lat"], "lng": place["lng"]}
    try:
        found = backend("GET", "/api/v1/places/nearby", auth, params=params)["places"]
    except ApiError as e:
        if e.code != "UPSTREAM_TIMEOUT":
            raise
        # ครั้งแรกของพื้นที่ใหม่ api-backend ตอบไม่ทันแต่โหลดต่อเบื้องหลัง ถามซ้ำอีกครั้งมักได้แล้ว
        found = backend("GET", "/api/v1/places/nearby", auth, params=params)["places"]
    return {"around": place["name"], "places": [{"name": p["name"], "kind_th": p.get("kind_th")} for p in found]}, []


def create_trip(args: dict, backend: Backend, auth: str, now: Optional[datetime] = None) -> tuple[dict, list]:
    d = YMD.match(str(args.get("date") or "").strip())
    t = HHMM.match(str(args.get("time") or "").strip())
    if not d or not t:
        return {"error": "ต้องรู้วันและเวลาออก ให้ถามผู้ใช้"}, []
    when = datetime(int(d.group(1)), int(d.group(2)), int(d.group(3)), int(t.group(1)), int(t.group(2)), tzinfo=BANGKOK)
    if when <= (now or datetime.now(timezone.utc)):
        return {"error": f"เวลาออก {thai_time(to_utc_iso(when))} ผ่านไปแล้ว"}, []
    origin, err = resolve_place(args.get("origin"), backend, auth)
    if err:
        return {"error": err}, []
    destination, err = resolve_place(args.get("destination"), backend, auth)
    if err:
        return {"error": err}, []
    stops, err = resolve_stops(args.get("stops") or [], backend, auth)
    if err:
        return {"error": err}, []
    trip = backend("POST", "/api/v1/trips", auth, json={
        "origin": origin, "destination": destination, "departure_time": to_utc_iso(when), "waypoints": stops})
    actions = [{"type": "TRIP_CREATED", "trip_id": trip["trip_id"], "trip_no": trip["trip_no"]}]
    return saved_and_planned(trip, backend, auth, {"created": True}), actions


def update_trip_places(args: dict, backend: Backend, auth: str) -> tuple[dict, list]:
    trip, ask = find_trip(trip_no(args), backend, auth)
    if ask:
        return {"error": ask}, []
    patch: dict = {}
    for key in ("origin", "destination"):
        if args.get(key):
            patch[key], err = resolve_place(args[key], backend, auth)
            if err:
                return {"error": err}, []
    if args.get("stops") is not None:
        patch["waypoints"], err = resolve_stops(args["stops"], backend, auth)
        if err:
            return {"error": err}, []
    if not patch:
        return {"error": "ไม่ได้บอกว่าจะเปลี่ยนต้นทาง ปลายทาง หรือจุดแวะ"}, []
    saved = backend("PATCH", f"/api/v1/trips/{trip['trip_id']}", auth, json=patch)
    actions = [{"type": "TRIP_UPDATED", "trip_id": trip["trip_id"], "trip_no": trip["trip_no"]}]
    return saved_and_planned(saved, backend, auth, {"updated": True}), actions


HANDLERS = {"list_trips": list_trips, "update_trip_time": update_trip_time,
            "plan_trip": plan_trip, "get_trip_weather": get_trip_weather,
            "nearby_places": nearby_places, "create_trip": create_trip, "update_trip_places": update_trip_places}


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
