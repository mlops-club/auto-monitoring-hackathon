export interface NodesResponse {
  nodes: NodeMetrics[];
}

export interface NodeMetrics {
  id: string;
  ip: string | null;
  health: string;
  labels: Record<string, string>;
  cpu: CpuMetrics;
  ram: RamMetrics;
  disks: DiskMetrics[];
  nics: NicMetrics[];
  gpus: null;
  rdma: null;
  pcie: null;
}

export interface CpuMetrics {
  util: number | null;
  cores: number | null;
  model: string | null;
}

export interface RamMetrics {
  used: number | null;
  total_bytes: number | null;
  used_gb: number | null;
  swap: number | null;
}

export interface DiskMetrics {
  dev: string;
  free: number | null;
  size_bytes: number | null;
  iops: number | null;
  tput_bytes: number | null;
}

export interface NicMetrics {
  dev: string;
  bw_bytes: number | null;
  speed_bytes: number | null;
  drops: number | null;
}

export interface MetricSample {
  timestamp: number;
  value: number;
}

export interface NodeHistoryResponse {
  node: string;
  metric: string;
  samples: MetricSample[];
}

export interface NodeLabelsResponse {
  nodes: Record<string, Record<string, string>>;
}
