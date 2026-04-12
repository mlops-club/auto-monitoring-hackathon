import type { DiskMetrics } from "../../api/types";
import { HeatSquare } from "../primitives/HeatSquare";

interface Props {
  disks: DiskMetrics[];
  activeTab: "Space" | "IOPS" | "Tput";
}

function fmtTput(bytesPerSec: number | null): string {
  if (bytesPerSec == null) return "—";
  if (bytesPerSec >= 1e9) return `${(bytesPerSec / 1e9).toFixed(1)} GB/s`;
  if (bytesPerSec >= 1e6) return `${(bytesPerSec / 1e6).toFixed(1)} MB/s`;
  if (bytesPerSec >= 1e3) return `${(bytesPerSec / 1e3).toFixed(1)} KB/s`;
  return `${bytesPerSec.toFixed(0)} B/s`;
}

function fmtSize(bytes: number): string {
  const gib = bytes / (1024 ** 3);
  if (gib >= 1024) return `${(gib / 1024).toFixed(1)} TiB`;
  return `${gib.toFixed(1)} GiB`;
}

function diskUsageLabel(d: DiskMetrics): string {
  if (d.size_bytes == null || d.free == null) return "—";
  const usedPct = 100 - d.free;
  const usedBytes = d.size_bytes * (usedPct / 100);
  return `${fmtSize(usedBytes)} / ${fmtSize(d.size_bytes)}`;
}

export function DiskColumn({ disks, activeTab }: Props) {
  const visible = disks.filter((d) => {
    if (activeTab === "Space") return d.free != null;
    return d.iops != null || d.tput_bytes != null;
  });

  return (
    <td>
      <div className="sq-row" data-testid="disk-column">
        {visible.map((d) => {
          switch (activeTab) {
            case "Space": {
              const used = d.free != null ? 100 - d.free : 0;
              return (
                <HeatSquare
                  key={d.dev}
                  value={used}
                  tooltip={{
                    title: d.dev,
                    rows: [
                      { label: "Used", value: diskUsageLabel(d) },
                      { label: "Util", value: `${used.toFixed(1)}%` },
                      { label: "Free", value: `${d.free?.toFixed(1) ?? "—"}%` },
                    ],
                  }}
                />
              );
            }
            case "IOPS": {
              const pct = d.iops != null ? Math.min((d.iops / 200) * 100, 100) : 0;
              return (
                <HeatSquare
                  key={d.dev}
                  value={pct}
                  tooltip={{
                    title: d.dev,
                    rows: [
                      { label: "IOPS", value: d.iops?.toFixed(1) ?? "—" },
                      { label: "Tput", value: fmtTput(d.tput_bytes) },
                    ],
                  }}
                />
              );
            }
            case "Tput": {
              const pct = d.tput_bytes != null ? Math.min((d.tput_bytes / 1e8) * 100, 100) : 0;
              return (
                <HeatSquare
                  key={d.dev}
                  value={pct}
                  tooltip={{
                    title: d.dev,
                    rows: [
                      { label: "Tput", value: fmtTput(d.tput_bytes) },
                      { label: "IOPS", value: d.iops?.toFixed(1) ?? "—" },
                    ],
                  }}
                />
              );
            }
          }
        })}
      </div>
    </td>
  );
}
