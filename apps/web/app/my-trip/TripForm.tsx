"use client";

import { useState } from "react";
import Map from "@/shared/Map";
import { api, ApiError } from "@/shared/api";
import { thaiInputToUtc } from "@/shared/time";
import type { Place, Trip, TripInput } from "@/shared/types";

type Props = { onCreated: (t: Trip) => void; onCancel: () => void };

// ตอนนี้: จิ้มแผนที่ครั้งแรก = ต้นทาง ครั้งที่สอง = ปลายทาง
// TODO(web-mytrip): ปุ่ม "ใช้ตำแหน่งปัจจุบัน" (README ข้อ 2), ตั้งชื่อจุด, หมุดระหว่างทางไม่เกิน 5 จุด (README ข้อ 8)
export default function TripForm({ onCreated, onCancel }: Props) {
  const [origin, setOrigin] = useState<Place | null>(null);
  const [destination, setDestination] = useState<Place | null>(null);
  const [waypoints] = useState<Place[]>([]);
  const [departure, setDeparture] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function pick(p: Place) {
    if (!origin) setOrigin({ ...p, name: "ต้นทาง" });
    else if (!destination) setDestination({ ...p, name: "ปลายทาง" });
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!origin || !destination || !departure) return setError("กรุณาเลือกต้นทาง ปลายทาง และเวลาออกเดินทาง");
    setBusy(true);
    setError("");
    try {
      const body: TripInput = { origin, destination, waypoints, departure_time: thaiInputToUtc(departure) };
      onCreated(await api<Trip>("/trips", { method: "POST", body }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "สร้างทริปไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  const points = [origin, destination].filter((p): p is Place => p !== null);
  return (
    <div className="grid">
      <div className="card">
        <p className="muted">
          {!origin ? "จิ้มแผนที่เพื่อเลือกต้นทาง" : !destination ? "จิ้มแผนที่เพื่อเลือกปลายทาง" : "เลือกครบแล้ว"}
        </p>
        <Map onMapClick={pick} markers={points.map((p, i) => ({ id: String(i), lat: p.lat, lng: p.lng, popup: p.name }))} />
      </div>
      <form className="card" onSubmit={submit}>
        <h3>สร้างทริป</h3>
        <label>
          เวลาออกเดินทาง (เวลาไทย)
          <input type="datetime-local" value={departure} onChange={(e) => setDeparture(e.target.value)} required />
        </label>
        {error && <p className="error-text">{error}</p>}
        <div className="row">
          <button className="btn" disabled={busy}>
            {busy ? "กำลังบันทึก..." : "บันทึก"}
          </button>
          <button
            type="button"
            className="btn btn-outline"
            onClick={() => {
              setOrigin(null);
              setDestination(null);
            }}
          >
            เลือกจุดใหม่
          </button>
          <button type="button" className="btn btn-outline" onClick={onCancel}>
            ยกเลิก
          </button>
        </div>
      </form>
    </div>
  );
}
