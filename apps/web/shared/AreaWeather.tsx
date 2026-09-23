"use client";

import Map from "./Map";
import StatusBox from "./StatusBox";
import Warnings from "./Warnings";
import { formatThaiTime } from "./time";
import { useApi } from "./useApi";
import { useLocation } from "./useLocation";
import type { AreaWeather as Area } from "./types";

// แผนที่ + สภาพอากาศแบบ area รอบตำแหน่งผู้ใช้ ใช้ตอนผู้ใช้ยังไม่มีทริป (Overview และ My Trip)
export default function AreaWeather() {
  const { pos, denied } = useLocation();
  const { data, error, loading, reload } = useApi<Area>(pos ? `/weather/area?lat=${pos.lat}&lng=${pos.lng}` : null);

  return (
    <div className="card">
      <h3>สภาพอากาศบริเวณใกล้เคียง</h3>
      {denied && <p className="muted">ไม่ได้รับอนุญาตให้ใช้ตำแหน่ง แสดงกรุงเทพฯ แทน</p>}
      {data && <Warnings warnings={data.warnings} />}
      {!pos || loading || error ? (
        <StatusBox loading={!pos || loading} error={error} onRetry={reload} />
      ) : (
        <>
          <Map
            center={pos}
            zoom={9}
            markers={(data?.cells ?? []).map((c, i) => ({
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
            }))}
          />
          <p className="muted">อัปเดต {formatThaiTime(data?.updated_at)}</p>
        </>
      )}
    </div>
  );
}
