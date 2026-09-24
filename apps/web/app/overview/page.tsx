"use client";

import Link from "next/link";
import AreaWeather from "@/shared/AreaWeather";
import EmergencyCard from "@/shared/EmergencyCard";
import Map from "@/shared/Map";
import RiskBadge from "@/shared/RiskBadge";
import StatusBox from "@/shared/StatusBox";
import Warnings from "@/shared/Warnings";
import { riskColor } from "@/shared/risk";
import { formatDuration, formatThaiTime } from "@/shared/time";
import { useApi } from "@/shared/useApi";
import type { HazardType, RiskLevel, Trip, TripPlan } from "@/shared/types";

export default function OverviewPage() {
  const { data: trip, error, loading, reload } = useApi<Trip | null>("/trips/upcoming");

  return (
    <>
      <div className="row" style={{ marginBottom: 16 }}>
        <Link className="btn" href="/my-trip">วางแผนทริป</Link>
        <Link className="btn btn-outline" href="/safety-map">ดูจุดเสี่ยงภัย</Link>
        <Link className="btn btn-outline" href="/assistant">ถามผู้ช่วย</Link>
      </div>
      {loading || error ? (
        <StatusBox loading={loading} error={error} onRetry={reload} />
      ) : trip ? (
        <UpcomingTrip trip={trip} />
      ) : (
        <AreaWeather />
      )}
    </>
  );
}

// ภัยหลักของแผนที่เป็น HIGH ดูจากพยากรณ์ของจุดที่แย่ที่สุด ใช้เลือกคำแนะนำฉุกเฉิน
function mainHazard(plan: TripPlan): HazardType | null {
  if (plan.risk_level !== "HIGH") return null;
  const f = plan.waypoints.map((w) => w.forecast).filter((x) => x !== null);
  if (f.some((x) => x.rain_mm_per_h > 35)) return "HEAVY_RAIN";
  if (f.some((x) => x.wind_kmh > 61)) return "STRONG_WIND";
  return null;
}

function UpcomingTrip({ trip }: { trip: Trip }) {
  const plan = trip.plan;
  const best = plan?.route_options.find((r) => r.is_recommended);
  const stops: { waypoint_id: string; lat: number; lng: number; name: string; risk_level?: RiskLevel | null }[] = plan
    ? plan.waypoints
    : [trip.origin, ...trip.waypoints, trip.destination].map((p, i) => ({ ...p, name: p.name ?? "", waypoint_id: String(i) }));

  return (
    <div className="grid">
      <div className="card">
        <h3>ทริปถัดไป: Trip {String(trip.trip_no).padStart(2, "0")}</h3>
        {trip.plan_status === "STALE" && (
          <div className="warnings">
            ทริปถูกแก้หลังวางแผน ข้อมูลอาจไม่ตรง <Link href="/my-trip">วางแผนใหม่</Link>
          </div>
        )}
        {plan && <Warnings warnings={plan.warnings} />}
        <Map
          routes={best ? [{ id: best.route_id, points: best.geometry, color: riskColor(best.risk_level), highlighted: true }] : []}
          markers={stops.map((s) => ({
            id: s.waypoint_id,
            lat: s.lat,
            lng: s.lng,
            color: plan ? riskColor(s.risk_level) : undefined,
            popup: s.name,
          }))}
          fitTo={best?.geometry ?? stops}
        />
      </div>
      <div className="card">
        <p>ออกเดินทาง {formatThaiTime(trip.departure_time)}</p>
        {plan ? (
          <>
            <p>
              ใช้เวลาประมาณ {formatDuration(plan.duration_min)} <RiskBadge level={plan.risk_level} score={plan.risk_score} />
            </p>
            <p>{plan.summary_th}</p>
            {mainHazard(plan) && <EmergencyCard hazardType={mainHazard(plan)!} />}
            <ol>
              {plan.waypoints.map((w) => (
                <li key={w.waypoint_id}>
                  {w.name} · {formatThaiTime(w.eta)} · {w.forecast?.condition_th ?? "ไม่มีข้อมูลอากาศ"}
                </li>
              ))}
            </ol>
          </>
        ) : (
          <>
            <p className="muted">ทริปนี้ยังไม่ได้วางแผนเส้นทาง</p>
            <Link className="btn" href="/my-trip">ไปวางแผน</Link>
          </>
        )}
      </div>
    </div>
  );
}
