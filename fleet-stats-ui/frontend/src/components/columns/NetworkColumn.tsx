import type { NicMetrics } from "../../api/types";
import { HeatSquare } from "../primitives/HeatSquare";

interface Props {
  nics: NicMetrics[];
  activeTab: "BW" | "Drops";
}

function isPhysicalNic(dev: string): boolean {
  if (dev === "lo") return false;
  if (dev.startsWith("eni")) return false;
  if (dev.startsWith("veth")) return false;
  if (dev.startsWith("docker")) return false;
  if (dev.startsWith("br-")) return false;
  if (dev.startsWith("cali")) return false;
  return true;
}

function fmtRate(bytesPerSec: number | null): string {
  if (bytesPerSec == null) return "—";
  const bps = bytesPerSec * 8;
  if (bps >= 1e9) return `${(bps / 1e9).toFixed(2)} Gbps`;
  if (bps >= 1e6) return `${(bps / 1e6).toFixed(1)} Mbps`;
  if (bps >= 1e3) return `${(bps / 1e3).toFixed(0)} Kbps`;
  return `${bps.toFixed(0)} bps`;
}

function bwPercent(nic: NicMetrics): number {
  if (nic.bw_bytes == null) return 0;
  if (nic.speed_bytes != null && nic.speed_bytes > 0) {
    return (nic.bw_bytes / nic.speed_bytes) * 100;
  }
  return Math.min((nic.bw_bytes / 1250000000) * 100, 100);
}

function dropSeverity(drops: number | null): number {
  if (drops == null || drops === 0) return 0;
  if (drops > 500) return 100;
  if (drops > 50) return 60;
  return 30;
}

export function NetworkColumn({ nics, activeTab }: Props) {
  const visible = nics.filter((n) => isPhysicalNic(n.dev));

  return (
    <td>
      <div className="sq-row" data-testid="network-column">
        {visible.map((n) => {
          const pct = bwPercent(n);
          switch (activeTab) {
            case "BW":
              return (
                <HeatSquare
                  key={n.dev}
                  value={pct}
                  tooltip={{
                    title: n.dev,
                    rows: [
                      { label: "BW", value: `${fmtRate(n.bw_bytes)} (${pct.toFixed(1)}%)` },
                      { label: "Link", value: fmtRate(n.speed_bytes) },
                      { label: "Drops", value: `${n.drops?.toFixed(1) ?? "—"}/s` },
                    ],
                  }}
                />
              );
            case "Drops":
              return (
                <HeatSquare
                  key={n.dev}
                  value={dropSeverity(n.drops)}
                  tooltip={{
                    title: n.dev,
                    rows: [
                      { label: "Drops", value: `${n.drops?.toFixed(1) ?? "—"}/s` },
                      { label: "BW", value: fmtRate(n.bw_bytes) },
                    ],
                  }}
                  thresholds={[25, 65]}
                />
              );
          }
        })}
      </div>
    </td>
  );
}
