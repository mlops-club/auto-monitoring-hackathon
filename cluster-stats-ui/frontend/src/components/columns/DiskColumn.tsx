import type { DiskMetrics } from "../../api/types";
import { HeatSquare } from "../primitives/HeatSquare";

interface Props {
  disks: DiskMetrics[];
  activeTab: "Space" | "IOPS" | "Tput";
}

function fmt(bytes: number | null): string {
  if (bytes == null) return "—";
  if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(1)} GB/s`;
  if (bytes >= 1e6) return `${(bytes / 1e6).toFixed(1)} MB/s`;
  return `${(bytes / 1e3).toFixed(1)} KB/s`;
}

export function DiskColumn({ disks, activeTab }: Props) {
  return (
    <td>
      <div className="sq-row" data-testid="disk-column">
        {disks.map((d) => {
          const used = d.free != null ? 100 - d.free : 0;
          switch (activeTab) {
            case "Space":
              return (
                <HeatSquare
                  key={d.dev}
                  value={used}
                  tooltip={`${d.dev}\nUsed: ${used.toFixed(0)}%\nFree: ${d.free?.toFixed(0) ?? "—"}%`}
                />
              );
            case "IOPS":
              return (
                <HeatSquare
                  key={d.dev}
                  value={d.iops != null ? Math.min(d.iops / 50, 100) : 0}
                  tooltip={`${d.dev}\nIOPS: ${d.iops?.toFixed(0) ?? "—"}`}
                />
              );
            case "Tput":
              return (
                <HeatSquare
                  key={d.dev}
                  value={d.tput_bytes != null ? Math.min(d.tput_bytes / 1e8, 100) : 0}
                  tooltip={`${d.dev}\nTput: ${fmt(d.tput_bytes)}`}
                />
              );
          }
        })}
      </div>
    </td>
  );
}
