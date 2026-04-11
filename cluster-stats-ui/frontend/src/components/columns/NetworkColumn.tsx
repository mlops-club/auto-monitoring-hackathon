import type { NicInfo } from "../../api/types";
import { HeatSquare } from "../primitives/HeatSquare";

interface Props {
  nics: NicInfo[];
  activeTab: "BW" | "Drops";
}

function dropSeverity(drops: number): number {
  if (drops > 500) return 100;
  if (drops > 50) return 60;
  if (drops > 0) return 30;
  return 0;
}

export function NetworkColumn({ nics, activeTab }: Props) {
  return (
    <td>
      <div className="sq-row" data-testid="network-column">
        {nics.map((n) => {
          switch (activeTab) {
            case "BW":
              return (
                <HeatSquare
                  key={n.dev}
                  value={n.bw}
                  tooltip={`${n.dev}\nBW: ${n.bw}%\nTX: ${n.tx} Gb/s\nRX: ${n.rx} Gb/s`}
                />
              );
            case "Drops":
              return (
                <HeatSquare
                  key={n.dev}
                  value={dropSeverity(n.drops)}
                  tooltip={`${n.dev}\nDrops: ${n.drops.toLocaleString()}`}
                  thresholds={[25, 65]}
                />
              );
          }
        })}
      </div>
    </td>
  );
}
