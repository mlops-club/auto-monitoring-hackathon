import type { NicMetrics } from "../../api/types";
import { HeatSquare } from "../primitives/HeatSquare";

interface Props {
  nics: NicMetrics[];
  activeTab: "BW" | "Drops";
}

function bwPercent(nic: NicMetrics): number {
  if (nic.bw_bytes == null) return 0;
  if (nic.speed_bytes != null && nic.speed_bytes > 0) {
    return (nic.bw_bytes / nic.speed_bytes) * 100;
  }
  // No link speed available — use 1 Gbps as reference
  return Math.min((nic.bw_bytes / 125000000) * 100, 100);
}

function fmtBytes(b: number | null): string {
  if (b == null) return "—";
  if (b >= 1e9) return `${(b / 1e9).toFixed(1)} Gb/s`;
  if (b >= 1e6) return `${(b / 1e6).toFixed(1)} Mb/s`;
  return `${(b / 1e3).toFixed(1)} Kb/s`;
}

function dropSeverity(drops: number | null): number {
  if (drops == null || drops === 0) return 0;
  if (drops > 500) return 100;
  if (drops > 50) return 60;
  return 30;
}

export function NetworkColumn({ nics, activeTab }: Props) {
  return (
    <td>
      <div className="sq-row" data-testid="network-column">
        {nics.map((n) => {
          switch (activeTab) {
            case "BW": {
              const pct = bwPercent(n);
              return (
                <HeatSquare
                  key={n.dev}
                  value={pct}
                  tooltip={`${n.dev}\nBW: ${pct.toFixed(0)}%\nRate: ${fmtBytes(n.bw_bytes)}\nSpeed: ${fmtBytes(n.speed_bytes)}`}
                />
              );
            }
            case "Drops":
              return (
                <HeatSquare
                  key={n.dev}
                  value={dropSeverity(n.drops)}
                  tooltip={`${n.dev}\nDrops: ${n.drops?.toFixed(1) ?? "—"}/s`}
                  thresholds={[25, 65]}
                />
              );
          }
        })}
      </div>
    </td>
  );
}
