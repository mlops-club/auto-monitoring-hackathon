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
      cpu: { util: 35, cores: 2, model: "Intel Xeon Platinum 8259CL" },
      ram: { used: 42, total: "8 GB", usedGb: 3.4, swap: 0, psi: 0.1 },
      disks: [
        { dev: "nvme0n1", free: 72, iops: 150, maxIops: 3000, tput: 0.12, maxTput: 0.25, totalTB: 0.02 },
      ],
      nics: [
        { dev: "eth0", bw: 18, drops: 0, tx: 0.5, rx: 1.2 },
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
      cpu: { util: 78, cores: 2, model: "Intel Xeon Platinum 8259CL" },
      ram: { used: 85, total: "8 GB", usedGb: 6.8, swap: 5, psi: 3.2 },
      disks: [
        { dev: "nvme0n1", free: 15, iops: 2800, maxIops: 3000, tput: 0.22, maxTput: 0.25, totalTB: 0.02 },
        { dev: "nvme1n1", free: 55, iops: 400, maxIops: 3000, tput: 0.05, maxTput: 0.25, totalTB: 0.02 },
      ],
      nics: [
        { dev: "eth0", bw: 65, drops: 42, tx: 3.2, rx: 4.1 },
        { dev: "eth1", bw: 30, drops: 0, tx: 1.0, rx: 0.8 },
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
      cpu: { util: 97, cores: 2, model: "Intel Xeon Platinum 8259CL" },
      ram: { used: 94, total: "8 GB", usedGb: 7.5, swap: 18, psi: 22.0 },
      disks: [
        { dev: "nvme0n1", free: 3, iops: 2950, maxIops: 3000, tput: 0.24, maxTput: 0.25, totalTB: 0.02 },
      ],
      nics: [
        { dev: "eth0", bw: 92, drops: 1580, tx: 8.5, rx: 9.2 },
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
  const data: [number, number][] = [];
  for (let i = 59; i >= 0; i--) {
    data.push([now - i * 60, Math.random() * 100]);
  }
  return { metric, data };
}
