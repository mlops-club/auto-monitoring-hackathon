import type { DiskInfo } from "../../api/types";
import { HeatSquare } from "../primitives/HeatSquare";

interface Props {
  disks: DiskInfo[];
  activeTab: "Space" | "IOPS" | "Tput";
}

export function DiskColumn({ disks, activeTab }: Props) {
  return (
    <td>
      <div className="sq-row" data-testid="disk-column">
        {disks.map((d) => {
          const used = 100 - d.free;
          const usedTB = (used / 100 * d.totalTB).toFixed(1);
          const totalTB = d.totalTB.toFixed(1);
          switch (activeTab) {
            case "Space":
              return (
                <HeatSquare
                  key={d.dev}
                  value={used}
                  tooltip={`${d.dev} (${totalTB} TB)\nUsed: ${usedTB} / ${totalTB} TB (${used}%)\nFree: ${d.free}%\nIOPS: ${d.iops}\nTput: ${d.tput} GB/s`}
                />
              );
            case "IOPS":
              return (
                <HeatSquare
                  key={d.dev}
                  value={(d.iops / d.maxIops) * 100}
                  tooltip={`${d.dev}\nIOPS: ${d.iops} / ${d.maxIops}`}
                />
              );
            case "Tput":
              return (
                <HeatSquare
                  key={d.dev}
                  value={(d.tput / d.maxTput) * 100}
                  tooltip={`${d.dev}\nTput: ${d.tput} / ${d.maxTput} GB/s`}
                />
              );
          }
        })}
      </div>
    </td>
  );
}
