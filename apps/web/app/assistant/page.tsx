"use client";

// หน้าคุยกับน้องกิเลนแบบเต็มหน้า ใช้บทสนทนาเดียวกับแชทลอย (lib/chat.tsx)
import Link from "next/link";
import Icon from "@/components/Icon";
import { Topbar } from "@/components/Shell";
import { Composer, MessageList } from "@/components/ChatDrawer";
import { RiskChip } from "@/components/ui";
import { RECO, thaiDateTime } from "@/lib/data";
import { useApp } from "@/lib/store";
import { chatSuggestions, chatWhen, useChat } from "@/lib/chat";

// ตัวอย่างสิ่งที่น้องกิเลนทำได้ แสดงตอนเริ่มบทสนทนาใหม่
const CAN_DO = [
  { icon: "edit", title: "สร้าง แก้ ลบทริปด้วยคำพูด", ex: "\"ไปเชียงใหม่วันเสาร์ 8 โมงเช้า\"" },
  { icon: "clock", title: "เช็กอากาศ ณ เวลาที่ไปถึง", ex: "\"Trip 01 ถึงนครสวรรค์ฝนตกไหม\"" },
  { icon: "spark", title: "หาเวลาออกที่ปลอดภัยกว่า", ex: "\"ออกกี่โมงดีที่สุด\"" },
  { icon: "shield", title: "วิธีรับมือภัยระหว่างทาง", ex: "\"รถดับกลางน้ำทำยังไง\"" },
];

export default function Assistant() {
  const { msgs, busy, send, reset, cancel, history, currentId, open, remove } = useChat();
  const { nextTrip } = useApp();
  const tripNo = nextTrip ? `Trip ${String(nextTrip.trip_no).padStart(2, "0")}` : null;
  const ideas = chatSuggestions(tripNo);
  const fresh = msgs.length <= 1;

  return (
    <>
      <Topbar title="คุยกับน้องกิเลน" sub="ผู้ช่วยวางแผนเดินทาง ตอบจากทริปของคุณและข้อมูลความเสี่ยงจริง" />
      <div className="assist">
        <section className="card assist-chat">
          <header className="assist-head">
            <span className="avatar-online big">
              <img src="/assets/shared/qilin-avatar.webp" alt="" />
            </span>
            <div className="grow" style={{ minWidth: 0 }}>
              <h3>น้องกิเลน</h3>
              <p className="tiny muted">{busy ? "กำลังพิมพ์..." : "พร้อมช่วยแล้ว"}</p>
            </div>
            <button className="btn sm ghost" onClick={reset} disabled={fresh || busy} title="ลบบทสนทนานี้แล้วเริ่มใหม่">
              <Icon name="plus" size={15} />
              เริ่มคุยใหม่
            </button>
          </header>

          <div className="assist-body">
            {fresh ? (
              <div className="assist-welcome">
                <img className="qilin-welcome-anim" src="/assets/mascots/chat-qilin-navigation.webp" alt="น้องกิเลน" />
                <h2>สวัสดีครับ น้องกิเลนเอง</h2>
                <p className="muted">อยากไปไหน หรืออยากเช็กอะไรเกี่ยวกับทริป พิมพ์มาได้เลย หรือเลือกคำถามด้านล่าง</p>
                <div className="can-inline">
                  {CAN_DO.map((c) => (
                    <span key={c.title}>
                      <Icon name={c.icon} size={14} />
                      {c.title}
                    </span>
                  ))}
                </div>
                <div className="idea-grid">
                  {ideas.map((q) => (
                    <button key={q.q} className="idea" onClick={() => send(q.q)} disabled={busy}>
                      <span className="idea-icon">
                        <Icon name={q.icon} size={18} />
                      </span>
                      <span>
                        <b>{q.title}</b>
                        <small>{q.q}</small>
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="assist-msgs">
                <MessageList msgs={msgs} busy={busy} />
              </div>
            )}
          </div>

          <footer className="assist-foot">
            {!fresh && (
              <div className="quick-chips">
                {ideas.map((q) => (
                  <button key={q.q} className="chip sm" onClick={() => send(q.q)} disabled={busy}>
                    <Icon name={q.icon} size={13} />
                    {q.q}
                  </button>
                ))}
              </div>
            )}
            <Composer onSend={send} busy={busy} autoFocus onCancel={cancel} />
            <p className="tiny muted" style={{ textAlign: "center" }}>
              กด Enter เพื่อส่ง · Shift + Enter ขึ้นบรรทัดใหม่ · น้องกิเลนอาจตอบผิดได้ เรื่องฉุกเฉินให้โทร 1669 หรือ 1784
            </p>
          </footer>
        </section>

        <aside className="assist-side">
          <section className="card">
            <p className="sec-title">
              <Icon name="route" size={15} /> ทริปถัดไป
            </p>
            {nextTrip ? (
              <Link href={`/trips?id=${nextTrip.trip_id}`} className="side-trip">
                <span className="row between nowrap">
                  <span className="tiny muted">{tripNo}</span>
                  {nextTrip.plan && <RiskChip level={nextTrip.plan.risk_level} />}
                </span>
                <b className="ellipsis">{nextTrip.title}</b>
                <span className="tiny muted">{thaiDateTime(nextTrip.departure_time)}</span>
                {nextTrip.plan && <span className="small">{RECO[nextTrip.plan.recommendation].title}</span>}
              </Link>
            ) : (
              <p className="small muted">ยังไม่มีทริป ลองพิมพ์ว่า &quot;ไปหัวหินวันเสาร์นี้ 9 โมง&quot; น้องกิเลนสร้างให้ได้เลย</p>
            )}
          </section>

          <section className="card grow-card history-card">
            <div className="row between nowrap" style={{ marginBottom: 10 }}>
              <p className="sec-title" style={{ margin: 0 }}>
                <Icon name="list" size={15} /> ประวัติแชท
              </p>
              <span className="tiny muted">{history.length} บทสนทนา</span>
            </div>
            {history.length === 0 && <p className="small muted">ยังไม่มีประวัติ คุยกับน้องกิเลนแล้วจะเก็บไว้ที่นี่ กด &quot;เริ่มคุยใหม่&quot; เรื่องเดิมก็ยังอยู่</p>}
            <div className="history-list">
              {history.map((c) => (
                <div key={c.id} className={`history-item ${c.id === currentId ? "on" : ""}`}>
                  <button className="history-open" onClick={() => open(c.id)} disabled={busy || c.id === currentId} title={c.title}>
                    <b className="ellipsis">{c.title}</b>
                    <small>
                      {chatWhen(c.at)} · {c.msgs.filter((m) => m.role === "me").length} คำถาม
                      {c.id === currentId ? " · กำลังคุย" : ""}
                    </small>
                  </button>
                  <button
                    className="history-del"
                    onClick={() => confirm("ลบบทสนทนานี้ใช่ไหม") && remove(c.id)}
                    disabled={busy}
                    aria-label={`ลบบทสนทนา ${c.title}`}
                    title="ลบ"
                  >
                    <Icon name="trash" size={14} />
                  </button>
                </div>
              ))}
            </div>
          </section>

          <section className="card side-sos">
            <Icon name="phone" size={18} />
            <span className="grow small">
              เหตุฉุกเฉินจริง อย่ารอแชท
              <br />
              <b>โทร 1669 · 191 · 1784</b>
            </span>
            <Link href="/emergency" className="btn sm ghost">
              ดูเบอร์ทั้งหมด
            </Link>
          </section>
        </aside>
      </div>
    </>
  );
}
