"use client";

import { useEffect, useId, useRef, useState } from "react";
import { api } from "@/shared/api";
import type { PlaceResult } from "@/shared/types";

const DEBOUNCE_MS = 400;
const MIN_CHARS = 2;
const MAX_RESULTS = 5;
const TIMEOUT_MS = 8000; // ค้นนานเกินนี้ถือว่าพัง ห้ามค้าง

type Status = "idle" | "searching" | "done" | "error";
type Props = { label: string; onPick: (p: PlaceResult) => void };

function withTimeout<T>(p: Promise<T>): Promise<T> {
  return Promise.race([p, new Promise<T>((_, reject) => setTimeout(() => reject(new Error("timeout")), TIMEOUT_MS))]);
}

// ช่องพิมพ์ชื่อสถานที่ แล้วมีรายการให้กด (GET /places/search, CONTRACT หัวข้อ 6)
export default function PlaceSearch({ label, onPick }: Props) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<PlaceResult[]>([]);
  const [status, setStatus] = useState<Status>("idle");
  const [active, setActive] = useState(0);
  const requestNo = useRef(0);
  const listId = useId();

  useEffect(() => {
    const text = q.trim();
    const no = ++requestNo.current; // คำตอบของคำค้นเก่าที่มาช้า ทิ้งไป
    if (text.length < MIN_CHARS) {
      setResults([]);
      setStatus("idle");
      return;
    }
    const timer = setTimeout(async () => {
      setStatus("searching");
      try {
        const data = await withTimeout(api<{ places: PlaceResult[] }>(`/places/search?q=${encodeURIComponent(text)}`));
        if (no !== requestNo.current) return;
        setResults(data.places.slice(0, MAX_RESULTS));
        setActive(0);
        setStatus("done");
      } catch {
        if (no !== requestNo.current) return;
        setResults([]);
        setStatus("error");
      }
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [q]);

  function choose(p: PlaceResult) {
    onPick(p);
    requestNo.current++;
    setQ("");
    setResults([]);
    setStatus("idle");
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault(); // ไม่ให้ Enter ไปกดบันทึกฟอร์ม
      if (results[active]) choose(results[active]);
    } else if (e.key === "ArrowDown" && results.length) {
      e.preventDefault();
      setActive((i) => (i + 1) % results.length);
    } else if (e.key === "ArrowUp" && results.length) {
      e.preventDefault();
      setActive((i) => (i - 1 + results.length) % results.length);
    } else if (e.key === "Escape") {
      setQ("");
    }
  }

  return (
    <div style={{ position: "relative" }}>
      <input
        aria-label={`ค้นหา${label}`}
        placeholder={`พิมพ์ชื่อ${label} เช่น กทม`}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={onKeyDown}
        role="combobox"
        aria-expanded={results.length > 0}
        aria-controls={listId}
        aria-autocomplete="list"
        autoComplete="off"
      />
      {status === "searching" && <p className="muted" style={{ margin: "4px 0 0" }}>กำลังค้นหา...</p>}
      {status === "done" && results.length === 0 && (
        <p className="muted" style={{ margin: "4px 0 0" }}>
          ไม่เจอสถานที่นี้ ลองพิมพ์ชื่ออื่น หรือจิ้มแผนที่แทน
        </p>
      )}
      {status === "error" && (
        <p className="error-text" style={{ margin: "4px 0 0" }}>
          ค้นหาสถานที่ไม่ได้ตอนนี้ จิ้มแผนที่หรือกดสถานที่ตัวอย่างแทน
        </p>
      )}
      {results.length > 0 && (
        <ul
          id={listId}
          role="listbox"
          style={{
            listStyle: "none",
            margin: "4px 0 0",
            padding: 4,
            background: "var(--glass-hi)",
            border: "1px solid var(--line)",
            borderRadius: 12,
            boxShadow: "var(--shadow)",
          }}
        >
          {results.map((r, i) => (
            <li
              key={`${r.lat},${r.lng},${r.name}`}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => {
                e.preventDefault(); // กดก่อนช่องพิมพ์เสีย focus
                choose(r);
              }}
              onMouseEnter={() => setActive(i)}
              style={{
                padding: "6px 10px",
                borderRadius: 8,
                cursor: "pointer",
                background: i === active ? "rgba(67, 136, 243, 0.12)" : "transparent",
              }}
            >
              <div>{r.name}</div>
              {r.detail && r.detail !== r.name && (
                <div className="muted" style={{ fontSize: 12 }}>
                  {r.detail}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
