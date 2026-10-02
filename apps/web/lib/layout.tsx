"use client";
// ปรับหน้าตาตามผู้ใช้: ขนาดตัวอักษรทั้งเว็บ (--fs ใน globals.css) และลากเส้นแบ่งเพื่อขยาย/ย่อการ์ด จำไว้ในเครื่อง
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

export const TEXT_SIZES = [
  { scale: 1, label: "ปกติ" },
  { scale: 1.15, label: "ใหญ่" },
  { scale: 1.3, label: "ใหญ่มาก" },
  { scale: 1.5, label: "ใหญ่พิเศษ" },
];
const FS_KEY = "rmr_redesign_text";
const SPLIT_PREFIX = "rmr_redesign_split_";
const RESET_EVENT = "rmr-split-reset";

export function getTextScale(): number {
  try {
    const v = Number(localStorage.getItem(FS_KEY));
    if (TEXT_SIZES.some((s) => s.scale === v)) return v;
  } catch {}
  return 1;
}

export function applyTextScale(scale = getTextScale()) {
  document.documentElement.style.setProperty("--fs", String(scale));
  try {
    localStorage.setItem(FS_KEY, String(scale));
  } catch {}
}

// คืนขนาดการ์ดทุกหน้ากลับเป็นค่าเริ่มต้น
export function resetSplits() {
  try {
    Object.keys(localStorage)
      .filter((k) => k.startsWith(SPLIT_PREFIX))
      .forEach((k) => localStorage.removeItem(k));
  } catch {}
  window.dispatchEvent(new Event(RESET_EVENT));
}

function load(key: string, defaults: number[], min: number): number[] {
  try {
    const v = JSON.parse(localStorage.getItem(SPLIT_PREFIX + key) ?? "null");
    if (Array.isArray(v) && v.length === defaults.length && v.every((x) => typeof x === "number" && x > 0)) {
      const sum = v.reduce((a, b) => a + b, 0);
      const fractions = v.map((x) => x / sum);
      // ถ้าค่าที่บันทึกไว้แคบเกินไปกว่าลิมิตความปลอดภัย ให้ใช้ค่าเริ่มต้น
      if (fractions.every((f) => f >= min * 0.85)) return v;
    }
  } catch {}
  return defaults;
}

/**
 * แบ่งพื้นที่ grid เป็นสัดส่วนที่ลากปรับได้
 * คืน style (ตั้ง CSS var ให้ CSS เอาไปใช้เป็น grid-template) กับเส้นแบ่งที่ต้องวางไว้ใน container (position: relative)
 * จอเล็กที่ CSS ยุบเหลือคอลัมน์เดียวจะซ่อนเส้นแบ่งและไม่ใช้ var นี้
 */
export function useSplit(key: string, defaults: number[], opts: { axis?: "x" | "y"; gap?: number; min?: number; cssVar: string; label: string }) {
  const n = defaults.length;
  // กำหนดขั้นต่ำที่ปลอดภัยตามจำนวนการ์ด เพื่อไม่ให้ตัวหนังสือล้นการ์ด
  const safeDefaultMin = n === 2 ? 0.32 : n === 3 ? 0.24 : 0.2;
  const { axis = "x", gap = 18, min = safeDefaultMin, cssVar, label } = opts;
  const [weights, setWeights] = useState(defaults);
  const box = useRef<HTMLElement | null>(null);

  useEffect(() => {
    setWeights(load(key, defaults, min));
    const reset = () => setWeights(defaults);
    window.addEventListener(RESET_EVENT, reset);
    return () => window.removeEventListener(RESET_EVENT, reset);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  function save(w: number[]) {
    setWeights(w);
    try {
      localStorage.setItem(SPLIT_PREFIX + key, JSON.stringify(w));
    } catch {}
  }

  const total = weights.reduce((a, b) => a + b, 0);
  const frac = weights.map((w) => w / total);
  const cum = frac.slice(0, -1).map((_, i) => frac.slice(0, i + 1).reduce((a, b) => a + b, 0));

  // ย้ายเส้นแบ่งที่ i ไปที่สัดส่วน p โดยการ์ดสองใบข้างๆ ต้องไม่เล็กกว่า min (จำกัดการย่อขนาดไม่ให้ตัวหนังสือล้น)
  function moveTo(i: number, p: number) {
    const lo = (i === 0 ? 0 : cum[i - 1]) + min;
    const hi = (i === cum.length - 1 ? 1 : cum[i + 1]) - min;
    if (lo > hi) return;
    const next = [...cum];
    next[i] = Math.min(hi, Math.max(lo, p));
    const edges = [0, ...next, 1];
    save(edges.slice(1).map((e, k) => +(e - edges[k]).toFixed(3)));
  }

  function onPointerDown(i: number, e: React.PointerEvent<HTMLDivElement>) {
    const el = box.current;
    if (!el) return;
    e.preventDefault();
    const handle = e.currentTarget;
    handle.setPointerCapture(e.pointerId);
    const move = (ev: PointerEvent) => {
      const r = el.getBoundingClientRect();
      const size = (axis === "x" ? r.width : r.height) - (n - 1) * gap;
      const pos = (axis === "x" ? ev.clientX - r.left : ev.clientY - r.top) - i * gap - gap / 2;
      moveTo(i, pos / size);
    };
    const up = () => {
      handle.removeEventListener("pointermove", move);
      handle.removeEventListener("pointerup", up);
      handle.removeEventListener("pointercancel", up);
    };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", up);
    handle.addEventListener("pointercancel", up);
  }

  function onKeyDown(i: number, e: React.KeyboardEvent) {
    const back = axis === "x" ? "ArrowLeft" : "ArrowUp";
    const fwd = axis === "x" ? "ArrowRight" : "ArrowDown";
    if (e.key === back || e.key === fwd) {
      e.preventDefault();
      moveTo(i, cum[i] + (e.key === fwd ? 0.04 : -0.04));
    } else if (e.key === "Home" || e.key === "Enter") {
      e.preventDefault();
      save(defaults);
    }
  }

  const style = { [cssVar]: frac.map((f) => `minmax(0, ${f.toFixed(3)}fr)`).join(" ") } as CSSProperties;
  const handles: ReactNode = cum.map((c, i) => {
    const at = `calc((100% - ${(n - 1) * gap}px) * ${c.toFixed(4)} + ${i * gap + gap / 2}px)`;
    return (
      <div
        key={i}
        className={`splitter ${axis}`}
        style={axis === "x" ? { left: at } : { top: at }}
        role="separator"
        aria-orientation={axis === "x" ? "vertical" : "horizontal"}
        aria-valuenow={Math.round(c * 100)}
        aria-label={label}
        title={`ลากเพื่อปรับขนาด${label} · ดับเบิลคลิกเพื่อคืนค่าเดิม`}
        tabIndex={0}
        onPointerDown={(e) => onPointerDown(i, e)}
        onDoubleClick={() => save(defaults)}
        onKeyDown={(e) => onKeyDown(i, e)}
      />
    );
  });
  return { ref: box, style, handles };
}
