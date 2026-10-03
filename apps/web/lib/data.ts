// ชนิดข้อมูลตาม docs/CONTRACT.md + ตัวช่วยแสดงผล ข้อมูลจริงอยู่ใน lib/store.tsx
import sample from "./sample.json";

export type LatLng = { lat: number; lng: number };
export type Risk = "LOW" | "MEDIUM" | "HIGH" | null;
export type Recommendation = "NORMAL" | "DELAY" | "REROUTE" | "AVOID";
export type HazardType = "RAIN" | "HEAVY_RAIN" | "STRONG_WIND" | "FLOOD" | "LANDSLIDE_RISK" | "STORM" | "EARTHQUAKE";

export type Forecast = { time: string; rain_mm_per_h: number; wind_kmh: number; temp_c: number; condition_th: string };
export type Waypoint = {
  waypoint_id: string;
  kind: "ORIGIN" | "STOP" | "DESTINATION";
  name: string;
  lat: number;
  lng: number;
  eta: string;
  forecast: Forecast | null;
  risk_level: Risk;
};
export type RouteOption = {
  route_id: string;
  duration_min: number;
  distance_km: number;
  risk_level: Risk;
  risk_score: number | null;
  is_recommended: boolean;
  geometry: LatLng[];
};
export type Plan = {
  departure_time: string;
  arrival_time: string;
  duration_min: number;
  risk_level: Risk;
  risk_score: number | null;
  recommendation: Recommendation;
  summary_th: string;
  route_options: RouteOption[];
  waypoints: Waypoint[];
  warnings: string[];
};
export type Trip = {
  trip_id: string;
  trip_no: number;
  title: string;
  origin: string;
  destination: string;
  stops: string[];
  departure_time: string;
  plan_status: "NONE" | "FRESH" | "STALE";
  plan: Plan | null;
  departures: { offset_h: number; risk_level: Risk; risk_score: number | null; recommendation: Recommendation }[];
};
export type Hazard = {
  hazard_id: string;
  hazard_type: HazardType;
  severity: "LOW" | "MEDIUM" | "HIGH";
  lat: number;
  lng: number;
  province: string | null;
  title_th: string;
  source: string;
  updated_at: string;
};
export type Emergency = { hazard_type: HazardType; steps_th: string[]; contacts: { name_th: string; phone: string }[] };
export type NearbyPlace = { name: string; detail: string | null; lat: number; lng: number; kind_th: string };
export type AreaCell = { lat: number; lng: number; forecast: Forecast };

// วิธีรับมือตัวอย่างจากระบบจริง ใช้แสดงไปก่อนระหว่างรอ GET /safety/emergency (lib/store.tsx)
const s = sample as unknown as { emergency: Record<HazardType, Emergency> };
export const EMERGENCY = s.emergency;

// ---------- ตัวช่วยแสดงผล ----------

export const RISK_COLOR: Record<string, string> = { LOW: "#22a06b", MEDIUM: "#f0a020", HIGH: "#e5484d", NONE: "#8a97a8" };
export const RISK_TH: Record<string, string> = { LOW: "ต่ำ", MEDIUM: "ปานกลาง", HIGH: "สูง", NONE: "ไม่ทราบ" };
export const riskKey = (r: Risk | undefined) => r ?? "NONE";

export const RECO: Record<Recommendation, { title: string; tone: "ok" | "warn" | "danger" | "info" }> = {
  NORMAL: { title: "เดินทางได้ตามปกติ", tone: "ok" },
  REROUTE: { title: "แนะนำใช้เส้นทางอื่น", tone: "warn" },
  DELAY: { title: "แนะนำเลื่อนเวลาออกเดินทาง", tone: "warn" },
  AVOID: { title: "ไม่แนะนำให้เดินทางช่วงนี้", tone: "danger" },
};

export const HAZARD_META: Record<HazardType, { label: string; icon: string }> = {
  RAIN: { label: "ฝน", icon: "rain" },
  HEAVY_RAIN: { label: "ฝนหนัก", icon: "heavyrain" },
  STRONG_WIND: { label: "ลมแรง", icon: "wind" },
  FLOOD: { label: "น้ำท่วม", icon: "flood" },
  LANDSLIDE_RISK: { label: "ดินถล่ม", icon: "landslide" },
  STORM: { label: "พายุ", icon: "storm" },
  EARTHQUAKE: { label: "แผ่นดินไหว", icon: "quake" },
};

const TZ = "Asia/Bangkok";
export function thaiTime(iso: string) {
  return new Date(iso).toLocaleTimeString("th-TH", { timeZone: TZ, hour: "2-digit", minute: "2-digit" }) + " น.";
}
export function thaiDate(iso: string) {
  return new Date(iso).toLocaleDateString("th-TH", { timeZone: TZ, weekday: "short", day: "numeric", month: "short" });
}
export function thaiDateTime(iso: string) {
  return `${thaiDate(iso)} · ${thaiTime(iso)}`;
}
export function duration(min: number) {
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h ? `${h} ชม.${m ? ` ${m} นาที` : ""}` : `${m} นาที`;
}
export function addHours(iso: string, h: number) {
  return new Date(new Date(iso).getTime() + h * 3600_000).toISOString();
}
// ไอคอนอากาศจากตัวเลข ไม่ใช้คำบรรยาย
export function weatherIcon(f: Forecast | null) {
  if (!f) return "cloudoff";
  if (f.rain_mm_per_h > 35) return "heavyrain";
  if (f.rain_mm_per_h >= 1) return "rain";
  if (f.wind_kmh >= 40) return "wind";
  if (/เมฆ/.test(f.condition_th)) return "cloud";
  return "sun";
}
