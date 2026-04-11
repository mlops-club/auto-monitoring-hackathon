import type { CpuInfo, RamInfo } from "../../api/types";
import { HeatSquare } from "../primitives/HeatSquare";

interface Props {
  cpu: CpuInfo;
  ram: RamInfo;
  activeTab: "CPU" | "Swap";
}

export function CpuRamColumn({ cpu, ram, activeTab }: Props) {
  return (
    <td>
      <div className="sq-row" data-testid="cpuram-column">
        {activeTab === "CPU" ? (
          <>
            <span className="core-count">{cpu.cores}c</span>
            <HeatSquare
              value={cpu.util}
              tooltip={`CPU\n${cpu.model} (${cpu.cores} cores)\nAvg Util: ${cpu.util}%`}
            />
            <HeatSquare
              value={ram.used}
              tooltip={`RAM\n${ram.usedGb} GB / ${ram.total} (${ram.used}%)\nSwap: ${ram.swap}%\nPSI: ${ram.psi}%`}
            />
          </>
        ) : (
          <>
            <HeatSquare
              value={ram.swap}
              tooltip={`Swap\n${ram.swap}%\nPSI: ${ram.psi}%`}
              thresholds={[5, 20]}
            />
            <HeatSquare
              value={ram.psi > 10 ? 80 : ram.psi > 2 ? 40 : ram.psi > 0 ? 15 : 0}
              tooltip={`PSI (Pressure Stall)\n${ram.psi}%`}
              thresholds={[20, 50]}
            />
          </>
        )}
      </div>
    </td>
  );
}
