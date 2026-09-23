import { RISK_LABEL, riskColor } from "./risk";
import type { RiskLevel } from "./types";

export default function RiskBadge({ level, score }: { level: RiskLevel | null; score?: number | null }) {
  return (
    <span className="badge" style={{ background: riskColor(level) }}>
      ความเสี่ยง{RISK_LABEL[level ?? "UNKNOWN"]}
      {score != null && ` (${score})`}
    </span>
  );
}
