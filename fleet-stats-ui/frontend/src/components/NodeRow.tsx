import type { NodeMetrics } from "../api/types";
import { NodeCell } from "./columns/NodeCell";
import { DiskColumn } from "./columns/DiskColumn";
import { NetworkColumn } from "./columns/NetworkColumn";
import { CpuRamColumn } from "./columns/CpuRamColumn";
import { GpuColumn } from "./columns/GpuColumn";
import { RdmaColumn } from "./columns/RdmaColumn";
import { PcieColumn } from "./columns/PcieColumn";

interface Props {
  node: NodeMetrics;
  diskTab: "Space" | "IOPS" | "Tput";
  netTab: "BW" | "Drops";
  cpuRamTab: "CPU" | "Swap";
  onSquareClick?: (nodeId: string, metric: string) => void;
}

export function NodeRow({ node, diskTab, netTab, cpuRamTab }: Props) {
  return (
    <tr data-testid="node-row">
      <NodeCell node={node} />
      <DiskColumn disks={node.disks} activeTab={diskTab} />
      <NetworkColumn nics={node.nics} activeTab={netTab} />
      <CpuRamColumn cpu={node.cpu} ram={node.ram} activeTab={cpuRamTab} />
      <GpuColumn gpus={node.gpus} />
      <RdmaColumn rdma={node.rdma} />
      <PcieColumn pcie={node.pcie} />
    </tr>
  );
}
