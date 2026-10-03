"use client";

import { useEffect, useState } from "react";
import Icon from "./Icon";
import { RiskChip } from "./ui";
import { RISK_COLOR, RISK_TH, addHours, riskKey, thaiTime, weatherIcon, type Plan, type Waypoint } from "@/lib/data";
import { loadDepartures, type Departure, type LiveTrip } from "@/lib/store";

const KIND_TH = { ORIGIN: "ต้นทาง", STOP: "จุดแวะ", DESTINATION: "ปลายทาง" } as const;

// สภาพอากาศ ณ เวลาที่ไปถึงแต่ละจุด เรียงตามเส้นทาง (แบบแนวนอน)
export function RouteTimeline({ waypoints }: { waypoints: Waypoint[] }) {
  return (
    <div className="timeline">
      {waypoints.map((w) => (
        <div key={w.waypoint_id} className="tl-step" title={w.forecast?.condition_th ?? "ยังไม่มีข้อมูลอากาศ"}>
          <div className="tl-dot" style={{ background: RISK_COLOR[riskKey(w.risk_level)] }}>
            <Icon name={w.kind === "DESTINATION" ? "flag" : w.kind === "ORIGIN" ? "car" : "pin"} size={15} stroke={2.2} />
          </div>
          <div className="when">{thaiTime(w.eta)}</div>
          <div className="where">
            {KIND_TH[w.kind]} · {w.name}
          </div>
          <div className="wx">
            <Icon name={weatherIcon(w.forecast)} size={16} />
            {w.forecast ? `${w.forecast.rain_mm_per_h} มม.` : "ไม่ทราบ"}
          </div>
        </div>
      ))}
    </div>
  );
}

// รายการจุดแบบละเอียด (แนวตั้ง)
export function StopList({ waypoints }: { waypoints: Waypoint[] }) {
  return (
    <div className="stops">
      {waypoints.map((w) => (
        <div key={w.waypoint_id} className="stop">
          <span className="node" style={{ background: `${RISK_COLOR[riskKey(w.risk_level)]}1a`, color: RISK_COLOR[riskKey(w.risk_level)] }}>
            <Icon name={w.kind === "DESTINATION" ? "flag" : w.kind === "ORIGIN" ? "car" : "pin"} size={18} />
          </span>
          <div>
            <p className="bold">{w.name}</p>
            <p className="small muted">
              {KIND_TH[w.kind]} · ถึง {thaiTime(w.eta)}
            </p>
            <p className="small row" style={{ gap: 12, marginTop: 4 }}>
              {w.forecast ? (
                <>
                  <span className="row" style={{ gap: 4 }}>
                    <Icon name={weatherIcon(w.forecast)} size={16} />
                    {w.forecast.condition_th}
                  </span>
                  <span className="row" style={{ gap: 4 }}>
                    <Icon name="rain" size={16} />
                    {w.forecast.rain_mm_per_h} มม./ชม.
                  </span>
                  <span className="row" style={{ gap: 4 }}>
                    <Icon name="wind" size={16} />
                    {w.forecast.wind_kmh} กม./ชม.
                  </span>
                  <span className="row" style={{ gap: 4 }}>
                    <Icon name="thermo" size={16} />
                    {w.forecast.temp_c}°
                  </span>
                </>
              ) : (
                <span className="muted">ยังไม่มีข้อมูลอากาศ</span>
              )}
            </p>
          </div>
          <RiskChip level={w.risk_level} />
        </div>
      ))}
    </div>
  );
}

// ฟีเจอร์ใหม่: เทียบความเสี่ยงถ้าออกตามเวลาเดิม / ช้าไป 3 / 6 ชม. แนะนำช่วงที่ปลอดภัยที่สุด
export function DepartureAdvisor({ trip, onPick, busy }: { trip: LiveTrip; onPick?: (offset: number) => void; busy?: boolean }) {
  const [deps, setDeps] = useState<Departure[] | null>(null);
  useEffect(() => {
    let live = true;
    setDeps(null);
    loadDepartures(trip).then((d) => live && setDeps(d));
    return () => {
      live = false;
    };
  }, [trip]);
  if (!trip.plan) return <p className="small muted">วางแผนทริปก่อน แล้วน้องกิเลนจะเทียบเวลาออกให้</p>;
  if (!deps) return <p className="small muted">น้องกิเลนกำลังลองเลื่อนเวลาออก +3 และ +6 ชม. ให้...</p>;
  const order = { LOW: 0, MEDIUM: 1, HIGH: 2 } as Record<string, number>;
  const best = [...deps].sort(
    (a, b) => (order[riskKey(a.risk_level)] ?? 3) - (order[riskKey(b.risk_level)] ?? 3) || (a.risk_score ?? 99) - (b.risk_score ?? 99),
  )[0];
  return (
    <div className="depart-grid">
      {deps.map((d) => {
        const k = riskKey(d.risk_level);
        const isBest = d === best;
        return (
          <button key={d.offset_h} className={`depart ${isBest ? "best" : ""}`} disabled={busy} onClick={() => onPick?.(d.offset_h)}>
            <div className="row between">
              <span className="t">{d.offset_h === 0 ? "ตามเวลาเดิม" : `ช้าไป ${d.offset_h} ชม.`}</span>
              {isBest && (
                <span className="tiny bold" style={{ color: "var(--low)" }}>
                  แนะนำ
                </span>
              )}
            </div>
            <div className="h">{thaiTime(addHours(trip.departure_time, d.offset_h))}</div>
            <span className={`risk ${k}`}>{RISK_TH[k]}</span>
            <div className="bar">
              <i style={{ width: `${d.risk_score ?? 0}%`, background: RISK_COLOR[k] }} />
            </div>
          </button>
        );
      })}
    </div>
  );
}

// ---------- เช็กลิสต์ของแต่ละทริป ----------
// ผู้ใช้เพิ่ม ลบ แก้เองได้ แยกกันทุกทริป เก็บในเครื่อง (API ยังไม่มีที่เก็บเช็กลิสต์)
// มี 2 กลุ่ม: เตรียมก่อนออก (รถ/มือถือ/บอกคนที่บ้าน) กับ ของที่ต้องเอาไป (ต่างกันไปแต่ละทริป)
type Group = "prep" | "pack";
type Item = { id: string; text: string; done: boolean; group: Group };

const GROUP_TH: Record<Group, string> = { prep: "เตรียมก่อนออก", pack: "ของที่ต้องเอาไป" };
const DEFAULTS: Omit<Item, "id" | "done">[] = [
  { group: "prep", text: "เช็กลมยาง น้ำมันเครื่อง และไฟหน้า-ไฟเบรก" },
  { group: "prep", text: "ชาร์จมือถือและพาวเวอร์แบงก์ให้เต็ม" },
  { group: "prep", text: "บอกเส้นทางและเวลาถึงให้คนที่บ้านรู้" },
  { group: "prep", text: "เช็กความเสี่ยงอีกรอบก่อนออก 1 ชั่วโมง" },
  { group: "pack", text: "บัตรประชาชนและใบขับขี่" },
  { group: "pack", text: "ยาประจำตัว" },
];
const OLD_CHECKS = [
  "เช็กลมยาง น้ำมันเครื่อง และไฟหน้า-ไฟเบรก",
  "ชาร์จมือถือและพาวเวอร์แบงก์ให้เต็ม",
  "ดาวน์โหลดแผนที่ออฟไลน์ของเส้นทาง",
  "บันทึกเบอร์ฉุกเฉิน 1784 และ 1193 ไว้ในเครื่อง",
  "บอกเส้นทางและเวลาถึงให้คนที่บ้านรู้",
  "เช็กความเสี่ยงอีกรอบก่อนออก 1 ชั่วโมง",
];
const newId = () => Math.random().toString(36).slice(2, 10);

function loadItems(tripId: string): Item[] {
  try {
    const saved = localStorage.getItem(`checklist2-${tripId}`);
    if (saved) return JSON.parse(saved);
    // ย้ายของเดิม (เก็บเป็นลำดับข้อที่ติ๊ก) มาเป็นรูปแบบใหม่
    const old: number[] = JSON.parse(localStorage.getItem(`checklist-${tripId}`) ?? "[]");
    const doneText = new Set(old.map((i) => OLD_CHECKS[i]));
    return DEFAULTS.map((d) => ({ ...d, id: newId(), done: doneText.has(d.text) }));
  } catch {
    return DEFAULTS.map((d) => ({ ...d, id: newId(), done: false }));
  }
}

export function Checklist({ tripId, suggest = [] }: { tripId: string; suggest?: string[] }) {
  const [items, setItems] = useState<Item[] | null>(null);
  const [draft, setDraft] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  useEffect(() => setItems(loadItems(tripId)), [tripId]);

  function save(next: Item[]) {
    setItems(next);
    try {
      localStorage.setItem(`checklist2-${tripId}`, JSON.stringify(next));
    } catch {}
  }
  if (!items) return null;
  const add = (text: string, group: Group = "pack") => {
    const t = text.trim();
    if (!t || items.some((i) => i.text === t)) return;
    save([...items, { id: newId(), text: t, done: false, group }]);
  };
  const done = items.filter((i) => i.done).length;
  const ideas = suggest.filter((s) => !items.some((i) => i.text === s));

  return (
    <div className="checklist">
      <div className="row between nowrap">
        <span className="small muted">
          พร้อมแล้ว {done}/{items.length}
        </span>
        <div className="bar" style={{ width: 110, marginTop: 0 }}>
          <i style={{ width: `${items.length ? (done / items.length) * 100 : 0}%`, background: "var(--low)" }} />
        </div>
      </div>

      <div className="checklist-body">
        {(["pack", "prep"] as Group[]).map((g) => {
          const list = items.filter((i) => i.group === g);
          if (!list.length) return null;
          return (
            <div key={g} className="stack" style={{ gap: 6 }}>
              <p className="label">{GROUP_TH[g]}</p>
              {list.map((it) => (
                <div key={it.id} className={`check ${it.done ? "done" : ""}`}>
                  <input type="checkbox" checked={it.done} onChange={() => save(items.map((x) => (x.id === it.id ? { ...x, done: !x.done } : x)))} aria-label={it.text} />
                  {editing === it.id ? (
                    <input
                      className="check-edit"
                      autoFocus
                      defaultValue={it.text}
                      onBlur={(e) => {
                        const t = e.target.value.trim();
                        save(items.map((x) => (x.id === it.id && t ? { ...x, text: t } : x)));
                        setEditing(null);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
                        if (e.key === "Escape") setEditing(null);
                      }}
                    />
                  ) : (
                    <span className="small grow" onDoubleClick={() => setEditing(it.id)} title="ดับเบิลคลิกเพื่อแก้">
                      {it.text}
                    </span>
                  )}
                  <button className="check-del" onClick={() => save(items.filter((x) => x.id !== it.id))} aria-label={`ลบ ${it.text}`}>
                    <Icon name="x" size={14} />
                  </button>
                </div>
              ))}
            </div>
          );
        })}
        {items.length === 0 && <p className="small muted">ยังไม่มีรายการ เพิ่มของที่ต้องเตรียมได้เลย</p>}
      </div>

      {ideas.length > 0 && (
        <div className="check-ideas">
          <span className="tiny muted">น้องกิเลนแนะนำสำหรับทริปนี้</span>
          <div className="row" style={{ gap: 6 }}>
            {ideas.slice(0, 4).map((s) => (
              <button key={s} className="chip sm" onClick={() => add(s)}>
                <Icon name="plus" size={13} />
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      <form
        className="check-add"
        onSubmit={(e) => {
          e.preventDefault();
          add(draft);
          setDraft("");
        }}
      >
        <input className="input" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="เพิ่มรายการ เช่น ครีมกันแดด" maxLength={80} />
        <button className="btn sm" disabled={!draft.trim()} aria-label="เพิ่มรายการ">
          <Icon name="plus" size={16} />
        </button>
      </form>
    </div>
  );
}

// ของที่ควรเอาไปตามสภาพทริปจริง (อากาศตอนไปถึง ภัยบนเส้นทาง ระยะเวลา)
export function tripSuggestions(plan: Plan | null, routeTips: string[]): string[] {
  if (!plan) return [];
  const out: string[] = [];
  const wx = plan.waypoints.map((w) => w.forecast).filter((f): f is NonNullable<typeof f> => !!f);
  if (wx.some((f) => f.rain_mm_per_h >= 1)) out.push("ร่มหรือเสื้อกันฝน");
  if (routeTips.some((t) => t.includes("น้ำท่วม"))) out.push("รองเท้ากันน้ำ", "ถุงกันน้ำใส่มือถือ");
  if (wx.some((f) => f.temp_c >= 33)) out.push("น้ำดื่มและหมวก");
  if (wx.some((f) => f.temp_c <= 20)) out.push("เสื้อกันหนาว");
  if (plan.duration_min >= 240) out.push("ขนมและน้ำดื่มระหว่างทาง", "หมอนรองคอ");
  if (plan.risk_level === "HIGH") out.push("ไฟฉายและถ่านสำรอง");
  out.push("สายชาร์จและที่ชาร์จในรถ", "เงินสดสำรอง");
  return out;
}
