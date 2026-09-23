"use client";

// โมดูล 2 อ่าน app/my-trip/README.md ก่อน จุดที่ต้องเติมมี TODO(web-mytrip)
import { useState } from "react";
import AreaWeather from "@/shared/AreaWeather";
import Map from "@/shared/Map";
import RiskBadge from "@/shared/RiskBadge";
import StatusBox from "@/shared/StatusBox";
import Warnings from "@/shared/Warnings";
import { api, ApiError } from "@/shared/api";
import { riskColor } from "@/shared/risk";
import { formatDuration, formatThaiTime } from "@/shared/time";
import { useApi } from "@/shared/useApi";
import type { Trip, TripPlan } from "@/shared/types";
import TripForm from "./TripForm";

export default function MyTripPage() {
  const { data: trips, error, loading, reload } = useApi<Trip[]>("/trips");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [planning, setPlanning] = useState(false);
  const [planError, setPlanError] = useState("");

  if (loading || error || !trips) return <StatusBox loading={loading} error={error} onRetry={reload} />;

  const trip = trips.find((t) => t.trip_id === selectedId) ?? trips[0];

  async function plan() {
    if (!trip) return;
    setPlanning(true);
    setPlanError("");
    try {
      await api<TripPlan>(`/trips/${trip.trip_id}/plan`, { method: "POST" });
      // TODO(web-mytrip): เปิด popup สรุป (เวลาเดินทาง + risk_score + summary_th) หลังแพลนเสร็จ
      await reload();
    } catch (e) {
      setPlanError(e instanceof ApiError ? e.message : "วางแผนไม่สำเร็จ");
    } finally {
      setPlanning(false);
    }
  }

  return (
    <>
      <div className="row" style={{ marginBottom: 16 }}>
        {trips.map((t) => (
          <button
            key={t.trip_id}
            className={`btn ${t.trip_id === trip?.trip_id ? "" : "btn-outline"}`}
            onClick={() => setSelectedId(t.trip_id)}
          >
            Trip {String(t.trip_no).padStart(2, "0")}
          </button>
        ))}
        <button className="btn btn-outline" onClick={() => setCreating(true)}>
          + สร้างทริป
        </button>
      </div>

      {creating ? (
        <TripForm
          onCancel={() => setCreating(false)}
          onCreated={async (t) => {
            setCreating(false);
            await reload();
            setSelectedId(t.trip_id);
          }}
        />
      ) : !trip ? (
        <AreaWeather />
      ) : (
        <div className="grid">
          <div className="card">
            {trip.plan_status === "STALE" && (
              <div className="warnings">ทริปถูกแก้หลังวางแผน กด Plan ใหม่เพื่อดูความเสี่ยงล่าสุด</div>
            )}
            {trip.plan && <Warnings warnings={trip.plan.warnings} />}
            {/* TODO(web-mytrip): ให้กดเลือกเส้นอื่นได้ แล้วตัวเลขในการ์ดขวาเปลี่ยนตามเส้นที่เลือก (README ข้อ 4, 5) */}
            <Map
              routes={(trip.plan?.route_options ?? []).map((r) => ({
                id: r.route_id,
                points: r.geometry,
                color: riskColor(r.risk_level),
                highlighted: r.is_recommended,
              }))}
              markers={(trip.plan?.waypoints ?? []).map((w) => ({
                id: w.waypoint_id,
                lat: w.lat,
                lng: w.lng,
                color: riskColor(w.risk_level),
                popup: w.name,
              }))}
              fitTo={trip.plan ? trip.plan.waypoints : [trip.origin, trip.destination]}
            />
          </div>
          <div className="card">
            <p>ออกเดินทาง {formatThaiTime(trip.departure_time)}</p>
            <button className="btn" onClick={plan} disabled={planning}>
              {planning ? "กำลังคำนวณ..." : "Plan"}
            </button>
            {planError && <p className="error-text">{planError}</p>}
            {trip.plan && (
              <>
                <p>
                  {formatDuration(trip.plan.duration_min)}{" "}
                  <RiskBadge level={trip.plan.risk_level} score={trip.plan.risk_score} />
                </p>
                <p>{trip.plan.summary_th}</p>
                {/* TODO(web-mytrip): แท็บขวาแสดงทุก waypoint ORIGIN/STOP/DESTINATION พร้อมเวลาถึง อากาศ และ RiskBadge (README ข้อ 6) */}
              </>
            )}
            {/* TODO(web-mytrip): แก้ทริป (PATCH) และลบทริป (DELETE) */}
          </div>
        </div>
      )}
    </>
  );
}
