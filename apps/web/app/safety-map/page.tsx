"use client";

// โมดูล 3 อ่าน app/safety-map/README.md ก่อน จุดที่ต้องเติมมี TODO(web-safety-assistant)
import { useState } from "react";
import Map, { type Bounds } from "@/shared/Map";
import StatusBox from "@/shared/StatusBox";
import Warnings from "@/shared/Warnings";
import { riskColor } from "@/shared/risk";
import { formatThaiTime } from "@/shared/time";
import { useApi } from "@/shared/useApi";
import type { Hazard } from "@/shared/types";

export default function SafetyMapPage() {
  const [bounds, setBounds] = useState<Bounds | null>(null);
  // TODO(web-safety-assistant): debounce ประมาณ 400 ms ก่อนเปลี่ยน bounds (README ข้อ 1)
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
        onBoundsChange={setBounds}
        markers={(data?.hazards ?? []).map((h) => ({
          id: h.hazard_id,
          lat: h.lat,
          lng: h.lng,
          color: riskColor(h.severity),
          popup: (
            <div>
              <strong>{h.title_th}</strong>
              {/* TODO(web-safety-assistant): source DERIVED ต้องมีคำว่า "ประเมิน" ให้เห็นชัด (README ข้อ 4) */}
              <br />
              {h.province} · {h.hazard_type}
              <br />
              <span className="muted">
                อัปเดต {formatThaiTime(h.updated_at)} · {h.source}
              </span>
            </div>
          ),
        }))}
      />
      {/* TODO(web-safety-assistant): กดหมุด HIGH แล้วแสดง <EmergencyCard hazardType={h.hazard_type} /> */}
      {data && data.hazards.length === 0 && <p className="muted">ไม่มีจุดเสี่ยงในบริเวณนี้</p>}
    </div>
  );
}
