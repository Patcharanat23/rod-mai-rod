"use client";

// โมดูล 3 อ่าน app/assistant/README.md ก่อน จุดที่ต้องเติมมี TODO(web-safety-assistant)
import Link from "next/link";
import { useRef, useState } from "react";
import Warnings from "@/shared/Warnings";
import { api, ApiError } from "@/shared/api";
import type { ChatAction, ChatMessage, ChatReply } from "@/shared/types";

const HISTORY_LIMIT = 10;

// ปุ่มคำถามตัวอย่างสำหรับสาธิต (README ข้อ 7)
const SAMPLE_PROMPTS = [
  "ช่วงนี้เที่ยวที่ไหนดี",
  "เลื่อน Trip 01 ไปวันถัดไป",
  "Trip 01 อากาศเป็นยังไง",
  "น้ำท่วมระหว่างทางต้องทำยังไง",
];

const ACTION_TEXT: Record<ChatAction["type"], string> = {
  TRIP_CREATED: "ถูกสร้างแล้ว",
  TRIP_UPDATED: "ถูกแก้แล้ว",
  TRIP_DELETED: "ถูกลบแล้ว",
};

// actions เก็บไว้แสดงการ์ดเท่านั้น ไม่ส่งกลับไปใน history
type Message = ChatMessage & { actions?: ChatAction[] };

function tripLabel(no: number) {
  return `Trip ${String(no).padStart(2, "0")}`;
}

function ActionCards({ actions }: { actions: ChatAction[] }) {
  const known = actions.filter((a) => a.type in ACTION_TEXT);
  if (!known.length) return null;
  return (
    <div style={{ display: "grid", gap: 6, margin: "4px 0 12px" }}>
      {known.map((a, i) => (
        <div
          key={`${a.trip_id}-${a.type}-${i}`}
          className="row"
          style={{ justifyContent: "space-between", border: "1px solid #bfdbfe", background: "#eff6ff", borderRadius: 6, padding: "8px 12px" }}
        >
          <span>
            {tripLabel(a.trip_no)} {ACTION_TEXT[a.type]}
          </span>
          <Link href="/my-trip" className="btn btn-outline" style={{ padding: "4px 10px", fontSize: 14 }}>
            ไปที่ My Trip
          </Link>
        </div>
      ))}
    </div>
  );
}

export default function AssistantPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [lastReply, setLastReply] = useState<ChatReply | null>(null);
  // กันกด Enter รัวๆ ก่อน state busy อัปเดตทัน
  const sending = useRef(false);

  async function send(text: string) {
    if (!text.trim() || sending.current) return;
    sending.current = true;
    const history: ChatMessage[] = messages.slice(-HISTORY_LIMIT).map(({ role, content }) => ({ role, content }));
    setMessages([...messages, { role: "user", content: text }]);
    setInput("");
    setBusy(true);
    try {
      const reply = await api<ChatReply>("/assistant/chat", { method: "POST", body: { message: text, history } });
      setLastReply(reply);
      setMessages((m) => [...m, { role: "assistant", content: reply.reply, actions: reply.actions ?? [] }]);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "ส่งข้อความไม่สำเร็จ";
      setMessages((m) => [...m, { role: "assistant", content: msg }]);
    } finally {
      sending.current = false;
      setBusy(false);
    }
  }

  return (
    <div className="card" style={{ maxWidth: 760, margin: "0 auto" }}>
      <h3>ผู้ช่วยวางแผนทริป</h3>
      <Warnings warnings={lastReply?.warnings} />
      <div style={{ minHeight: 300 }}>
        {messages.length === 0 && !busy && <p className="muted">ลองกดคำถามตัวอย่างด้านล่าง หรือพิมพ์คำถามเอง</p>}
        {messages.map((m, i) => (
          <div key={i}>
            {/* แสดงเป็นข้อความธรรมดา ห้ามใช้ dangerouslySetInnerHTML (README ข้อ 4) */}
            <p style={{ textAlign: m.role === "user" ? "right" : "left", whiteSpace: "pre-wrap" }}>{m.content}</p>
            {m.actions && <ActionCards actions={m.actions} />}
          </div>
        ))}
        {busy && <p className="muted">กำลังพิมพ์...</p>}
      </div>
      <div className="row" style={{ marginBottom: 8 }}>
        {SAMPLE_PROMPTS.map((p) => (
          <button key={p} className="btn btn-outline" style={{ fontSize: 14 }} onClick={() => send(p)} disabled={busy}>
            {p}
          </button>
        ))}
      </div>
      <div className="row">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            // Enter ตอนกำลังเลือกตัวอักษรไทยห้ามส่ง (README ข้อ 1) keyCode 229 คือ Enter ของ IME บางเบราว์เซอร์
            if (e.key === "Enter" && !e.nativeEvent.isComposing && e.keyCode !== 229) {
              e.preventDefault();
              send(input);
            }
          }}
          placeholder="พิมพ์ข้อความ เช่น เลื่อน Trip 01 ไปวันถัดไป"
          style={{ flex: 1, width: "auto" }}
        />
        <button className="btn" onClick={() => send(input)} disabled={busy}>
          ส่ง
        </button>
      </div>
    </div>
  );
}
