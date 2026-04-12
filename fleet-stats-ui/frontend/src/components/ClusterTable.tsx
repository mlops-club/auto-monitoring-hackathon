import { useState, useMemo } from "react";
import type { NodeMetrics } from "../api/types";
import { TabBar } from "./primitives/TabBar";
import { NodeRow } from "./NodeRow";

const COL_COUNT = 7;

interface Props {
  nodes: NodeMetrics[];
  groupBy: string | null;
}

function groupNodes(nodes: NodeMetrics[], key: string): Map<string, NodeMetrics[]> {
  const groups = new Map<string, NodeMetrics[]>();
  for (const node of nodes) {
    const val = node.labels[key] ?? "unknown";
    const list = groups.get(val);
    if (list) list.push(node);
    else groups.set(val, [node]);
  }
  // Sort by group size descending
  return new Map([...groups.entries()].sort((a, b) => b[1].length - a[1].length));
}

export function ClusterTable({ nodes, groupBy }: Props) {
  const [diskTab, setDiskTab] = useState<"Space" | "IOPS" | "Tput">("Space");
  const [netTab, setNetTab] = useState<"BW" | "Drops">("BW");
  const [cpuRamTab, setCpuRamTab] = useState<"CPU" | "Swap">("CPU");

  const groups = useMemo(
    () => groupBy ? groupNodes(nodes, groupBy) : null,
    [nodes, groupBy],
  );

  const renderRow = (node: NodeMetrics) => (
    <NodeRow key={node.id} node={node} diskTab={diskTab} netTab={netTab} cpuRamTab={cpuRamTab} />
  );

  return (
    <table className="cluster-table" data-testid="cluster-table">
      <thead>
        <tr>
          <th>
            <span className="col-label">Node</span>
          </th>
          <th>
            <span className="col-label">Disks</span>
            <TabBar tabs={["Space", "IOPS", "Tput"]} active={diskTab} onChange={(t) => setDiskTab(t as typeof diskTab)} />
          </th>
          <th>
            <span className="col-label">Network</span>
            <TabBar tabs={["BW", "Drops"]} active={netTab} onChange={(t) => setNetTab(t as typeof netTab)} />
          </th>
          <th>
            <span className="col-label">CPU / RAM</span>
            <TabBar tabs={["CPU", "Swap"]} active={cpuRamTab} onChange={(t) => setCpuRamTab(t as typeof cpuRamTab)} />
          </th>
          <th><span className="col-label">GPU</span></th>
          <th><span className="col-label">RDMA</span></th>
          <th><span className="col-label">PCIe</span></th>
        </tr>
      </thead>
      <tbody>
        {groups ? (
          [...groups.entries()].map(([groupKey, groupNodes]) => (
            <GroupSection key={groupKey} label={groupKey} count={groupNodes.length}>
              {groupNodes.map(renderRow)}
            </GroupSection>
          ))
        ) : (
          nodes.map(renderRow)
        )}
      </tbody>
    </table>
  );
}

function GroupSection({ label, count, children }: { label: string; count: number; children: React.ReactNode }) {
  return (
    <>
      <tr className="group-header-row" data-testid="group-header">
        <td colSpan={COL_COUNT}>
          {label}
          <span className="group-count">{count} node{count !== 1 ? "s" : ""}</span>
        </td>
      </tr>
      {children}
    </>
  );
}
