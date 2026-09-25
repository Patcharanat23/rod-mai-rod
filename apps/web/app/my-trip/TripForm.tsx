"use client";

import { useEffect, useState } from "react";
import Map from "@/shared/Map";
import { api, ApiError } from "@/shared/api";
import { thaiInputToUtc } from "@/shared/time";
import { useLocation } from "@/shared/useLocation";
import type { LatLng, Place, PlaceResult, Trip, TripInput } from "@/shared/types";
import PlaceSearch from "./PlaceSearch";

type Props = { onCreated: (t: Trip) => void; onCancel: () => void };
type Target = "origin" | "destination" | "stop";

const MAX_STOPS = 5;

// พิกัดต้องตรงตามนี้ DEMO_MODE ถึงจะหาไฟล์บันทึกเส้นทางเจอ
const PRESETS: Place[] = [
  { name: "กรุงเทพ", lat: 13.7563, lng: 100.5018 },
  { name: "นครสวรรค์", lat: 15.7047, lng: 100.1372 },
  { name: "เชียงใหม่", lat: 18.7883, lng: 98.9853 },
];

const TARGET_LABEL: Record<Target, string> = { origin: "ต้นทาง", destination: "ปลายทาง", stop: "จุดแวะ" };

const smallBtn = { padding: "4px 12px", fontSize: 13 };

export default function TripForm({ onCreated, onCancel }: Props) {
  const [origin, setOrigin] = useState<Place | null>(null);
  const [destination, setDestination] = useState<Place | null>(null);
  const [stops, setStops] = useState<Place[]>([]);
  const [target, setTarget] = useState<Target | null>("origin");
  const [departure, setDeparture] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [locating, setLocating] = useState(false);
  const [locateMsg, setLocateMsg] = useState("");

  // ใส่จุดลงช่องที่กำลังเลือกอยู่ แล้วเลื่อนไปช่องถัดไปที่ยังว่าง
  function place(p: Place) {
    if (target === "origin") {
      setOrigin(p);
      setTarget(destination ? null : "destination");
    } else if (target === "destination") {
      setDestination(p);
      setTarget(origin ? null : "origin");
    } else if (target === "stop" && stops.length < MAX_STOPS) {
      setStops((s) => [...s, p]);
      setTarget(null);
    }
  }

  function pickOnMap(p: LatLng) {
    if (!target) return;
    const name = target === "stop" ? `จุดแวะ ${stops.length + 1}` : TARGET_LABEL[target];
    place({ lat: p.lat, lng: p.lng, name });
  }

  // README ข้อ 2: ไม่ได้รับอนุญาตหรือเปิดผ่านที่อยู่ที่ไม่ใช่ https/localhost ต้องบอกและให้เลือกเอง
  function located(pos: LatLng, denied: boolean) {
    setLocating(false);
    if (denied) {
      setLocateMsg("ใช้ตำแหน่งปัจจุบันไม่ได้ (ไม่ได้รับอนุญาต หรือเบราว์เซอร์ไม่ให้ใช้ตำแหน่งบนหน้านี้) จิ้มแผนที่หรือกดสถานที่ตัวอย่างแทน");
      return;
    }
    setLocateMsg("");
    place({ lat: pos.lat, lng: pos.lng, name: "ตำแหน่งปัจจุบัน" });
  }

  function pickFromSearch(r: PlaceResult) {
    place({ lat: r.lat, lng: r.lng, name: r.name });
  }

  function rename(which: Target, name: string, index = 0) {
    if (which === "origin") setOrigin((o) => (o ? { ...o, name } : o));
    else if (which === "destination") setDestination((d) => (d ? { ...d, name } : d));
    else setStops((s) => s.map((p, i) => (i === index ? { ...p, name } : p)));
  }

  function reset() {
    setOrigin(null);
    setDestination(null);
    setStops([]);
    setTarget("origin");
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!origin || !destination || !departure) return setError("กรุณาเลือกต้นทาง ปลายทาง และเวลาออกเดินทาง");
    const all = [origin, ...stops, destination];
    if (all.some((p) => !p.name?.trim())) return setError("กรุณาตั้งชื่อให้ครบทุกจุด");
    const clean = (p: Place): Place => ({ ...p, name: p.name?.trim() });
    setBusy(true);
    setError("");
    try {
      const body: TripInput = {
        origin: clean(origin),
        destination: clean(destination),
        waypoints: stops.map(clean),
        departure_time: thaiInputToUtc(departure),
      };
      onCreated(await api<Trip>("/trips", { method: "POST", body }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "สร้างทริปไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  // ลำดับบนแผนที่ตรงกับลำดับที่ส่งไป: ต้นทาง > จุดแวะ 1..n > ปลายทาง
  const markers = [
    ...(origin ? [{ id: "origin", lat: origin.lat, lng: origin.lng, label: "ต้น", color: "#4388f3", popup: origin.name }] : []),
    ...stops.map((p, i) => ({ id: `stop-${i}`, lat: p.lat, lng: p.lng, label: `แวะ ${i + 1}`, color: "#7769f7", popup: p.name })),
    ...(destination
      ? [{ id: "destination", lat: destination.lat, lng: destination.lng, label: "ปลาย", color: "#16324b", popup: destination.name }]
      : []),
  ];

  return (
    <div className="grid">
      <div className="card">
        <p className="muted">
          {target ? `พิมพ์ชื่อ จิ้มแผนที่ หรือกดสถานที่ตัวอย่างเพื่อเลือก${TARGET_LABEL[target]}` : "กดปุ่มในฟอร์มเพื่อเลือกหรือเพิ่มจุด"}
        </p>
        <Map onMapClick={pickOnMap} markers={markers} fitTo={markers.length >= 2 ? markers : undefined} />
      </div>
      <form className="card" onSubmit={submit}>
        <h3>สร้างทริป</h3>

        <p className="muted" style={{ marginBottom: 6 }}>
          สถานที่ตัวอย่าง{target ? ` (ใส่เป็น${TARGET_LABEL[target]})` : ""}
        </p>
        <div className="row" style={{ marginBottom: 8 }}>
          {PRESETS.map((p) => (
            <button
              key={p.name}
              type="button"
              className="btn btn-outline"
              style={smallBtn}
              disabled={!target}
              onClick={() => place({ ...p })}
            >
              {p.name}
            </button>
          ))}
        </div>
        <div className="row" style={{ marginBottom: locateMsg ? 6 : 14 }}>
          <button
            type="button"
            className="btn btn-outline"
            style={smallBtn}
            disabled={!target || locating}
            onClick={() => {
              setLocateMsg("");
              setLocating(true);
            }}
          >
            {locating ? "กำลังหาตำแหน่ง..." : "ใช้ตำแหน่งปัจจุบัน"}
          </button>
        </div>
        {locateMsg && (
          <p className="error-text" style={{ marginTop: 0 }}>
            {locateMsg}
          </p>
        )}
        {locating && <Locator onDone={located} />}

        <PointField
          title="ต้นทาง"
          point={origin}
          active={target === "origin"}
          onPick={() => setTarget("origin")}
          onRename={(n) => rename("origin", n)}
          onSearch={pickFromSearch}
        />

        {stops.map((p, i) => (
          <PointField
            key={i}
            title={`จุดแวะ ${i + 1}`}
            point={p}
            onRename={(n) => rename("stop", n, i)}
            onRemove={() => setStops((s) => s.filter((_, j) => j !== i))}
          />
        ))}
        {target === "stop" && stops.length < MAX_STOPS && (
          <PointField
            title={`จุดแวะ ${stops.length + 1}`}
            point={null}
            active
            onRename={() => {}}
            onSearch={pickFromSearch}
          />
        )}
        {stops.length < MAX_STOPS ? (
          <button
            type="button"
            className="btn btn-outline"
            style={{ ...smallBtn, marginBottom: 14 }}
            onClick={() => setTarget(target === "stop" ? null : "stop")}
          >
            {target === "stop" ? "ยกเลิกการเพิ่มจุดแวะ" : `+ เพิ่มจุดแวะ (${stops.length}/${MAX_STOPS})`}
          </button>
        ) : (
          <p className="muted">ครบ {MAX_STOPS} จุดแวะแล้ว</p>
        )}

        <PointField
          title="ปลายทาง"
          point={destination}
          active={target === "destination"}
          onPick={() => setTarget("destination")}
          onRename={(n) => rename("destination", n)}
          onSearch={pickFromSearch}
        />

        <label>
          เวลาออกเดินทาง (เวลาไทย)
          <input type="datetime-local" value={departure} onChange={(e) => setDeparture(e.target.value)} required />
        </label>
        {error && <p className="error-text">{error}</p>}
        <div className="row">
          <button className="btn" disabled={busy}>
            {busy ? "กำลังบันทึก..." : "บันทึก"}
          </button>
          <button type="button" className="btn btn-outline" onClick={reset}>
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

// ขอตำแหน่งตอนกดปุ่มเท่านั้น (useLocation ขอทันทีที่ถูก mount) ได้ผลแล้วส่งกลับครั้งเดียว
function Locator({ onDone }: { onDone: (pos: LatLng, denied: boolean) => void }) {
  const { pos, denied } = useLocation();
  useEffect(() => {
    if (pos) onDone(pos, denied);
  }, [pos, denied]);
  return null;
}

type PointFieldProps = {
  title: string;
  point: Place | null;
  active?: boolean;
  onPick?: () => void;
  onRename: (name: string) => void;
  onRemove?: () => void;
  onSearch?: (p: PlaceResult) => void;
};

function PointField({ title, point, active, onPick, onRename, onRemove, onSearch }: PointFieldProps) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 4 }}>
        <strong style={{ fontSize: 14 }}>{title}</strong>
        <div className="row">
          {onPick && (
            <button type="button" className={`btn ${active ? "" : "btn-outline"}`} style={smallBtn} onClick={onPick}>
              {active ? "กำลังเลือก..." : point ? "เลือกใหม่" : "เลือก"}
            </button>
          )}
          {onRemove && (
            <button type="button" className="btn btn-outline" style={smallBtn} onClick={onRemove}>
              ลบ
            </button>
          )}
        </div>
      </div>
      {active && onSearch ? (
        <PlaceSearch label={title} onPick={onSearch} />
      ) : point ? (
        <input
          aria-label={`ชื่อ${title}`}
          placeholder={`ตั้งชื่อ${title}`}
          value={point.name ?? ""}
          onChange={(e) => onRename(e.target.value)}
        />
      ) : (
        <p className="muted" style={{ margin: 0 }}>
          ยังไม่ได้เลือก
        </p>
      )}
    </div>
  );
}
