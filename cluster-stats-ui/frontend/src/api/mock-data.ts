import type { NodesResponse, NodeLabelsResponse, NodeHistoryResponse } from "./types";

export const MOCK_NODES: NodesResponse = {
  nodes: [
    {
      id: "ip-10-0-1-45.us-west-2.compute.internal",
      ip: "10.0.1.45",
      health: "ok",
      labels: {
        "kubernetes.io/os": "linux",
        "node.kubernetes.io/instance-type": "m5.large",
        "topology.kubernetes.io/zone": "us-west-2a",
      },
      cpu: { util: 35, cores: null, model: null },
      ram: { used: 42, total_bytes: 8e9, used_gb: 3.4, swap: 0 },
      disks: [
        { dev: "nvme0n1", free: 72, iops: 150, tput_bytes: 125000000 },
      ],
      nics: [
        { dev: "eth0", bw_bytes: 22500000, speed_bytes: 125000000, drops: 0 },
      ],
      gpus: null,
      rdma: null,
      pcie: null,
    },
    {
      id: "ip-10-0-2-88.us-west-2.compute.internal",
      ip: "10.0.2.88",
      health: "warn",
      labels: {
        "kubernetes.io/os": "linux",
        "node.kubernetes.io/instance-type": "m5.large",
        "topology.kubernetes.io/zone": "us-west-2b",
      },
      cpu: { util: 78, cores: null, model: null },
      ram: { used: 85, total_bytes: 8e9, used_gb: 6.8, swap: 5 },
      disks: [
        { dev: "nvme0n1", free: 15, iops: 2800, tput_bytes: 220000000 },
        { dev: "nvme1n1", free: 55, iops: 400, tput_bytes: 50000000 },
      ],
      nics: [
        { dev: "eth0", bw_bytes: 81250000, speed_bytes: 125000000, drops: 42 },
        { dev: "eth1", bw_bytes: 37500000, speed_bytes: 125000000, drops: 0 },
      ],
      gpus: null,
      rdma: null,
      pcie: null,
    },
    {
      id: "ip-10-0-3-12.us-west-2.compute.internal",
      ip: "10.0.3.12",
      health: "crit",
      labels: {
        "kubernetes.io/os": "linux",
        "node.kubernetes.io/instance-type": "m5.large",
        "topology.kubernetes.io/zone": "us-west-2a",
      },
      cpu: { util: 97, cores: null, model: null },
      ram: { used: 94, total_bytes: 8e9, used_gb: 7.5, swap: 18 },
      disks: [
        { dev: "nvme0n1", free: 3, iops: 2950, tput_bytes: 240000000 },
      ],
      nics: [
        { dev: "eth0", bw_bytes: 115000000, speed_bytes: 125000000, drops: 1580 },
      ],
      gpus: null,
      rdma: null,
      pcie: null,
    },
  ],
};

export const MOCK_LABELS: NodeLabelsResponse = {
  nodes: {
    "ip-10-0-1-45.us-west-2.compute.internal": MOCK_NODES.nodes[0].labels,
    "ip-10-0-2-88.us-west-2.compute.internal": MOCK_NODES.nodes[1].labels,
    "ip-10-0-3-12.us-west-2.compute.internal": MOCK_NODES.nodes[2].labels,
  },
};

export function mockNodeHistory(metric: string): NodeHistoryResponse {
  const now = Math.floor(Date.now() / 1000);
  const samples = [];
  for (let i = 59; i >= 0; i--) {
    samples.push({ timestamp: now - i * 60, value: Math.random() * 100 });
  }
  return { node: "mock", metric, samples };
}
