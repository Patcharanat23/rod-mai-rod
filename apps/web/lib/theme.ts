// ธีมทั้งเว็บ: ตั้ง html[data-theme] แล้ว CSS สลับชุดตัวแปรสี (globals.css ท้ายไฟล์) จำไว้ในเครื่อง
export type Theme = "dark" | "glass";
const KEY = "rmr_redesign_theme";

export const THEMES: { id: Theme; label: string; swatch: string }[] = [
  { id: "dark", label: "มืดกลาส (Dark Glass)", swatch: "linear-gradient(135deg, #0b1424, #10b981)" },
  { id: "glass", label: "ขาวกลาสสดใส (Light Glass)", swatch: "linear-gradient(135deg, #ffffff, #38bdf8, #10b981)" },
];

export function getTheme(): Theme {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "dark" || v === "glass") return v;
  } catch {}
  return "dark";
}

export function applyTheme(t: Theme = getTheme()) {
  document.documentElement.dataset.theme = t;
  try {
    localStorage.setItem(KEY, t);
  } catch {}
}
