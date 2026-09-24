"""risk-decision (stub)

ส่วนที่ต่อไว้จริงแล้ว: ขอพยากรณ์ ณ เวลาที่ไปถึงของทุกจุดทุกเส้นจาก weather-disaster ในคำขอเดียว
คิดระดับตามเกณฑ์ CONTRACT หัวข้อ 4 และจุดที่ไม่มีข้อมูลเป็น null พร้อม WEATHER_UNAVAILABLE
หมุดภัยในรัศมี 20 กม. รอบแต่ละจุดก็รวมเข้ากับระดับความเสี่ยงแล้ว (7.1)
risk_score คิดจากความรุนแรงจริงของปัจจัยที่แย่ที่สุดแล้ว ไม่ใช่ค่าคงที่ (7.2)
summary_th บอกสาเหตุ ระยะทางจากจุดเริ่มต้น เวลาไทยโดยประมาณ และควรทำอะไรแล้ว (7.3)
DELAY (เลื่อนออก +3/+6 ชม. เช็คเส้นหลักอย่างเดียว) ก็ทำแล้วเช่นกัน (7.4 เสริม)
แก้แล้วตามรีวิว PR #40 รอบ 1: จุดไม่มีข้อมูลตอนเลื่อนเวลาไม่ถูกนับเป็นปลอดภัยอีกต่อไป และ
warning ของจุดเลื่อนเวลาไม่รั่วไปปนกับจุดจริงแล้ว
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from envelope import ApiError, call, ok, setup
from geo import haversine_km, to_iso

app = FastAPI(title="risk-decision")
setup(app, "risk-decision")

WEATHER_TIMEOUT = 10  # วินาที ตาม CONTRACT หัวข้อ 3

# เกณฑ์ตาม CONTRACT หัวข้อ 4 เก็บไว้ที่เดียว ค่าขอบพอดีนับเป็น MEDIUM
RAIN_MEDIUM, RAIN_HIGH_ABOVE = 10.0, 35.0
WIND_MEDIUM, WIND_HIGH_ABOVE = 40.0, 61.0
MAX_SLOWER_RATIO = 1.5
HAZARD_RADIUS_KM = 20.0
# ระยะ padding ของกรอบพิกัดตอนขอหมุดภัย กันหมุดใกล้ขอบรัศมีหลุดกรอบ (1 องศา ~ 111 กม.)
_BBOX_PAD_DEG = HAZARD_RADIUS_KM / 111.0
SCORE_RANGE = {"LOW": (0, 33), "MEDIUM": (34, 66), "HIGH": (67, 100)}
_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
THAI_TZ = timezone(timedelta(hours=7))  # ไทยไม่มี DST offset คงที่ตลอดปี
DELAY_OFFSET_HOURS = (3, 6)  # README ข้อ 6: ลองเลื่อนออก +3 แล้ว +6 ชม. เช็คเส้นหลักอย่างเดียว


class Point(BaseModel):
    lat: float
    lng: float
    eta: datetime


class Route(BaseModel):
    route_id: str
    duration_min: float
    points: list[Point]


class EvaluateIn(BaseModel):
    routes: list[Route]


def rain_level(mm_per_h: float) -> str:
    if mm_per_h < RAIN_MEDIUM:
        return "LOW"
    return "MEDIUM" if mm_per_h <= RAIN_HIGH_ABOVE else "HIGH"


def wind_level(kmh: float) -> str:
    if kmh < WIND_MEDIUM:
        return "LOW"
    return "MEDIUM" if kmh <= WIND_HIGH_ABOVE else "HIGH"


def worst(levels: list[Optional[str]]) -> Optional[str]:
    """ระดับที่แย่ที่สุด ข้าม None ถ้าไม่มีข้อมูลเลยคืน None (ห้ามเดาเป็น LOW)"""
    known = [lv for lv in levels if lv is not None]
    return max(known, key=lambda lv: _ORDER[lv]) if known else None


def score_in_band(level: str, severity: float) -> int:
    """severity 0..1 = ความรุนแรงภายในระดับนั้น level มาจากเกณฑ์เสมอ score แค่ตามมา"""
    low, high = SCORE_RANGE[level]
    return round(low + (high - low) * max(0.0, min(1.0, severity)))


def nearby_hazards(point: dict, hazards: list[dict], radius_km: float = HAZARD_RADIUS_KM) -> list[dict]:
    """หมุดภัยที่อยู่ในรัศมี radius_km จากจุดนี้ (README ข้อ 8)"""
    return [h for h in hazards if haversine_km(point, h) <= radius_km]


def point_level(forecast: Optional[dict], hazards: list[dict]) -> Optional[str]:
    if forecast is None:
        return None
    hazard_level = worst([h["severity"] for h in hazards])
    return worst([rain_level(forecast["rain_mm_per_h"]), wind_level(forecast["wind_kmh"]), hazard_level])


def _severity_in_band(value: float, medium: float, high_above: float) -> float:
    """เศษส่วน 0..1 ว่าค่าจริงลึกแค่ไหนในช่วงของระดับตัวเอง ใกล้ขอบบนของช่วง = ใกล้ 1
    ช่วง HIGH ไม่มีขอบบนตายตัวใน CONTRACT เลยใช้ความกว้างของช่วง MEDIUM เป็นสเกลอ้างอิง แล้วอิ่มตัวที่ 1"""
    span = high_above - medium
    if value <= medium:
        return max(0.0, min(1.0, value / medium)) if medium else 0.0
    if value <= high_above:
        return (value - medium) / span
    return min(1.0, (value - high_above) / span)


def rain_severity(mm_per_h: float) -> float:
    return _severity_in_band(mm_per_h, RAIN_MEDIUM, RAIN_HIGH_ABOVE)


def wind_severity(kmh: float) -> float:
    return _severity_in_band(kmh, WIND_MEDIUM, WIND_HIGH_ABOVE)


def hazard_severity(point: dict, hazards: list[dict], radius_km: float = HAZARD_RADIUS_KM) -> float:
    """หมุดภัยที่รุนแรงที่สุดยิ่งอยู่ใกล้จุดเท่าไรยิ่งรุนแรง (ชิดจุด = 1, ชิดขอบรัศมี = 0)"""
    worst_sev = worst([h["severity"] for h in hazards])
    if worst_sev is None:
        return 0.0
    nearest = min(haversine_km(point, h) for h in hazards if h["severity"] == worst_sev)
    return max(0.0, min(1.0, 1 - nearest / radius_km))


def point_severity(forecast: dict, hazards: list[dict], point: dict, level: str) -> float:
    """severity 0..1 จากปัจจัยที่ทำให้ได้ level นี้ (ปัจจัยที่แย่ที่สุด ถ้าเสมอกันหลายตัวเอาค่าสูงสุด)"""
    candidates = []
    if rain_level(forecast["rain_mm_per_h"]) == level:
        candidates.append(rain_severity(forecast["rain_mm_per_h"]))
    if wind_level(forecast["wind_kmh"]) == level:
        candidates.append(wind_severity(forecast["wind_kmh"]))
    if worst([h["severity"] for h in hazards]) == level:
        candidates.append(hazard_severity(point, hazards))
    return max(candidates) if candidates else 0.0


def delayed_route_level(forecasts: list[Optional[dict]], point_hazards_list: list[list[dict]]) -> Optional[str]:
    """ระดับเส้นหลักถ้าเลื่อนเวลาออกไป ต่างจาก worst() ตรงที่ไม่ข้าม None: ถ้าจุดไหนไม่มีพยากรณ์
    ณ เวลาที่เลื่อนไป ถือว่าช่วงเวลานั้นใช้ตัดสิน DELAY ไม่ได้เลย (คืน None) เพราะ worst() เดิมข้าม
    จุดที่ไม่มีข้อมูลไปคิดจากจุดที่เหลือ ถ้าจุดที่ไม่มีข้อมูลพอดีเป็นจุดที่เสี่ยงที่สุด เส้นจะดูปลอดภัย
    ทั้งที่จริงคือ "ไม่รู้" ซึ่งผิดหลัก CONTRACT ที่ห้ามนับไม่มีข้อมูลเป็นปลอดภัย"""
    levels = []
    for forecast, hazards in zip(forecasts, point_hazards_list):
        level = point_level(forecast, hazards)
        if level is None:
            return None
        levels.append(level)
    return worst(levels)


def best_delay_hours(main_level: str, delay_levels: dict[int, Optional[str]]) -> Optional[int]:
    """จำนวนชั่วโมงที่เลื่อนแล้วน้อยที่สุด (3 ก่อน 6) ที่ทำให้ระดับเส้นหลักดีขึ้นกว่า main_level ถ้าไม่มีคืน None"""
    for hours in sorted(delay_levels):
        level = delay_levels[hours]
        if level is not None and _ORDER[level] < _ORDER[main_level]:
            return hours
    return None


def decide(results: list[dict], delay_levels: Optional[dict[int, Optional[str]]] = None) -> tuple[str, str]:
    """ตารางคำแนะนำ CONTRACT หัวข้อ 4 results[0] คือเส้นหลัก คืน (recommended_route_id, recommendation)
    delay_levels: {3: ระดับเส้นหลักถ้าเลื่อนออก 3 ชม., 6: ...} ไม่ใส่ = ไม่เช็ค DELAY (7.4 เสริม)"""
    main = results[0]
    candidates = [r for r in results
                  if r["risk_level"] is not None and r["duration_min"] <= main["duration_min"] * MAX_SLOWER_RATIO]
    if main["risk_level"] is None or not candidates:
        return main["route_id"], "NORMAL"
    best = min(candidates, key=lambda r: (_ORDER[r["risk_level"]], r["duration_min"]))
    if main["risk_level"] == "LOW":
        return main["route_id"], "NORMAL"
    if _ORDER[best["risk_level"]] < _ORDER[main["risk_level"]]:
        return best["route_id"], "REROUTE"
    if delay_levels and best_delay_hours(main["risk_level"], delay_levels) is not None:
        return main["route_id"], "DELAY"
    if main["risk_level"] == "HIGH":
        return main["route_id"], "AVOID"
    return main["route_id"], "NORMAL"


def _worst_point_and_distance(route: dict) -> tuple[Optional[dict], float]:
    """จุดที่เสี่ยงที่สุดบนเส้นทาง (ถ้าเสมอกันเอาจุดแรก) พร้อมระยะสะสมจากจุดเริ่มต้นถึงจุดนั้น (กม.)
    ไม่มีชื่อจุดพักให้ใช้ในระบบนี้ เลยรายงานเป็นระยะทางแทน (README ข้อ 9 บอก 'ถ้าเป็นไปได้')"""
    points = route["points"]
    known = [(i, p) for i, p in enumerate(points) if p["risk_level"] is not None]
    if not known:
        return None, 0.0
    idx, point = max(known, key=lambda ip: _ORDER[ip[1]["risk_level"]])
    distance = sum(haversine_km(points[j], points[j + 1]) for j in range(idx))
    return point, distance


def _thai_time_th(iso_z: str) -> str:
    """เวลาไทย (UTC+7) จาก ISO UTC string เช่น '2026-09-24T03:00:00Z' -> '10:00 น.'"""
    dt = datetime.strptime(iso_z, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    local = dt.astimezone(THAI_TZ)
    return f"{local.hour}:{local.minute:02d} น."


def _risk_cause_th(point: dict) -> str:
    """สาเหตุหลักที่ทำให้จุดนี้ได้ level นี้ เป็นภาษาไทยสั้นๆ (ปัจจัยเดียวกับที่ point_severity ใช้)"""
    level, forecast, hazards = point["risk_level"], point["forecast"], point["hazards"]
    heavy = level == "HIGH"
    causes = []
    if forecast and rain_level(forecast["rain_mm_per_h"]) == level:
        causes.append("ฝนตกหนัก" if heavy else "ฝนตก")
    if forecast and wind_level(forecast["wind_kmh"]) == level:
        causes.append("ลมแรงจัด" if heavy else "ลมแรง")
    if worst([h["severity"] for h in hazards]) == level:
        causes.append("มีหมุดภัยรุนแรง" if heavy else "มีหมุดภัยเฝ้าระวัง")
    return "และ".join(causes) if causes else "สภาพอากาศแปรปรวน"


def summary_text(main: dict, recommended: dict, recommendation: str, delay_hours: Optional[int] = None) -> str:
    """สรุปเป็นภาษาไทยว่าเสี่ยงเพราะอะไร ตรงไหน กี่โมง และควรทำอะไร (README ข้อ 9 ต้องไม่ว่างเปล่า)
    delay_hours: จำนวนชั่วโมงที่แนะนำให้เลื่อน ใช้เมื่อ recommendation == "DELAY" เท่านั้น"""
    level = main["risk_level"]
    if level is None:
        return "ตอนนี้ประเมินความเสี่ยงไม่ได้ ข้อมูลสภาพอากาศไม่พร้อม"
    if level == "LOW":
        return "สภาพอากาศตลอดเส้นทางปกติ เดินทางได้ตามปกติ"

    point, distance_km = _worst_point_and_distance(main)
    where = f"ช่วงประมาณ {round(distance_km)} กม. จากจุดเริ่มต้น" if point else "บางช่วงของเส้นทาง"
    when = f" เวลาประมาณ {_thai_time_th(point['eta'])}" if point else ""
    cause = _risk_cause_th(point) if point else "สภาพอากาศแปรปรวน"

    if recommendation == "REROUTE":
        slower = round(recommended["duration_min"] - main["duration_min"])
        action = f"แนะนำเส้นทางสำรอง ช้ากว่าเดิม {slower} นาที" if slower > 0 else "แนะนำเส้นทางสำรอง ไม่ช้ากว่าเดิม"
    elif recommendation == "DELAY":
        action = f"แนะนำเลื่อนเวลาออกเดินทาง {delay_hours} ชม. ความเสี่ยงจะลดลง" if delay_hours \
            else "แนะนำเลื่อนเวลาออกเดินทาง ความเสี่ยงจะลดลง"
    elif recommendation == "AVOID":
        action = "ควรเลี่ยงการเดินทางช่วงนี้"
    else:
        action = "ขับช้าลงและเปิดไฟหน้า"

    return f"{cause} {where}{when} {action}"


def fetch_forecasts(points: list[dict]) -> tuple[list[Optional[dict]], list[str]]:
    """พยากรณ์ของทุกจุดเรียงตามลำดับที่ส่งไป จุดที่ไม่มีข้อมูลเป็น None
    ไม่ส่งต่อ WEATHER_UNAVAILABLE จาก weather-disaster ตรงๆ (คำขอนี้อาจมีจุดเลื่อนเวลาของ DELAY
    ปนอยู่ ไม่รู้ว่า warning มาจากจุดไหน) ผู้เรียกเช็คจุดจริงของตัวเองแล้วใส่ warning เองอยู่แล้ว"""
    try:
        data = call("WEATHER_DISASTER_URL", "POST", "/api/v1/forecast/points", timeout=WEATHER_TIMEOUT,
                    json={"points": [{"lat": p["lat"], "lng": p["lng"], "time": p["eta"]} for p in points]})
    except ApiError:
        return [None] * len(points), ["WEATHER_UNAVAILABLE"]
    forecasts = [p.get("forecast") for p in data["points"]]
    if len(forecasts) != len(points):
        return [None] * len(points), ["WEATHER_UNAVAILABLE"]
    return forecasts, [w for w in data.get("warnings", []) if w != "WEATHER_UNAVAILABLE"]


def fetch_hazards(points: list[dict]) -> tuple[list[dict], list[str]]:
    """ขอหมุดภัยครั้งเดียวต่อคำขอ กรอบพิกัดครอบทุกจุด (เผื่อ padding กันหมุดใกล้ขอบหลุด)
    ขอไม่ได้: ไปต่อด้วยฝน/ลมอย่างเดียว พร้อม warning HAZARD_FEED_UNAVAILABLE (README ข้อ 8)
    """
    lats = [p["lat"] for p in points]
    lngs = [p["lng"] for p in points]
    params = {
        "min_lat": min(lats) - _BBOX_PAD_DEG,
        "min_lng": min(lngs) - _BBOX_PAD_DEG,
        "max_lat": max(lats) + _BBOX_PAD_DEG,
        "max_lng": max(lngs) + _BBOX_PAD_DEG,
    }
    try:
        data = call("WEATHER_DISASTER_URL", "GET", "/api/v1/hazards", timeout=WEATHER_TIMEOUT, params=params)
    except ApiError:
        return [], ["HAZARD_FEED_UNAVAILABLE"]
    return data.get("hazards", []), []


@app.post("/api/v1/risk/evaluate")
def evaluate(body: EvaluateIn):
    if not body.routes or any(not r.points for r in body.routes):
        raise ApiError("VALIDATION_ERROR", "ต้องมีอย่างน้อย 1 เส้นทาง และทุกเส้นต้องมีจุด")
    if any(p.eta.tzinfo is None for r in body.routes for p in r.points):
        raise ApiError("VALIDATION_ERROR", "eta ต้องมี timezone")

    flat = [{"lat": p.lat, "lng": p.lng, "eta": to_iso(p.eta)} for r in body.routes for p in r.points]
    main_points = body.routes[0].points
    # DELAY (7.4): จุดเลื่อนเวลาของเส้นหลักอย่างเดียว ตำแหน่งเดิม แค่ eta ขยับ รวมเข้าคำขอ forecast
    # เดียวกับชุดแรกตาม README ข้อ 6 กันไม่ให้เกิน timeout จากการยิงหลายรอบ
    delayed_flat = {hours: [{"lat": p.lat, "lng": p.lng, "eta": to_iso(p.eta + timedelta(hours=hours))}
                             for p in main_points] for hours in DELAY_OFFSET_HOURS}
    combined = flat + [pt for hours in DELAY_OFFSET_HOURS for pt in delayed_flat[hours]]

    all_forecasts, warnings = fetch_forecasts(combined)
    hazards, hazard_warnings = fetch_hazards(flat)  # ตำแหน่งเดิม เวลาเลื่อนไม่กระทบกรอบพิกัด
    warnings = warnings + hazard_warnings

    forecasts = all_forecasts[:len(flat)]
    n_main = len(main_points)
    offset_forecasts, idx = {}, len(flat)
    for hours in DELAY_OFFSET_HOURS:
        offset_forecasts[hours] = all_forecasts[idx: idx + n_main]
        idx += n_main

    results, i, main_point_hazards = [], 0, []
    for route_idx, route in enumerate(body.routes):
        points = []
        for _ in route.points:
            point_hazards = nearby_hazards(flat[i], hazards)
            level = point_level(forecasts[i], point_hazards)
            severity = point_severity(forecasts[i], point_hazards, flat[i], level) if level else None
            points.append({**flat[i], "forecast": forecasts[i], "hazards": point_hazards, "risk_level": level,
                           "risk_score": score_in_band(level, severity) if level else None})
            if route_idx == 0:
                main_point_hazards.append(point_hazards)  # หมุดภัยไม่ผูกเวลา ใช้ซ้ำกับ DELAY ได้
            i += 1
        if any(p["risk_level"] is None for p in points):
            warnings.append("WEATHER_UNAVAILABLE")
        scores = [p["risk_score"] for p in points if p["risk_score"] is not None]
        results.append({"route_id": route.route_id, "duration_min": route.duration_min,
                        "risk_level": worst([p["risk_level"] for p in points]),
                        "risk_score": max(scores) if scores else None, "points": points})

    delay_levels = {hours: delayed_route_level(offset_forecasts[hours], main_point_hazards)
                     for hours in DELAY_OFFSET_HOURS}

    recommended_id, recommendation = decide(results, delay_levels)
    recommended = next(r for r in results if r["route_id"] == recommended_id)
    delay_hours = best_delay_hours(results[0]["risk_level"], delay_levels) if recommendation == "DELAY" else None
    summary = summary_text(results[0], recommended, recommendation, delay_hours)
    for r in results:
        r.pop("duration_min")
    return ok({
        "routes": results,
        "recommended_route_id": recommended_id,
        "recommendation": recommendation,
        "summary_th": summary,
        "warnings": sorted(set(warnings)),
    })
