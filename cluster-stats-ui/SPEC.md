# Cluster Stats UI — Spec

## Overview

A React dashboard that displays real-time node-exporter metrics from a Kubernetes cluster. Data is fetched from a FastAPI backend that queries Mimir.

## Data sources

- `GET /api/nodes` — current metrics per node (CPU, RAM, disk, network)
- `GET /api/labels` — K8s node labels for filtering and grouping
- `GET /api/nodes/{node}/history` — time-series for a single metric

## Layout

A single full-width page: header, filter/group bar, then a table.

### Header

- Title: "Cluster Overview"
- Subtitle: node count (updates with filters)
- No health legend, no color-coded status indicators

### Filter & group bar

- Text input with autocomplete dropdown listing all `key=value` label pairs across nodes
- Active filters shown as removable chips
- "Group by" dropdown listing all label keys; selecting one sections the table by that label's values
- Each group section has a header row showing the value and node count

### Table

Seven columns: **Node**, **Disks**, **Network**, **CPU / RAM**, **GPU**, **RDMA**, **PCIe**.

Columns with multiple metrics have a tab bar in the header to switch the displayed metric globally (all rows update together).

| Column | Tabs | Notes |
|--------|------|-------|
| Node | — | Hostname pill, IP address. Labels shown in tooltip on hover. |
| Disks | Devices / Partitions | Two views of disk data — see "Disk column detail" below. |
| Network | BW / Drops | Only physical NICs (eth*). Filter out eni*, lo, veth*, docker*, br-*, cali*. |
| CPU / RAM | CPU / Swap | CPU tab: optional core count label + CPU square + RAM square. Swap tab: swap square. |
| GPU | — | Stubbed: "No data" placeholder. |
| RDMA | — | Stubbed: "No data" placeholder. |
| PCIe | — | Stubbed: "No data" placeholder. |

### Disk column detail

The Disk column has two tabs representing two different views of storage, mirroring what `lsblk` shows on a Linux machine.

**Devices tab** — physical block devices (e.g. `nvme0n1`, `nvme1n1`). On AWS these correspond to EBS volumes or instance store NVMe drives. One square per device.

- Data source: `node_disk_*` metrics (keyed by `device`, no `mountpoint`)
- Tooltip: device name / IOPS / Throughput (KB/MB/GB per second)
- Fill value: IOPS relative to scale (currently 200 IOPS = 100%)
- These are the entries that have IOPS and throughput data

**Partitions tab** — mounted filesystems (e.g. `/dev/nvme0n1p1` mounted at `/`). One square per partition.

- Data source: `node_filesystem_*` metrics (keyed by `device` + `mountpoint` + `fstype`)
- Tooltip: device name / Mount path / Used (X GiB / Y GiB) / Util % / Free %
- Fill value: disk usage percent (100 - free%)
- Filter out: `tmpfs`, `overlay` fstypes
- These are the entries that have free%, size_bytes, and mount path data
- IOPS does **not** apply to partitions (different metric family)

**Why two tabs**: node-exporter exposes block device I/O (`node_disk_*`) and filesystem usage (`node_filesystem_*`) as separate metric families with different label sets. Block devices have IOPS/throughput but no mount path or usage%. Filesystems have usage/free/mount but no IOPS. They cannot be joined reliably (a device can have multiple partitions, or none).

### Rows

- No alternating row colors
- No hover highlight
- No health badges or color-coded status indicators on rows

## Visual: battery squares

Each metric is rendered as a 13x13px "battery" square that fills from the bottom proportional to the value.

- Fill color: green (< low threshold), yellow (>= low, < high), red (>= high)
- Default thresholds: 40%, 70%
- Overrides: Network drops [25, 65], Swap [5, 20]
- On hover: scale 1.5x with shadow

All metric cells use the same square component. No special gauge or bar variants.

## Tooltips

Appear above the square on hover. Structured as:

- **Title** (bold, white, with a subtle divider below): device name or metric name
- **Rows**: label (muted gray, left-aligned) and value (white monospace, right-aligned)

Must not be clipped by the square's container.

### Tooltip content by column

**Disk — Devices tab**: device name / IOPS / Throughput (formatted KB/MB/GB per second)

**Disk — Partitions tab**: device name / Mount path / Used (X GiB / Y GiB or TiB) / Util % / Free %

**Network — BW**: device name / BW in Gbps/Mbps with % / Link speed / Drops per second

**Network — Drops**: device name / Drops per second / BW

**CPU**: "CPU" / Model (if available) / Cores (if available) / Avg Util %

**RAM**: "RAM" / Used GB of Total / Util % / Swap %

**Swap**: "Swap" / Usage %

**Node cell labels tooltip**: plain text, one `key=value` per line

## Backend API contract

### `GET /api/nodes` → `NodesResponse`

```
NodesResponse { nodes: NodeMetrics[] }

NodeMetrics {
  id: string              — K8s node name
  ip: string | null       — internal IP (from instance label)
  health: string          — "ok" | "warn" | "crit" | "unknown" (computed from thresholds)
  labels: Record<string, string>  — K8s node labels
  cpu: CpuMetrics
  ram: RamMetrics
  disks: DiskMetrics[]
  nics: NicMetrics[]
  gpus: null              — stubbed
  rdma: null              — stubbed
  pcie: null              — stubbed
}

CpuMetrics { util: float?, cores: int?, model: string? }

RamMetrics { used: float?, total_bytes: int?, used_gb: float?, swap: float? }

DiskMetrics { dev: string, free: float?, size_bytes: int?, iops: float?, tput_bytes: float? }

NicMetrics { dev: string, bw_bytes: float?, speed_bytes: float?, drops: float? }
```

### `GET /api/nodes/{node}/history` → `NodeHistoryResponse`

```
NodeHistoryResponse { node: string, metric: string, samples: MetricSample[] }
MetricSample { timestamp: float, value: float }
```

Query params: `metric` (required), `start` (epoch, default 15m ago), `end` (epoch, default now), `step` (default "60s").

Valid metric keys: `cpu`, `ram`, `swap`, `disk_free`, `disk_iops`, `disk_tput`, `net_bw`, `net_drops`.

### `GET /api/labels` → `NodeLabelsResponse`

```
NodeLabelsResponse { nodes: Record<string, Record<string, string>> }
```

### PromQL queries (backend → Mimir)

| Key | PromQL | Groups by |
|-----|--------|-----------|
| cpu_util | `100 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100` | instance |
| ram_used_pct | `100 * (1 - MemAvailable / MemTotal)` | instance |
| ram_total | `node_memory_MemTotal_bytes` | instance |
| swap_used_pct | `100 * (1 - SwapFree / SwapTotal)` | instance |
| disk_free | `100 * avail / size` (fstype !~ tmpfs\|overlay) | instance, device, mountpoint |
| disk_size | `node_filesystem_size_bytes` (fstype !~ tmpfs\|overlay) | instance, device, mountpoint |
| disk_iops | `rate(reads) + rate(writes)` | instance, device |
| disk_tput | `rate(read_bytes) + rate(written_bytes)` | instance, device |
| net_bw | `rate(rx_bytes) + rate(tx_bytes)` (excl lo, veth, docker, br) | instance, device |
| net_speed | `node_network_speed_bytes` | instance, device |
| net_drops | `rate(rx_drop) + rate(tx_drop)` | instance, device |

### Unit formatting conventions

| Domain | Format |
|--------|--------|
| Disk size | GiB (< 1024 GiB) or TiB (>= 1024 GiB), 1 decimal |
| Disk throughput | B/s → KB/s → MB/s → GB/s, 1 decimal |
| Network rate | bps → Kbps → Mbps → Gbps (×8 from bytes), 1-2 decimals |
| Percentages | 1 decimal |

## States

- **Loading**: centered "Loading..." text
- **Error**: banner with error message (e.g. "fetchNodes failed: 503")
- **Empty**: "No nodes match the current filters."
- **No data columns**: grayed dashed square with "No data" aria-label

## Testing

Vitest + React Testing Library + jsdom. All tests fully isolated — no network, no backend, no Docker. API client mocked via `vi.mock()`. Mock data provides 3 nodes with varying health levels.
