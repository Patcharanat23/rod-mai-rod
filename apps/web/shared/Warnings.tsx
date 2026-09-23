import type { Warning } from "./types";

const TEXT: Record<Warning, string> = {
  WEATHER_UNAVAILABLE: "ข้อมูลสภาพอากาศบางส่วนไม่พร้อม ความเสี่ยงบางจุดจึงเป็น \"ไม่ทราบ\"",
  HAZARD_FEED_UNAVAILABLE: "ข้อมูลภัยพิบัติบางแหล่งไม่พร้อม หมุดอาจไม่ครบ",
  ALTERNATIVE_ROUTES_UNAVAILABLE: "หาเส้นทางสำรองไม่ได้ แสดงเฉพาะเส้นทางหลัก",
  FORECAST_OUT_OF_RANGE: "วันเดินทางไกลเกินช่วงพยากรณ์ ยังไม่มีข้อมูลสภาพอากาศ",
  LLM_UNAVAILABLE: "ตอนนี้ตอบคำถามทั่วไปไม่ได้ แต่คำสั่งเลื่อนทริปยังใช้ได้",
};

// ทุกหน้าที่ได้ warnings ต้องแสดงตัวนี้ (CONTRACT หัวข้อ 3)
export default function Warnings({ warnings }: { warnings?: string[] | null }) {
  if (!warnings?.length) return null;
  return (
    <div className="warnings">
      {warnings.map((w) => (
        <div key={w}>{TEXT[w as Warning] ?? w}</div>
      ))}
    </div>
  );
}
