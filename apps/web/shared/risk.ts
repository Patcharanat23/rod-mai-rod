import type { RiskLevel } from "./types";

// สีเดียวกันทั้งเว็บ ใช้กับเส้นทาง หมุด และ badge
export const RISK_COLOR: Record<RiskLevel | "UNKNOWN", string> = {
  LOW: "#16a34a",
  MEDIUM: "#f59e0b",
  HIGH: "#dc2626",
  UNKNOWN: "#6b7280",
};

export const RISK_LABEL: Record<RiskLevel | "UNKNOWN", string> = {
  LOW: "ต่ำ",
  MEDIUM: "ปานกลาง",
  HIGH: "สูง",
  UNKNOWN: "ไม่ทราบ",
};

// null = ไม่มีข้อมูล ห้ามแสดงเป็น "ต่ำ"
export function riskColor(level: RiskLevel | null | undefined): string {
  return RISK_COLOR[level ?? "UNKNOWN"];
}
