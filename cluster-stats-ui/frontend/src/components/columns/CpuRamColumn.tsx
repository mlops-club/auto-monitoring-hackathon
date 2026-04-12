import type { CpuMetrics, RamMetrics } from "../../api/types";
import { HeatSquare } from "../primitives/HeatSquare";

interface Props {
  cpu: CpuMetrics;
  ram: RamMetrics;
  activeTab: "CPU" | "Swap";
}

function fmtRam(totalBytes: number | null): string {
  if (totalBytes == null) return "—";
  if (totalBytes >= 1e12) return `${(totalBytes / 1e12).toFixed(1)} TB`;
  return `${(totalBytes / 1e9).toFixed(1)} GB`;
}

export function CpuRamColumn({ cpu, ram, activeTab }: Props) {
  return (
    <td>
      <div className="sq-row" data-testid="cpuram-column">
        {activeTab === "CPU" ? (
          <>
            {cpu.cores != null && <span className="core-count">{cpu.cores}c</span>}
            <HeatSquare
              value={cpu.util ?? 0}
              tooltip={{
                title: "CPU",
                rows: [
                  ...(cpu.model ? [{ label: "Model", value: cpu.model }] : []),
                  ...(cpu.cores != null ? [{ label: "Cores", value: String(cpu.cores) }] : []),
                  { label: "Avg Util", value: `${cpu.util?.toFixed(1) ?? "—"}%` },
                ],
              }}
            />
            <HeatSquare
              value={ram.used ?? 0}
              tooltip={{
                title: "RAM",
                rows: [
                  { label: "Used", value: `${ram.used_gb ?? "—"} GB / ${fmtRam(ram.total_bytes)}` },
                  { label: "Util", value: `${ram.used?.toFixed(1) ?? "—"}%` },
                  { label: "Swap", value: `${ram.swap?.toFixed(1) ?? "—"}%` },
                ],
              }}
            />
          </>
        ) : (
          <>
            <HeatSquare
              value={ram.swap ?? 0}
              tooltip={{
                title: "Swap",
                rows: [
                  { label: "Usage", value: `${ram.swap?.toFixed(1) ?? "—"}%` },
                ],
              }}
              thresholds={[5, 20]}
            />
          </>
        )}
      </div>
    </td>
  );
}
