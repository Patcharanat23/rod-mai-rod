"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import Icon from "./Icon";
import { useApp } from "@/lib/store";
import { ACTION_TH, chatSuggestions, chatTime, useChat, type Msg } from "@/lib/chat";

// ---------- ชิ้นส่วนที่ใช้ร่วมกับหน้า /assistant ----------

export function MessageList({ msgs, busy, onNavigate }: { msgs: Msg[]; busy: boolean; onNavigate?: () => void }) {
  const { trips } = useApp();
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [msgs, busy]);
  return (
    <>
      {msgs.map((m, i) => (
        <div key={i} className={`bubble-row ${m.role}`}>
          {m.role === "bot" && <img className="bubble-avatar" src="/assets/shared/qilin-avatar.webp" alt="" />}
          <div className="bubble-col">
            <div className={`msg ${m.role} ${m.error ? "error" : ""}`}>{m.text}</div>
            {m.actions?.map((a, j) => {
              const t = trips.find((x) => x.trip_no === a.trip_no);
              const no = `Trip ${String(a.trip_no ?? "").padStart(2, "0")}`;
              return (
                <div key={j} className="msg-action">
                  <Icon name={a.type === "TRIP_DELETED" ? "trash" : "check"} size={17} />
                  <span className="grow">
                    {ACTION_TH[a.type]} {no} แล้ว
                  </span>
                  {a.type !== "TRIP_DELETED" && (
                    <Link href={t ? `/trips?id=${t.trip_id}` : "/trips"} className="btn sm ghost" onClick={onNavigate}>
                      ดูทริป
                    </Link>
                  )}
                </div>
              );
            })}
            <span className="bubble-time">{chatTime(m.at)}</span>
          </div>
        </div>
      ))}
      {busy && (
        <div className="bubble-row bot">
          <img className="bubble-avatar" src="/assets/shared/qilin-avatar.webp" alt="" />
          <div className="msg bot typing" aria-label="น้องกิเลนกำลังพิมพ์">
            <i />
            <i />
            <i />
          </div>
        </div>
      )}
      <div ref={end} />
    </>
  );
}

// ช่องพิมพ์: Enter ส่ง, Shift+Enter ขึ้นบรรทัดใหม่, ขยายสูงตามข้อความ
export function Composer({ onSend, busy, autoFocus, onCancel }: { onSend: (t: string) => void; busy: boolean; autoFocus?: boolean; onCancel?: () => void }) {
  const [text, setText] = useState("");
  const ta = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = ta.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }, [text]);
  function submit() {
    if (!text.trim() || busy) return;
    onSend(text);
    setText("");
  }
  return (
    <form
      className="composer"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <textarea
        ref={ta}
        rows={1}
        value={text}
        autoFocus={autoFocus}
        maxLength={500}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            submit();
          }
        }}
        placeholder="พิมพ์ถามน้องกิเลน เช่น เลื่อนทริปไปพรุ่งนี้บ่ายสองโมง"
        aria-label="ข้อความถึงน้องกิเลน"
      />
      {busy && onCancel ? (
        <button type="button" className="btn stop" onClick={onCancel} aria-label="หยุดรอคำตอบ" title="หยุดรอคำตอบ">
          <span className="stop-square" />
        </button>
      ) : (
        <button className="btn" disabled={busy || !text.trim()} aria-label="ส่ง">
          <Icon name="send" size={18} />
        </button>
      )}
    </form>
  );
}

// ---------- แชทลอย (เปิดจากปุ่มวงกลมน้องกิเลน ได้ทุกหน้า) ----------

export default function ChatDrawer({ onClose }: { onClose: () => void }) {
  const { msgs, busy, send, cancel, reset } = useChat();
  const { nextTrip } = useApp();
  const quick = chatSuggestions(nextTrip ? `Trip ${String(nextTrip.trip_no).padStart(2, "0")}` : null);

  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);

  return (
    <>
      <div className="drawer-bg" onClick={onClose} />
      <section className="drawer" role="dialog" aria-label="คุยกับน้องกิเลน">
        <div className="drawer-head">
          <span className="avatar-online">
            <img src="/assets/shared/qilin-avatar.webp" alt="" />
          </span>
          <div className="grow">
            <h3>น้องกิเลน</h3>
            <p className="small muted">ผู้ช่วยวางแผนเดินทางอย่างปลอดภัย</p>
          </div>
          <button className="icon-btn" onClick={reset} disabled={busy || msgs.length <= 1} aria-label="เริ่มคุยใหม่" title="เริ่มคุยใหม่ (เก็บบทสนทนานี้ไว้ในประวัติ)">
            <Icon name="plus" size={18} />
          </button>
          <Link href="/assistant" className="icon-btn" onClick={onClose} aria-label="เปิดเต็มหน้า" title="เปิดเต็มหน้า (ดูประวัติแชท)">
            <Icon name="layers" size={18} />
          </Link>
          <button className="icon-btn" onClick={onClose} aria-label="ปิด">
            <Icon name="x" />
          </button>
        </div>
        <div className="msgs">
          <MessageList msgs={msgs} busy={busy} onNavigate={onClose} />
        </div>
        <div className="quick-chips">
          {quick.map((q) => (
            <button key={q.q} className="chip sm" onClick={() => send(q.q)} disabled={busy}>
              <Icon name={q.icon} size={13} />
              {q.q}
            </button>
          ))}
        </div>
        <Composer onSend={send} busy={busy} autoFocus onCancel={cancel} />
      </section>
    </>
  );
}
