// เวลาในระบบเป็น UTC เสมอ แปลงเป็นเวลาไทยตอนแสดงผลด้วยฟังก์ชันในไฟล์นี้เท่านั้น

const TZ = "Asia/Bangkok";

// "2026-09-28T01:00:00Z" -> "28 ก.ย. 08:00"
export function formatThaiTime(iso: string | null | undefined): string {
  if (!iso) return "-";
  return new Intl.DateTimeFormat("th-TH", {
    timeZone: TZ,
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

// 565 -> "9 ชม. 25 นาที"
export function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  return h > 0 ? `${h} ชม. ${m} นาที` : `${m} นาที`;
}

// ค่าจาก <input type="datetime-local"> เช่น "2026-09-28T08:00" ถือเป็นเวลาไทย -> UTC ที่ส่ง api-backend ได้
export function thaiInputToUtc(value: string): string {
  return new Date(`${value}:00+07:00`).toISOString().replace(".000Z", "Z");
}

// กลับด้าน ใช้ใส่ค่าเริ่มต้นให้ <input type="datetime-local">
export function utcToThaiInput(iso: string): string {
  const d = new Date(new Date(iso).getTime() + 7 * 60 * 60 * 1000);
  return d.toISOString().slice(0, 16);
}
