"use client";

// โมดูล 3 อ่าน app/safety-map/README.md ก่อน จุดที่ต้องเติมมี TODO(web-safety-assistant)
import { useEffect, useState, type Dispatch, type SetStateAction } from "react";
import EmergencyCard from "@/shared/EmergencyCard";
import Map, { type Bounds } from "@/shared/Map";
import StatusBox from "@/shared/StatusBox";
import Warnings from "@/shared/Warnings";
import RiskBadge from "@/shared/RiskBadge";
import { RISK_LABEL, riskColor } from "@/shared/risk";
import { formatThaiTime } from "@/shared/time";
import { useApi } from "@/shared/useApi";
import type { Hazard, HazardType, RiskLevel } from "@/shared/types";

// รอให้ผู้ใช้หยุดเลื่อนแผนที่ก่อนค่อยขอหมุด (README ข้อ 1)
const BOUNDS_DEBOUNCE_MS = 400;

// สัญลักษณ์ตัวอักษรของแต่ละ hazard_type ใน CONTRACT (README ข้อ 3)
const HAZARD_META: Record<HazardType, { symbol: string; label: string }> = {
  RAIN: { symbol: "ฝน", label: "ฝน" },
  HEAVY_RAIN: { symbol: "ฝน+", label: "ฝนหนัก" },
  STRONG_WIND: { symbol: "ลม", label: "ลมแรง" },
  FLOOD: { symbol: "น้ำ", label: "น้ำท่วม" },
  LANDSLIDE_RISK: { symbol: "ดิน", label: "เสี่ยงดินถล่ม" },
  STORM: { symbol: "พายุ", label: "พายุ" },
  EARTHQUAKE: { symbol: "ไหว", label: "แผ่นดินไหว" },
};
// ชนิดที่ไม่รู้จักห้ามพัง ใช้สัญลักษณ์สำรอง
const UNKNOWN_HAZARD = { symbol: "?", label: "ภัยอื่นๆ" };
const SEVERITIES: RiskLevel[] = ["HIGH", "MEDIUM", "LOW"];

function hazardMeta(type: string) {
  return HAZARD_META[type as HazardType] ?? UNKNOWN_HAZARD;
}

// กลุ่มของตัวกรอง ชนิดที่ไม่รู้จักรวมเป็น "อื่นๆ"
const OTHER = "OTHER";
const FILTER_GROUPS = [...Object.keys(HAZARD_META), OTHER];

const FILTER_BTN = { display: "inline-flex", alignItems: "center", gap: 6, padding: "4px 10px", fontSize: 13 };

function filterGroup(type: string) {
  return type in HAZARD_META ? type : OTHER;
}

function HazardFilter({
  hazards,
  selected,
  onChange,
}: {
  hazards: Hazard[];
  selected: Set<string>;
  onChange: Dispatch<SetStateAction<Set<string>>>;
}) {
  const counts: Record<string, number> = {};
  for (const h of hazards) {
    const g = filterGroup(h.hazard_type);
    counts[g] = (counts[g] ?? 0) + 1;
  }
  function toggle(g: string) {
    onChange((prev) => {
      const next = new Set(prev);
      if (next.has(g)) next.delete(g);
      else next.add(g);
      return next;
    });
  }
  const all = selected.size === 0;
  return (
    <div className="row" role="group" aria-label="กรองหมุดตามชนิดภัย" style={{ gap: 6, marginBottom: 12 }}>
      <button
        type="button"
        className={`btn ${all ? "" : "btn-outline"}`}
        style={FILTER_BTN}
        aria-pressed={all}
        onClick={() => onChange(new Set())}
      >
        ทั้งหมด ({hazards.length})
      </button>
      {FILTER_GROUPS.map((g) => {
        const on = selected.has(g);
        return (
          <button
            key={g}
            type="button"
            className={`btn ${on ? "" : "btn-outline"}`}
            style={FILTER_BTN}
            aria-pressed={on}
            onClick={() => toggle(g)}
          >
            <HazardSymbol type={g} color={on ? "#fff" : undefined} />
            {g === OTHER ? "อื่นๆ" : hazardMeta(g).label} ({counts[g] ?? 0})
          </button>
        );
      })}
    </div>
  );
}

function HazardSymbol({ type, color = "#374151" }: { type: string; color?: string }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        minWidth: 24,
        height: 24,
        padding: "0 4px",
        borderRadius: 12,
        border: `2px solid ${color}`,
        color,
        fontSize: 12,
        fontWeight: 700,
        lineHeight: 1,
      }}
    >
      {hazardMeta(type).symbol}
    </span>
  );
}

function Legend() {
  return (
    <details
      open
      style={{
        position: "absolute",
        top: 10,
        right: 10,
        zIndex: 1000,
        background: "#fff",
        border: "1px solid #e5e7eb",
        borderRadius: 8,
        padding: "6px 10px",
        fontSize: 13,
        maxWidth: 190,
      }}
    >
      <summary style={{ cursor: "pointer", fontWeight: 600 }}>คำอธิบายสัญลักษณ์</summary>
      <div style={{ display: "grid", gap: 4, marginTop: 6 }}>
        {SEVERITIES.map((lv) => (
          <div key={lv} className="row" style={{ gap: 6 }}>
            <span style={{ width: 12, height: 12, borderRadius: 6, background: riskColor(lv) }} />
            ความเสี่ยง{RISK_LABEL[lv]}
          </div>
        ))}
        {[...Object.keys(HAZARD_META), "UNKNOWN"].map((t) => (
          <div key={t} className="row" style={{ gap: 6 }}>
            <HazardSymbol type={t} />
            {hazardMeta(t).label}
          </div>
        ))}
      </div>
    </details>
  );
}

function HazardPopup({ h }: { h: Hazard }) {
  const derived = h.source === "DERIVED";
  return (
    <div style={{ maxWidth: 300, maxHeight: 360, overflowY: "auto" }}>
      <div className="row" style={{ gap: 6, flexWrap: "nowrap", alignItems: "flex-start" }}>
        <HazardSymbol type={h.hazard_type} color={riskColor(h.severity)} />
        <div>
          <strong>{h.title_th}</strong>
          {/* ข้อมูลประเมินห้ามดูเหมือนประกาศทางการ (README ข้อ 4) */}
          {/* weather-disaster อาจใส่คำว่าประเมินในชื่อมาแล้ว ไม่ต้องต่อซ้ำ */}
          {derived && !h.title_th.includes("ประเมิน") && <strong style={{ color: "#b45309" }}> (ประเมิน)</strong>}
        </div>
      </div>
      <div className="row" style={{ gap: 6, margin: "4px 0" }}>
        <RiskBadge level={h.severity} />
        <span>
          {hazardMeta(h.hazard_type).label}
          {/* GDACS / USGS ไม่มีชื่อจังหวัด */}
          {h.province && ` · ${h.province}`}
        </span>
      </div>
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
  // ว่าง = แสดงทุกชนิด เก็บแยกจากข้อมูล จึงค้างอยู่ตอนเลื่อน/ซูมแผนที่
  const [selected, setSelected] = useState<Set<string>>(new Set());

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
  const hazards = data?.hazards ?? [];
  const shown = selected.size === 0 ? hazards : hazards.filter((h) => selected.has(filterGroup(h.hazard_type)));

  return (
    <div className="card">
      <h3>แผนที่จุดเสี่ยงภัย</h3>
      {data && <Warnings warnings={data.warnings} />}
      {error && <StatusBox error={error} onRetry={reload} />}
      {loading && <p className="muted">กำลังโหลดหมุด...</p>}
      <HazardFilter hazards={hazards} selected={selected} onChange={setSelected} />
      {/* TODO(web-safety-assistant): marker cluster (README ข้อ 2) ต้องขอเพิ่ม package ก่อน */}
      <div style={{ position: "relative" }}>
        <Legend />
        <Map
          onBoundsChange={setRawBounds}
          markers={shown.map((h) => ({
            id: h.hazard_id,
            lat: h.lat,
            lng: h.lng,
            color: riskColor(h.severity),
            label: hazardMeta(h.hazard_type).symbol,
            popup: <HazardPopup h={h} />,
          }))}
        />
      </div>
      {data && hazards.length === 0 && <p className="muted">ไม่มีจุดเสี่ยงในบริเวณนี้</p>}
      {data && hazards.length > 0 && shown.length === 0 && (
        <p className="muted">ไม่มีหมุดชนิดที่เลือกในบริเวณนี้ กด "ทั้งหมด" เพื่อดูทุกชนิด</p>
      )}
    </div>
  );
}
