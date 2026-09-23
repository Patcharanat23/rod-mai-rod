"use client";

import { useApi } from "./useApi";
import type { Emergency, HazardType } from "./types";

// คำแนะนำฉุกเฉิน + เบอร์ติดต่อ แสดงเมื่อเส้นทางหรือหมุดภัยเป็น HIGH
// ดึงไม่ได้หรือยังไม่มีคำแนะนำของภัยชนิดนี้ ไม่แสดงอะไร (RUNBOOK หัวข้อ C)
export default function EmergencyCard({ hazardType }: { hazardType: HazardType }) {
  const { data } = useApi<Emergency>(`/safety/emergency?hazard_type=${hazardType}`);
  if (!data) return null;
  return (
    <div className="card" style={{ borderColor: "#dc2626" }}>
      <strong>ข้อควรปฏิบัติ</strong>
      <ul>
        {data.steps_th.map((s) => (
          <li key={s}>{s}</li>
        ))}
      </ul>
      <div className="row">
        {data.contacts.map((c) => (
          <a key={c.phone} className="btn btn-outline" href={`tel:${c.phone}`}>
            {c.name_th} {c.phone}
          </a>
        ))}
      </div>
    </div>
  );
}
