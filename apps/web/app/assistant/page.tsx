"use client";

// โมดูล 3 อ่าน app/assistant/README.md ก่อน จุดที่ต้องเติมมี TODO(web-safety-assistant)
import { useState } from "react";
import Warnings from "@/shared/Warnings";
import { api, ApiError } from "@/shared/api";
import type { ChatMessage, ChatReply } from "@/shared/types";

const HISTORY_LIMIT = 10;

export default function AssistantPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [lastReply, setLastReply] = useState<ChatReply | null>(null);

  async function send(text: string) {
    if (!text.trim() || busy) return;
    const history = messages.slice(-HISTORY_LIMIT);
    setMessages([...messages, { role: "user", content: text }]);
    setInput("");
    setBusy(true);
    try {
      const reply = await api<ChatReply>("/assistant/chat", { method: "POST", body: { message: text, history } });
      setLastReply(reply);
      setMessages((m) => [...m, { role: "assistant", content: reply.reply }]);
      // TODO(web-safety-assistant): ถ้า reply.actions มี TRIP_* แสดงการ์ดทริปที่เปลี่ยน + ปุ่มไป My Trip (README ข้อ 3)
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "ส่งข้อความไม่สำเร็จ";
      setMessages((m) => [...m, { role: "assistant", content: msg }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card" style={{ maxWidth: 760, margin: "0 auto" }}>
      <h3>ผู้ช่วยวางแผนทริป</h3>
      <Warnings warnings={lastReply?.warnings} />
      <div style={{ minHeight: 300 }}>
        {messages.map((m, i) => (
          // แสดงเป็นข้อความธรรมดา ห้ามใช้ dangerouslySetInnerHTML (README ข้อ 4)
          <p key={i} style={{ textAlign: m.role === "user" ? "right" : "left", whiteSpace: "pre-wrap" }}>
            {m.content}
          </p>
        ))}
        {busy && <p className="muted">กำลังพิมพ์...</p>}
      </div>
      {/* TODO(web-safety-assistant): ปุ่มคำถามตัวอย่าง 3-4 ปุ่ม (README ข้อ 7) */}
      <div className="row">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            // Enter ตอนกำลังเลือกตัวอักษรไทยห้ามส่ง (README ข้อ 1)
            if (e.key === "Enter" && !e.nativeEvent.isComposing) send(input);
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
