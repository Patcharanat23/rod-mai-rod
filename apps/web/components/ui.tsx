"use client";

import Icon from "./Icon";
import { RECO, RISK_TH, riskKey, type Recommendation, type Risk } from "@/lib/data";

export function RiskChip({ level, score, size }: { level: Risk | undefined; score?: number | null; size?: "lg" }) {
  const k = riskKey(level);
  return (
    <span className={`risk ${k} ${size ?? ""}`}>
      ความเสี่ยง{RISK_TH[k]}
      {score != null && <span className="score">· {score}</span>}
    </span>
  );
}

const RECO_ICON = { ok: "check", warn: "clock", danger: "alert", info: "info" } as const;

export function RecoBanner({ reco, summary, action }: { reco: Recommendation; summary: string; action?: React.ReactNode }) {
  const r = RECO[reco];
  const icon = reco === "REROUTE" ? "route" : RECO_ICON[r.tone];
  return (
    <div className={`banner ${r.tone}`}>
      <span className="b-icon">
        <Icon name={icon} size={19} stroke={2.2} />
      </span>
      <div className="grow">
        <p className="bold">{r.title}</p>
        <p className="small" style={{ color: "var(--ink-2)" }}>
          {summary}
        </p>
      </div>
      {action}
    </div>
  );
}

export function CardHead({ icon, tone, title, sub, right }: { icon: string; tone?: "aqua" | "sun" | "red"; title: string; sub?: string; right?: React.ReactNode }) {
  return (
    <div className="card-head">
      <span className={`card-icon ${tone ?? ""}`}>
        <Icon name={icon} />
      </span>
      <div className="grow">
        <h3>{title}</h3>
        {sub && <p>{sub}</p>}
      </div>
      {right}
    </div>
  );
}
