// แบ่งเส้นทางเป็นช่วงตามระดับความเสี่ยง ให้ระบายสีแต่ละช่วงต่างกันแบบ Google Maps
// ใช้เกณฑ์เดียวกับ risk-decision (docs/CONTRACT.md หัวข้อ 4):
// - อากาศ: พยากรณ์ของจุดบนเส้นทางที่ใกล้ที่สุด ณ เวลาที่ไปถึง (ฝน 10/35 มม./ชม., ลม 40/61 กม./ชม.)
// - หมุดภัยใกล้เส้นทาง: น้ำท่วม 10 กม. ภัยอื่น 20 กม. ข้ามหมุดอากาศชั่วโมงนี้ (OPEN_METEO) เหมือน risk-decision
// เป็นการประมาณฝั่งหน้าเว็บ ระบบจริงควรให้ risk-decision ส่งระดับรายช่วงออกมาเอง
import { RISK_COLOR, RISK_TH, type Forecast, type Hazard, type LatLng, type Waypoint } from "./data";

type Level = "LOW" | "MEDIUM" | "HIGH";
export type RiskSegment = { points: LatLng[]; level: Level; tip: string };

const RANK: Record<Level, number> = { LOW: 0, MEDIUM: 1, HIGH: 2 };
const RADIUS_KM: Record<string, number> = { FLOOD: 10 };
const DEFAULT_RADIUS_KM = 20;

function km(a: LatLng, b: LatLng) {
  const r = Math.PI / 180;
  const dLat = (b.lat - a.lat) * r;
  const dLng = (b.lng - a.lng) * r;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(dLng / 2) ** 2;
  return 12742 * Math.asin(Math.sqrt(h));
}

function weatherLevel(f: Forecast | null): Level {
  if (!f) return "LOW";
  const rain: Level = f.rain_mm_per_h > 35 ? "HIGH" : f.rain_mm_per_h >= 10 ? "MEDIUM" : "LOW";
  const wind: Level = f.wind_kmh > 61 ? "HIGH" : f.wind_kmh >= 40 ? "MEDIUM" : "LOW";
  return RANK[rain] >= RANK[wind] ? rain : wind;
}

export function riskSegments(geometry: LatLng[], waypoints: Waypoint[], hazards: Hazard[]): RiskSegment[] {
  if (geometry.length < 2) return [];
  // หมุดที่อยู่ในกรอบเส้นทาง (+ ~25 กม.) เท่านั้น ลดงานคำนวณ
  const lats = geometry.map((p) => p.lat);
  const lngs = geometry.map((p) => p.lng);
  const pad = 0.25;
  const box = { a: Math.min(...lats) - pad, b: Math.max(...lats) + pad, c: Math.min(...lngs) - pad, d: Math.max(...lngs) + pad };
  const near = hazards.filter((h) => h.source !== "OPEN_METEO" && h.lat >= box.a && h.lat <= box.b && h.lng >= box.c && h.lng <= box.d);

  const perPoint = geometry.map((p) => {
    let level: Level = "LOW";
    let tip = "";
    // อากาศตอนไปถึง จากจุดบนเส้นทางที่ใกล้ที่สุด
    const wp = waypoints.reduce<Waypoint | null>((best, w) => (!best || km(p, w) < km(p, best) ? w : best), null);
    const wx = weatherLevel(wp?.forecast ?? null);
    if (RANK[wx] > RANK[level] && wp?.forecast) {
      level = wx;
      tip = `${wp.forecast.condition_th} ฝน ${wp.forecast.rain_mm_per_h} มม./ชม. ลม ${wp.forecast.wind_kmh} กม./ชม.`;
    }
    // หมุดภัยใกล้ช่วงนี้ เอาตัวที่รุนแรงที่สุด
    for (const h of near) {
      const worse = RANK[h.severity] > RANK[level] || (!tip && RANK[h.severity] === RANK[level]);
      if (!worse || km(p, h) > (RADIUS_KM[h.hazard_type] ?? DEFAULT_RADIUS_KM)) continue;
      level = h.severity;
      tip = h.title_th;
    }
    return { level, tip: tip || "ช่วงนี้ปกติ" };
  });

  // รวมจุดติดกันที่ระดับเท่ากันเป็นช่วงเดียว ต่อปลายช่วงให้เส้นไม่ขาด
  const out: RiskSegment[] = [];
  for (let i = 0; i < geometry.length - 1; i++) {
    const { level, tip } = perPoint[i];
    const last = out[out.length - 1];
    if (last && last.level === level) {
      last.points.push(geometry[i + 1]);
      if (last.tip === "ช่วงนี้ปกติ" && tip !== "ช่วงนี้ปกติ") last.tip = tip;
    } else out.push({ points: [geometry[i], geometry[i + 1]], level, tip });
  }
  return out;
}

// สำหรับส่งเข้า MapView ตรงๆ
export function coloredSegments(geometry: LatLng[], waypoints: Waypoint[], hazards: Hazard[]) {
  return riskSegments(geometry, waypoints, hazards).map((s) => ({ points: s.points, color: RISK_COLOR[s.level], tip: `ความเสี่ยง${RISK_TH[s.level]} · ${s.tip}` }));
}

// ความเสี่ยงของสถานที่หนึ่งจุด (ใช้กับที่เที่ยวรอบตัว): อากาศช่องที่ใกล้ที่สุด + หมุดภัยในรัศมี ใช้เกณฑ์เดียวกับเส้นทาง
export function placeRisk(p: LatLng, cells: { lat: number; lng: number; forecast: Forecast }[], hazards: Hazard[]) {
  const cell = cells.reduce<(typeof cells)[number] | null>((best, c) => (!best || km(p, c) < km(p, best) ? c : best), null);
  let level: Level = weatherLevel(cell?.forecast ?? null);
  let tip = cell ? `${cell.forecast.condition_th} ฝน ${cell.forecast.rain_mm_per_h} มม./ชม.` : "";
  for (const h of hazards) {
    if (h.source === "OPEN_METEO" || RANK[h.severity] <= RANK[level]) continue;
    if (km(p, h) > (RADIUS_KM[h.hazard_type] ?? DEFAULT_RADIUS_KM)) continue;
    level = h.severity;
    tip = h.title_th;
  }
  return { level, tip, forecast: cell?.forecast ?? null };
}

export function distanceKm(a: LatLng, b: LatLng) {
  return km(a, b);
}
