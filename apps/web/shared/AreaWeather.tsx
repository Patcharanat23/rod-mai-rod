"use client";

import { useEffect, useState } from "react";
import Map from "./Map";
import StatusBox from "./StatusBox";
import Warnings from "./Warnings";
import { formatThaiTime } from "./time";
import { useApi } from "./useApi";
import { BANGKOK, inThailand, useLocation } from "./useLocation";
import type { AreaWeather as Area, NearbyPlace } from "./types";

// แผนที่ + สภาพอากาศแบบ area รอบตำแหน่งผู้ใช้ ใช้ตอนผู้ใช้ยังไม่มีทริป (Overview และ My Trip)
const NEARBY_RETRY_MS = 15_000;

export default function AreaWeather() {
  const { pos: located, denied } = useLocation();
  // ระบบรองรับเฉพาะในไทย (CONTRACT OUT_OF_THAILAND) ผู้ใช้อยู่ต่างประเทศแสดงกรุงเทพแทน
  const abroad = located !== null && !inThailand(located);
  const pos = abroad ? BANGKOK : located;
  const { data, error, loading, reload } = useApi<Area>(pos ? `/weather/area?lat=${pos.lat}&lng=${pos.lng}` : null);
  // สถานที่เที่ยวใกล้ตัว ดึงไม่ได้ก็ไม่เป็นไร การ์ดอากาศยังต้องแสดงต่อ (CONTRACT หัวข้อ 6)
  const nearby = useApi<{ places: NearbyPlace[] }>(pos ? `/places/nearby?lat=${pos.lat}&lng=${pos.lng}` : null);
  const places = nearby.data?.places ?? [];
  // Overpass ฟรีช้าเป็นช่วงๆ ดึงไม่ทันลองใหม่อีกครั้งเดียว เผื่อ api-backend โหลดเสร็จเก็บ cache แล้ว
  const [retried, setRetried] = useState(false);
  const retryNearby = nearby.reload;
  useEffect(() => {
    if (!nearby.error || retried) return;
    const timer = setTimeout(() => {
      setRetried(true);
      retryNearby();
    }, NEARBY_RETRY_MS);
    return () => clearTimeout(timer);
  }, [nearby.error, retried, retryNearby]);

  return (
    <div className="card">
      <h3>สภาพอากาศบริเวณใกล้เคียง</h3>
      {denied && <p className="muted">ไม่ได้รับอนุญาตให้ใช้ตำแหน่ง แสดงกรุงเทพฯ แทน</p>}
      {abroad && <p className="muted">ตำแหน่งของคุณอยู่นอกประเทศไทย แสดงกรุงเทพฯ แทน</p>}
      {data && <Warnings warnings={data.warnings} />}
      {!pos || loading || error ? (
        <StatusBox loading={!pos || loading} error={error} onRetry={reload} />
      ) : (
        <>
          <Map
            center={pos}
            zoom={9}
            // cell ที่ไม่มีพยากรณ์ไม่ต้องวาด แถบ Warnings บอกผู้ใช้แล้ว
            markers={[
              ...places.map((pl, i) => ({
                id: `place-${i}`,
                lat: pl.lat,
                lng: pl.lng,
                label: String(i + 1), // เลขตรงกับรายการใต้แผนที่ หมุดที่อยู่ใกล้กันซ้อนกันได้
                color: "#f59e0b",
                popup: (
                  <div>
                    <strong>{pl.name}</strong>
                    <br />
                    {pl.kind_th}
                    {pl.detail ? ` · ${pl.detail}` : ""}
                  </div>
                ),
              })),
              ...(data?.cells ?? []).flatMap((c) => (c.forecast ? [{ ...c, forecast: c.forecast }] : [])).map((c, i) => ({
              id: String(i),
              lat: c.lat,
              lng: c.lng,
              color: c.forecast.rain_mm_per_h >= 10 ? "#2563eb" : "#93c5fd",
              popup: (
                <div>
                  <strong>{c.forecast.condition_th}</strong>
                  <br />
                  ฝน {c.forecast.rain_mm_per_h} มม./ชม. · ลม {c.forecast.wind_kmh} กม./ชม. · {c.forecast.temp_c}°C
                </div>
              ),
            })),
            ]}
          />
          <p className="muted">อัปเดต {formatThaiTime(data?.updated_at)}</p>
          {places.length > 0 && (
            <>
              <h4 style={{ margin: "12px 0 6px" }}>สถานที่เที่ยวใกล้คุณ</h4>
              <div className="row" style={{ gap: 6 }}>
                {places.map((pl, i) => (
                  <span key={i} className="btn btn-outline" style={{ padding: "4px 10px", fontSize: 13, cursor: "default" }}>
                    {i + 1}. {pl.name} <span className="muted">· {pl.kind_th}</span>
                  </span>
                ))}
              </div>
            </>
          )}
          {nearby.error && (
            <p className="muted">
              {retried ? "ยังดึงสถานที่เที่ยวใกล้ๆ ไม่ได้ตอนนี้" : "กำลังดึงสถานที่เที่ยวใกล้ๆ อีกครั้ง..."}
            </p>
          )}
        </>
      )}
    </div>
  );
}
