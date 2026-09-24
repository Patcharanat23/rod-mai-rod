"use client";

import { useState } from "react";
import { api, ApiError } from "@/shared/api";
import { thaiInputToUtc, utcToThaiInput } from "@/shared/time";
import type { Trip } from "@/shared/types";

type Props = { trip: Trip; onUpdated: () => Promise<void> | void; onDeleted: () => Promise<void> | void };
type Mode = "idle" | "edit" | "confirm-delete";

const smallBtn = { padding: "6px 14px", fontSize: 13 };

// แก้เวลาออกเดินทาง (PATCH) และลบทริป (DELETE) README ข้อ 7
// หลัง PATCH แผนเดิมเป็น STALE หน้าหลักมีแถบบอกให้กด Plan ใหม่อยู่แล้ว
export default function TripActions({ trip, onUpdated, onDeleted }: Props) {
  const [mode, setMode] = useState<Mode>("idle");
  const [departure, setDeparture] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const tripLabel = `Trip ${String(trip.trip_no).padStart(2, "0")}`;

  function start(next: Mode) {
    setError("");
    if (next === "edit") setDeparture(utcToThaiInput(trip.departure_time));
    setMode(next);
  }

  async function run(action: () => Promise<unknown>, done: () => Promise<void> | void, fallback: string) {
    setBusy(true);
    setError("");
    try {
      await action();
      setMode("idle");
      await done();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : fallback);
    } finally {
      setBusy(false);
    }
  }

  function saveTime(e: React.FormEvent) {
    e.preventDefault();
    if (!departure) return setError("กรุณาเลือกเวลาออกเดินทาง");
    run(
      () => api<Trip>(`/trips/${trip.trip_id}`, { method: "PATCH", body: { departure_time: thaiInputToUtc(departure) } }),
      onUpdated,
      "แก้เวลาไม่สำเร็จ",
    );
  }

  function remove() {
    run(() => api(`/trips/${trip.trip_id}`, { method: "DELETE" }), onDeleted, "ลบทริปไม่สำเร็จ");
  }

  return (
    <div style={{ borderTop: "1px solid var(--line)", marginTop: 16, paddingTop: 16 }}>
      {mode === "idle" && (
        <div className="row">
          <button type="button" className="btn btn-outline" style={smallBtn} onClick={() => start("edit")}>
            แก้เวลาออกเดินทาง
          </button>
          <button type="button" className="btn btn-outline" style={smallBtn} onClick={() => start("confirm-delete")}>
            ลบทริป
          </button>
        </div>
      )}

      {mode === "edit" && (
        <form onSubmit={saveTime}>
          <label>
            เวลาออกเดินทางใหม่ (เวลาไทย)
            <input type="datetime-local" value={departure} onChange={(e) => setDeparture(e.target.value)} required />
          </label>
          <p className="muted">บันทึกแล้วแผนเดิมจะเก่า ต้องกด Plan ใหม่เพื่อดูความเสี่ยงของเวลาใหม่</p>
          <div className="row">
            <button className="btn" style={smallBtn} disabled={busy}>
              {busy ? "กำลังบันทึก..." : "บันทึกเวลา"}
            </button>
            <button type="button" className="btn btn-outline" style={smallBtn} disabled={busy} onClick={() => setMode("idle")}>
              ยกเลิก
            </button>
          </div>
        </form>
      )}

      {mode === "confirm-delete" && (
        <div role="alertdialog" aria-label={`ยืนยันลบ ${tripLabel}`}>
          <p>
            ลบ <strong>{tripLabel}</strong> ใช่ไหม ลบแล้วกู้คืนไม่ได้
          </p>
          <div className="row">
            <button
              type="button"
              className="btn"
              style={{ ...smallBtn, background: "#dc2626" }}
              disabled={busy}
              onClick={remove}
            >
              {busy ? "กำลังลบ..." : "ลบเลย"}
            </button>
            <button type="button" className="btn btn-outline" style={smallBtn} disabled={busy} onClick={() => setMode("idle")}>
              ยกเลิก
            </button>
          </div>
        </div>
      )}

      {error && <p className="error-text">{error}</p>}
    </div>
  );
}
