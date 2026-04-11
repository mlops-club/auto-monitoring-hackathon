export interface NodesResponse {
  nodes: NodeSummary[];
}

export interface NodeSummary {
  id: string;
  ip: string;
  health: "ok" | "warn" | "crit";
  labels: Record<string, string>;
  cpu: CpuInfo;
  ram: RamInfo;
  disks: DiskInfo[];
  nics: NicInfo[];
  gpus: null;
  rdma: null;
  pcie: null;
}

export interface CpuInfo {
  util: number;
  cores: number;
  model: string;
}

export interface RamInfo {
  used: number;
  total: string;
  usedGb: number;
  swap: number;
  psi: number;
}

export interface DiskInfo {
  dev: string;
  free: number;
  iops: number;
  maxIops: number;
  tput: number;
  maxTput: number;
  totalTB: number;
}

export interface NicInfo {
  dev: string;
  bw: number;
  drops: number;
  tx: number;
  rx: number;
}

export interface NodeHistoryResponse {
  metric: string;
  data: [number, number][];
}

export interface NodeLabelsResponse {
  nodes: Record<string, Record<string, string>>;
}
