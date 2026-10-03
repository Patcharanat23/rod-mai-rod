"use client";

// ปุ่มวงกลมน้องกิเลน: กดเปิดแชท / ลากไปวางได้ ปล่อยแล้วดูดเข้ามุมจอที่ใกล้ที่สุด จำมุมไว้ในเครื่อง
// มุมบนอยู่ใต้แถบหัวหน้า มุมซ้ายไม่ทับเมนูข้าง มุมล่างบนมือถือไม่ทับเมนูล่าง
import { useEffect, useRef, useState } from "react";

type Corner = "tl" | "tr" | "bl" | "br";
const KEY = "rmr_redesign_fab_corner";
const SIZE = 62;
const MOVE_PX = 6; // ขยับน้อยกว่านี้ = กด ไม่ใช่ลาก

function load(): Corner {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "tl" || v === "tr" || v === "bl" || v === "br") return v;
  } catch {}
  return "br";
}

// ขอบที่ต้องเว้นในแต่ละด้าน
function insets() {
  const mobile = window.matchMedia("(max-width: 860px)").matches;
  const side = document.querySelector(".sidebar");
  const sideRight = side && getComputedStyle(side).display !== "none" ? side.getBoundingClientRect().right : 0;
  return { left: sideRight + 18, right: 18, top: mobile ? 86 : 100, bottom: mobile ? 92 : 22 };
}

function cornerXY(c: Corner) {
  const i = insets();
  const size = window.matchMedia("(max-width: 860px)").matches ? 56 : SIZE;
  return {
    x: c.endsWith("l") ? i.left : window.innerWidth - i.right - size,
    y: c.startsWith("t") ? i.top : window.innerHeight - i.bottom - size,
  };
}

export default function ChatFab({ onOpen }: { onOpen: () => void }) {
  const [corner, setCorner] = useState<Corner>("br");
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const [drag, setDrag] = useState<{ x: number; y: number } | null>(null);
  const start = useRef<{ px: number; py: number; x: number; y: number; moved: boolean } | null>(null);

  useEffect(() => {
    const c = load();
    setCorner(c);
    setPos(cornerXY(c));
    const onResize = () => setPos(cornerXY(load()));
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  function onPointerDown(e: React.PointerEvent<HTMLButtonElement>) {
    if (!pos || e.button !== 0) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    start.current = { px: e.clientX, py: e.clientY, x: pos.x, y: pos.y, moved: false };
  }
  function onPointerMove(e: React.PointerEvent<HTMLButtonElement>) {
    const s = start.current;
    if (!s) return;
    const dx = e.clientX - s.px;
    const dy = e.clientY - s.py;
    if (!s.moved && Math.hypot(dx, dy) < MOVE_PX) return;
    s.moved = true;
    setDrag({
      x: Math.min(Math.max(8, s.x + dx), window.innerWidth - SIZE - 8),
      y: Math.min(Math.max(8, s.y + dy), window.innerHeight - SIZE - 8),
    });
  }
  function onPointerUp(e: React.PointerEvent<HTMLButtonElement>) {
    const s = start.current;
    start.current = null;
    if (!s) return;
    if (!s.moved) {
      onOpen();
      return;
    }
    // ดูดเข้ามุมที่ใกล้จุดปล่อยที่สุด
    const cx = e.clientX < window.innerWidth / 2 ? "l" : "r";
    const cy = e.clientY < window.innerHeight / 2 ? "t" : "b";
    const c = `${cy}${cx}` as Corner;
    setCorner(c);
    setPos(cornerXY(c));
    setDrag(null);
    try {
      localStorage.setItem(KEY, c);
    } catch {}
  }
  // คีย์บอร์ด: Enter/Space เปิด, ลูกศรย้ายมุม
  function onKeyDown(e: React.KeyboardEvent) {
    const map: Record<string, (c: Corner) => Corner> = {
      ArrowLeft: (c) => `${c[0]}l` as Corner,
      ArrowRight: (c) => `${c[0]}r` as Corner,
      ArrowUp: (c) => `t${c[1]}` as Corner,
      ArrowDown: (c) => `b${c[1]}` as Corner,
    };
    const f = map[e.key];
    if (!f) return;
    e.preventDefault();
    const c = f(corner);
    setCorner(c);
    setPos(cornerXY(c));
    try {
      localStorage.setItem(KEY, c);
    } catch {}
  }

  if (!pos) return null;
  const at = drag ?? pos;
  return (
    <button
      className={`chat-fab corner-${corner} ${drag ? "dragging" : ""}`}
      style={{ left: at.x, top: at.y }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={() => ((start.current = null), setDrag(null))}
      onClick={(e) => {
        // เปิดจากคีย์บอร์ด (Enter/Space) เท่านั้น การกดด้วยเมาส์/นิ้วจัดการใน pointerup แล้ว
        if (e.detail === 0) onOpen();
      }}
      onKeyDown={onKeyDown}
      aria-label="คุยกับน้องกิเลน (ลากหรือกดลูกศรเพื่อย้ายมุม)"
    >
      <span className="fab-tip">{drag ? "ปล่อยตรงมุมที่ต้องการ" : "ถามน้องกิเลนได้นะ · ลากย้ายได้"}</span>
      <span className="fab-ring">
        <img src="/assets/shared/qilin-avatar.webp" alt="น้องกิเลน" draggable={false} />
      </span>
      <span className="fab-dot" />
    </button>
  );
}
