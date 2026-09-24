"use client";

// โมดูล 3 อ่าน app/safety-map/README.md ก่อน จุดที่ต้องเติมมี TODO(web-safety-assistant)
import { useEffect, useState } from "react";
import EmergencyCard from "@/shared/EmergencyCard";
import Map, { type Bounds } from "@/shared/Map";
import StatusBox from "@/shared/StatusBox";
import Warnings from "@/shared/Warnings";
import { riskColor } from "@/shared/risk";
import { formatThaiTime } from "@/shared/time";
import { useApi } from "@/shared/useApi";
import type { Hazard, HazardType } from "@/shared/types";

// รอให้ผู้ใช้หยุดเลื่อนแผนที่ก่อนค่อยขอหมุด (README ข้อ 1)
const BOUNDS_DEBOUNCE_MS = 400;

function HazardPopup({ h }: { h: Hazard }) {
  const derived = h.source === "DERIVED";
  return (
    <div style={{ maxWidth: 300, maxHeight: 360, overflowY: "auto" }}>
      <strong>{h.title_th}</strong>
      {/* ข้อมูลประเมินห้ามดูเหมือนประกาศทางการ (README ข้อ 4) */}
      {derived && <strong style={{ color: "#b45309" }}> (ประเมิน)</strong>}
      <br />
      {h.province} · {h.hazard_type}
      <br />
      <span className="muted">
        อัปเดต {formatThaiTime(h.updated_at)} · {derived ? "ประเมินโดยระบบ ไม่ใช่ประกาศทางการ" : h.source}
      </span>
      {h.severity === "HIGH" && (
        <div style={{ marginTop: 8 }}>
          <EmergencyCard hazardType={h.hazard_type as HazardType} />
        </div>
      )}
    </div>
  );
}

export default function SafetyMapPage() {
  const [rawBounds, setRawBounds] = useState<Bounds | null>(null);
  const [bounds, setBounds] = useState<Bounds | null>(null);

  useEffect(() => {
    if (!rawBounds) return;
    // ครั้งแรกโหลดทันที ไม่ต้องรอ
    if (!bounds) {
      setBounds(rawBounds);
      return;
    }
    const t = setTimeout(() => setBounds(rawBounds), BOUNDS_DEBOUNCE_MS);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rawBounds]);

  const query = bounds
    ? new URLSearchParams(Object.entries(bounds).map(([k, v]) => [k, v.toFixed(3)])).toString()
    : null;
  const { data, error, loading, reload } = useApi<{ hazards: Hazard[]; warnings: string[] }>(
    query ? `/hazards?${query}` : null,
  );

  return (
    <div className="card">
      <h3>แผนที่จุดเสี่ยงภัย</h3>
      {data && <Warnings warnings={data.warnings} />}
      {error && <StatusBox error={error} onRetry={reload} />}
      {loading && <p className="muted">กำลังโหลดหมุด...</p>}
      {/* TODO(web-safety-assistant): ไอคอนตาม hazard_type + ไอคอนสำรอง (README ข้อ 3), marker cluster (ข้อ 2) */}
      <Map
        onBoundsChange={setRawBounds}
        markers={(data?.hazards ?? []).map((h) => ({
          id: h.hazard_id,
          lat: h.lat,
          lng: h.lng,
          color: riskColor(h.severity),
          popup: <HazardPopup h={h} />,
        }))}
      />
      {data && data.hazards.length === 0 && <p className="muted">ไม่มีจุดเสี่ยงในบริเวณนี้</p>}
    </div>
  );
}
