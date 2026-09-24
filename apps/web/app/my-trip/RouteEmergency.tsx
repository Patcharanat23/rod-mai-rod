"use client";

import EmergencyCard from "@/shared/EmergencyCard";
import { useApi } from "@/shared/useApi";
import type { Hazard, HazardType, LatLng, TripPlan } from "@/shared/types";

const HAZARD_TYPES: HazardType[] = ["RAIN", "HEAVY_RAIN", "STRONG_WIND", "FLOOD", "LANDSLIDE_RISK", "STORM", "EARTHQUAKE"];
const NEAR_KM = 20; // รัศมีเดียวกับที่ risk-decision ใช้นับหมุดภัยใกล้จุด
const PAD_DEG = 0.2; // ขยายกรอบค้นหมุดภัยออกไปราว 20 กม.
const SEVERITY_RANK = { HIGH: 2, MEDIUM: 1, LOW: 0 } as const;

function distanceKm(a: LatLng, b: LatLng): number {
  const rad = (d: number) => (d * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat);
  const dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(h));
}

// ฝนหรือลมเกินเกณฑ์ HIGH ของ CONTRACT หัวข้อ 4 ดูจุดที่เป็น HIGH ก่อน แล้วค่อยดูจุดอื่น
function weatherCause(plan: TripPlan): HazardType | null {
  const ordered = [...plan.waypoints].sort((a, b) => Number(b.risk_level === "HIGH") - Number(a.risk_level === "HIGH"));
  for (const w of ordered) {
    if (!w.forecast) continue;
    if (w.forecast.rain_mm_per_h > 35) return "HEAVY_RAIN";
    if (w.forecast.wind_kmh > 61) return "STRONG_WIND";
  }
  return null;
}

// หมุดภัยที่อยู่ใกล้เส้นทางไม่เกิน 20 กม. เลือกตัวที่รุนแรงที่สุด
function nearestHazardType(hazards: Hazard[], route: LatLng[]): HazardType | null {
  const near = hazards
    .filter((h): h is Hazard & { hazard_type: HazardType } => HAZARD_TYPES.includes(h.hazard_type as HazardType))
    .map((h) => ({ h, km: Math.min(...route.map((p) => distanceKm(p, h))) }))
    .filter((x) => x.km <= NEAR_KM)
    .sort((a, b) => SEVERITY_RANK[b.h.severity] - SEVERITY_RANK[a.h.severity] || a.km - b.km);
  return near[0]?.h.hazard_type ?? null;
}

function boundsQuery(points: LatLng[]): string {
  const lats = points.map((p) => p.lat);
  const lngs = points.map((p) => p.lng);
  const f = (n: number) => n.toFixed(4);
  return (
    `min_lat=${f(Math.min(...lats) - PAD_DEG)}&min_lng=${f(Math.min(...lngs) - PAD_DEG)}` +
    `&max_lat=${f(Math.max(...lats) + PAD_DEG)}&max_lng=${f(Math.max(...lngs) + PAD_DEG)}`
  );
}

// แสดงคำแนะนำฉุกเฉินเมื่อเส้นทางที่แนะนำเป็น HIGH (README ข้อ 5 ของไฟล์งาน)
export default function RouteEmergency({ plan }: { plan: TripPlan }) {
  const high = plan.risk_level === "HIGH";
  const fromWeather = high ? weatherCause(plan) : null;
  const recommended = plan.route_options.find((r) => r.is_recommended) ?? plan.route_options[0];
  const route = recommended?.geometry.length ? recommended.geometry : plan.waypoints;

  // ค้นหมุดภัยเฉพาะตอนที่อากาศไม่ใช่สาเหตุ
  const { data, error, loading } = useApi<{ hazards: Hazard[] }>(
    high && !fromWeather ? `/hazards?${boundsQuery(route)}` : null,
  );

  if (!high) return null;
  if (fromWeather) return <EmergencyCard hazardType={fromWeather} />;
  if (loading) return null;
  // หาสาเหตุไม่เจอหรือดึงหมุดภัยไม่ได้ ใช้ HEAVY_RAIN ตามไฟล์งาน เพราะฝนเป็นสาเหตุที่พบบ่อยที่สุด
  const fromPins = !error && data ? nearestHazardType(data.hazards, route) : null;
  return <EmergencyCard hazardType={fromPins ?? "HEAVY_RAIN"} />;
}
