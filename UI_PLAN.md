# UI Plan: Cluster Monitoring Dashboard

## Progress Tracker

| Phase | Description | Status | PR |
|-------|-------------|--------|-----|
| **0** | Verify existing node-exporter metrics reach Mimir | Not started | — |
| **1** | K8s labels via API + metric→node mapping in Alloy | **Done** | [#13](https://github.com/mlops-club/auto-monitoring-hackathon/pull/13) |
| **1.1** | Add `node` relabel rule to Alloy (node_exporter + cAdvisor) | **Done** | #13 |
| **1.2** | FastAPI `GET /api/labels` endpoint (K8s node labels, 60s cache) | **Done** | #13 |
| **1.3** | RBAC ClusterRole/Binding for backend ServiceAccount | **Done** | #13 |
| **1.4** | Deploy & verify relabel + labels endpoint | Partially done (endpoint verified locally; Alloy redeploy pending) | #13 |
| **2** | FastAPI backend — Mimir query endpoints (`/api/nodes`, `/api/nodes/{node}/history`) | **Done** | #16 |
| **3** | React UI — display real node-exporter metrics | **Planned** (see §3.1–3.8) | — |
| **4** | Mock DCGM exporter for GPU metrics | Not started | — |
| **5** | Docker-compose local development stack | Not started | — |
| **6** | Playwright end-to-end tests | Not started | — |

---

## Metric Gap Analysis

### What the vibe-coded UI (`docs/cluster-view.html`) displays

| Category | UI Tabs/Metrics | Prometheus Metric Source | Collected Today? |
|----------|----------------|--------------------------|------------------|
| **CPU** | Utilization (%) | `node_cpu_seconds_total` | ✅ node-exporter |
| **RAM** | Used (%), Used (GB), Total | `node_memory_MemTotal_bytes`, `node_memory_MemAvailable_bytes` | ✅ node-exporter |
| **RAM** | Swap (%), PSI (%) | `node_memory_SwapTotal_bytes`, `node_memory_SwapFree_bytes`, `node_pressure_memory_*` | ✅ node-exporter (swap); ⚠️ PSI requires kernel 4.20+ and `--collector.pressure` |
| **Disk** | Space used (%) | `node_filesystem_avail_bytes`, `node_filesystem_size_bytes` | ✅ node-exporter |
| **Disk** | IOPS | `node_disk_reads_completed_total`, `node_disk_writes_completed_total` | ✅ node-exporter |
| **Disk** | Throughput (GB/s) | `node_disk_read_bytes_total`, `node_disk_written_bytes_total` | ✅ node-exporter |
| **Network** | Bandwidth (%) | `node_network_receive_bytes_total`, `node_network_transmit_bytes_total`, `node_network_speed_bytes` | ✅ node-exporter |
| **Network** | Packet drops | `node_network_receive_drop_total`, `node_network_transmit_drop_total` | ✅ node-exporter |
| **K8s Labels** | Dropdown filters (region, zone, instance-type, gpu.product, etc.) | K8s API `GET /api/v1/nodes` | ✅ Always available (just needs RBAC) |
| **GPU** | Util, VRAM, Temp, Power | `DCGM_FI_DEV_GPU_UTIL`, `DCGM_FI_DEV_FB_USED`, `DCGM_FI_DEV_GPU_TEMP`, `DCGM_FI_DEV_POWER_USAGE` | ❌ No GPUs / no DCGM exporter |
| **GPU** | Job allocation | Scheduler API (not a metric) | ❌ N/A |
| **RDMA/IB** | BW, Congestion (ECN), Retries | InfiniBand exporter metrics | ❌ No IB hardware / no exporter |
| **PCIe** | Throughput, Saturation | No standard exporter | ❌ No exporter exists |

### Summary

- **Already flowing into Mimir**: CPU, RAM (incl. swap), disk (space + I/O), network (BW + drops)
- **K8s node labels**: Get directly from K8s API (`GET /api/v1/nodes`) — no kube-state-metrics needed
- **Missing — no hardware, must mock**: GPU (DCGM), RDMA/IB, PCIe
- **Metric→node mapping**: Need to add a `node` relabel rule in Alloy so metrics carry the K8s node name (currently only `instance=IP:port`). Then the backend can join metrics to K8s API labels on node name.

---

## Phase 0: Verify existing node-exporter metrics reach Mimir

**Goal**: Confirm the metrics we *think* are collected are actually queryable in Mimir before writing any UI code.

### Steps

1. Port-forward Mimir:
   ```bash
   kubectl port-forward -n monitoring svc/mimir-gateway 8080:80
   ```

2. Query each metric family and confirm results come back:
   ```bash
   # CPU
   curl -s 'http://localhost:8080/prometheus/api/v1/query?query=node_cpu_seconds_total' | jq '.data.result | length'

   # Memory
   curl -s 'http://localhost:8080/prometheus/api/v1/query?query=node_memory_MemTotal_bytes' | jq '.data.result | length'

   # Swap
   curl -s 'http://localhost:8080/prometheus/api/v1/query?query=node_memory_SwapTotal_bytes' | jq '.data.result | length'

   # Disk space
   curl -s 'http://localhost:8080/prometheus/api/v1/query?query=node_filesystem_avail_bytes' | jq '.data.result | length'

   # Disk I/O
   curl -s 'http://localhost:8080/prometheus/api/v1/query?query=node_disk_reads_completed_total' | jq '.data.result | length'
   curl -s 'http://localhost:8080/prometheus/api/v1/query?query=node_disk_read_bytes_total' | jq '.data.result | length'

   # Network
   curl -s 'http://localhost:8080/prometheus/api/v1/query?query=node_network_receive_bytes_total' | jq '.data.result | length'
   curl -s 'http://localhost:8080/prometheus/api/v1/query?query=node_network_speed_bytes' | jq '.data.result | length'
   curl -s 'http://localhost:8080/prometheus/api/v1/query?query=node_network_receive_drop_total' | jq '.data.result | length'
   ```

3. Verify label cardinality — check that `instance` labels allow us to distinguish nodes:
   ```bash
   curl -s 'http://localhost:8080/prometheus/api/v1/query?query=node_uname_info' | jq '.data.result[].metric'
   ```

4. **PASS criteria**: Every query above returns `result | length > 0`. Record the actual label sets (instance, job, device, etc.) — these will inform the PromQL in the backend.

---

## Phase 1: K8s labels via API + metric→node mapping in Alloy

**Goal**: Enable the UI to filter/group nodes by K8s labels AND join those labels to metric streams.

### Why not kube-state-metrics?

K8s node labels don't need to flow through the metrics pipeline. The K8s API is the source of truth and is always available. The FastAPI backend can query it directly — no extra deployment needed. We just need to solve the **join problem**: metrics have `instance=10.0.1.45:9100` but the K8s API identifies nodes by name.

### 1.1 Add `node` relabel rule to Alloy

Currently, node-exporter metrics only carry `instance=IP:port`. Add a relabel rule so they also carry the K8s node name, which enables joining metrics to K8s API labels.

In `infra/k8s/helm/values/alloy.yaml`, update the `discovery.relabel "node_exporter"` block:
```river
discovery.relabel "node_exporter" {
  targets = discovery.kubernetes.endpoints.targets
  rule {
    source_labels = ["__meta_kubernetes_service_name"]
    regex         = "node-exporter"
    action        = "keep"
  }
  rule {
    source_labels = ["__meta_kubernetes_endpoint_port_name"]
    regex         = "metrics"
    action        = "keep"
  }
  // NEW: attach K8s node name to all scraped metrics
  rule {
    source_labels = ["__meta_kubernetes_pod_node_name"]
    target_label  = "node"
  }
}
```

Similarly for the cAdvisor scrape — add `node` from `__meta_kubernetes_node_name`:
```river
discovery.relabel "cadvisor" {
  targets = discovery.kubernetes.nodes.targets
  rule {
    replacement  = "/metrics/cadvisor"
    target_label = "__metrics_path__"
  }
  // NEW: attach K8s node name
  rule {
    source_labels = ["__meta_kubernetes_node_name"]
    target_label  = "node"
  }
}
```

### 1.2 FastAPI: query K8s API for labels

The backend calls `GET /api/v1/nodes` using the `kubernetes` Python client. When running in-cluster, it uses the pod's ServiceAccount token automatically. When running locally, it uses `~/.kube/config`.

```python
from kubernetes import client, config

def get_node_labels() -> dict[str, dict[str, str]]:
    """Returns {node_name: {label_key: label_value, ...}}"""
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    v1 = client.CoreV1Api()
    nodes = v1.list_node()
    return {
        node.metadata.name: node.metadata.labels or {}
        for node in nodes.items
    }
```

Cache this with a TTL of ~60s since labels rarely change.

### 1.3 RBAC for the backend ServiceAccount

The backend pod needs a ServiceAccount with permission to list/get nodes:
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: node-reader
rules:
  - apiGroups: [""]
    resources: ["nodes"]
    verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: cs-backend-node-reader
subjects:
  - kind: ServiceAccount
    name: cs-backend
    namespace: monitoring
roleRef:
  kind: ClusterRole
  name: node-reader
  apiGroup: rbac.authorization.k8s.io
```

### 1.4 Deploy & verify

```bash
# Deploy Alloy with updated relabel rules
./infra/k8s/helm/deploy-monitoring.sh

# Wait ~60s for a scrape cycle, then verify node label appears on metrics
kubectl port-forward -n monitoring svc/mimir-gateway 8080:80
curl -s 'http://localhost:8080/prometheus/api/v1/query?query=node_cpu_seconds_total' | \
  jq '.data.result[0].metric | {instance, node, job}'
```

**PASS criteria**:
- Metrics now have a `node` label alongside `instance` (e.g., `"node": "ip-10-0-1-45.us-west-2.compute.internal"`)
- Backend `/api/labels` returns label keys/values that match `kubectl get nodes --show-labels`

---

## Phase 2: FastAPI backend — Mimir query endpoints

**Goal**: Add API routes that query Mimir and return the data shape the React UI expects.

### 2.1 Settings

Add to `cs_backend/settings.py`:
```python
mimir_url: str = "http://mimir:8080"  # overridable via env MIMIR_URL
```

### 2.2 Mimir client

Create `cs_backend/mimir.py` — a thin async wrapper around `httpx` that queries the Mimir Prometheus API (`/prometheus/api/v1/query` and `/prometheus/api/v1/query_range`).

### 2.3 API endpoints

| Endpoint | Purpose | PromQL queries |
|----------|---------|----------------|
| `GET /api/nodes` | List of nodes with current scalar metrics | See PromQL table below |
| `GET /api/nodes/{node}/history?metric=cpu&start=...&end=...` | Time-series for the metrics modal | `query_range` variants |
| `GET /api/labels` | Distinct K8s label keys + values for dropdowns | K8s API `GET /api/v1/nodes` (cached) |

### 2.4 PromQL query map (node-exporter metrics only)

These are the PromQL queries the backend will execute against Mimir:

| UI Field | PromQL (instant) |
|----------|-----------------|
| CPU util (%) | `100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)` |
| RAM used (%) | `100 * (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)` |
| RAM total (bytes) | `node_memory_MemTotal_bytes` |
| Swap used (%) | `100 * (1 - node_memory_SwapFree_bytes / node_memory_SwapTotal_bytes)` |
| Disk free (%) per device | `100 * node_filesystem_avail_bytes{fstype!~"tmpfs\|overlay"} / node_filesystem_size_bytes` |
| Disk IOPS per device | `rate(node_disk_reads_completed_total[5m]) + rate(node_disk_writes_completed_total[5m])` |
| Disk throughput (bytes/s) per device | `rate(node_disk_read_bytes_total[5m]) + rate(node_disk_written_bytes_total[5m])` |
| Net BW (bytes/s) per NIC | `rate(node_network_receive_bytes_total{device!~"lo\|veth.*\|docker.*\|br-.*"}[5m]) + rate(node_network_transmit_bytes_total{...}[5m])` |
| Net link speed (bytes/s) | `node_network_speed_bytes` |
| Net drops per NIC | `rate(node_network_receive_drop_total[5m]) + rate(node_network_transmit_drop_total[5m])` |
| K8s labels | K8s API `GET /api/v1/nodes` → extract `.metadata.labels` (cached 60s) |

### 2.5 Response schema

The backend transforms the PromQL results into the JSON shape the UI expects (matching `docs/cluster-view.html` DATA structure), with GPU/RDMA/PCIe fields set to `null` when no data source exists.

### 2.6 Verify backend

```bash
# Run backend locally, pointing at port-forwarded Mimir
MIMIR_URL=http://localhost:8080 uv run uvicorn cs_backend.app:create_app --factory --port 8000

# Test endpoints
curl -s http://localhost:8000/api/nodes | jq '.nodes | length'
curl -s http://localhost:8000/api/labels | jq 'keys'
curl -s 'http://localhost:8000/api/nodes/NODE_INSTANCE/history?metric=cpu&start=2024-01-01T00:00:00Z&end=2024-01-01T01:00:00Z' | jq '.data | length'
```

**PASS criteria**: `/api/nodes` returns ≥1 node with non-null `cpu.util`, `ram.used`, `disks[].free`, `nics[].bw`. GPU/RDMA/PCIe fields are `null`.

---

## Phase 3: React UI — display real node-exporter metrics

**Goal**: Port the HTML dashboard (`docs/cluster-view.html`) to React, wired to the FastAPI backend's `/api/nodes`, `/api/nodes/{node}/history`, and `/api/labels` endpoints. All node-exporter metrics should display live data; GPU/RDMA/PCIe columns are stubbed.

> **Dependency note**: Phase 2 (FastAPI Mimir query endpoints) is being built on a separate branch. Phase 3 work should be structured so it can be developed in parallel and reconciled afterward. Strategy: define a **TypeScript API client layer** with explicit types for the `/api/nodes` and `/api/nodes/{node}/history` response shapes, and use **mock data** in dev/test until Phase 2 lands. The reconciliation merge will wire the real endpoints through the same typed client.

---

### 3.1 Scope (node-exporter metrics only)

#### Implement (live data from backend)

| Column | Tabs | Visual | Data source |
|--------|------|--------|-------------|
| **Node** | — | Hostname pill, IP, health badge, K8s labels tooltip | `GET /api/nodes` → `id`, `ip`, `health`, `labels` |
| **Disks** | Space / IOPS / Tput | One battery square per `device` | `GET /api/nodes` → `disks[]` |
| **Network** | BW / Drops | One battery square per NIC | `GET /api/nodes` → `nics[]` |
| **CPU / RAM** | CPU / Swap | CPU heat square + RAM gauge | `GET /api/nodes` → `cpu`, `ram` |

#### Stub out (show "No data" / grayed squares)

- GPU column
- RDMA/IB column
- PCIe column

---

### 3.2 API contract & TypeScript types

Define these in `frontend/src/api/types.ts`. They mirror the backend response schemas from Phase 2 (§2.5) and the DATA shape in `docs/cluster-view.html`:

```typescript
// --- GET /api/nodes response ---
export interface NodesResponse {
  nodes: NodeSummary[];
}

export interface NodeSummary {
  id: string;           // K8s node name
  ip: string;           // internal IP
  health: "ok" | "warn" | "crit";
  labels: Record<string, string>;
  cpu: { util: number; cores: number; model: string };
  ram: { used: number; total: string; usedGb: number; swap: number; psi: number };
  disks: DiskInfo[];
  nics: NicInfo[];
  // stubbed — null until Phase 4
  gpus: null;
  rdma: null;
  pcie: null;
}

export interface DiskInfo {
  dev: string;
  free: number;         // percent
  iops: number;
  maxIops: number;
  tput: number;         // GB/s
  maxTput: number;
  totalTB: number;
}

export interface NicInfo {
  dev: string;
  bw: number;           // percent
  drops: number;
  tx: number;           // Gb/s
  rx: number;
}

// --- GET /api/nodes/{node}/history response ---
export interface NodeHistoryResponse {
  metric: string;
  data: [number, number][];  // [timestamp_epoch_s, value]
}

// --- GET /api/labels response (already exists) ---
export interface NodeLabelsResponse {
  nodes: Record<string, Record<string, string>>;
}
```

### 3.3 API client layer with mock support

Create `frontend/src/api/client.ts`:

```typescript
import type { NodesResponse, NodeHistoryResponse, NodeLabelsResponse } from "./types";

const BASE = "";  // same-origin, proxied by Vite in dev

export async function fetchNodes(): Promise<NodesResponse> { ... }
export async function fetchNodeHistory(node: string, metric: string, start: string, end: string): Promise<NodeHistoryResponse> { ... }
export async function fetchLabels(): Promise<NodeLabelsResponse> { ... }
```

Create `frontend/src/api/mock-data.ts` — returns canned `NodesResponse` / `NodeLabelsResponse` shaped like the DATA constant in `docs/cluster-view.html` but limited to node-exporter fields (GPU/RDMA/PCIe are `null`). This is used by:
1. **Tests** (Vitest) — imported directly, no network needed
2. **Dev without backend** — toggled via `VITE_USE_MOCKS=true` env var

---

### 3.4 Component hierarchy

```
<App>
  <BrowserRouter>
    <Routes>
      <Route path="/" element={<ClusterDashboard />} />
      <Route path="/clusters/:clusterName" element={<ClusterDashboard />} />
    </Routes>
  </BrowserRouter>
</App>

<ClusterDashboard>                    ← top-level page, owns data fetching
  <DashboardHeader />                 ← title, legend, node count
  <FilterBar />                       ← search input + label chips, powered by GET /api/labels
  <ClusterTable>                      ← sticky header with column tabs (Disk: Space/IOPS/Tput, etc.)
    <NodeRow node={node} />           ← one per node
      <NodeCell />                    ← health bar + hostname pill + IP + labels tooltip
      <DiskColumn disks={disks} activeTab={tab} />
      <NetworkColumn nics={nics} activeTab={tab} />
      <CpuRamColumn cpu={cpu} ram={ram} activeTab={tab} />
      <GpuColumn gpus={null} />       ← stubbed "No data"
      <RdmaColumn rdma={null} />      ← stubbed "No data"
      <PcieColumn pcie={null} />      ← stubbed "No data"
  </ClusterTable>
  <MetricsModal />                    ← opens on square click, fetches GET /api/nodes/{id}/history
</ClusterDashboard>
```

#### Shared primitives (reusable across columns)

| Component | Purpose |
|-----------|---------|
| `<HeatSquare value={0-100} tooltip={string} thresholds={[40,70]} />` | Battery-fill square with green/yellow/red coloring |
| `<RamGauge percent={number} label={string} />` | Vertical gauge bar for RAM |
| `<TabBar tabs={string[]} active={string} onChange={fn} />` | Column tab switcher |
| `<Tooltip content={string} />` | Hover tooltip with formatted metric values |
| `<NoDataSquare />` | Grayed-out placeholder for stubbed columns |

---

### 3.5 Implementation steps

| Step | Description | Files touched | Depends on Phase 2? |
|------|-------------|---------------|---------------------|
| **3.5.1** | Add Vitest + React Testing Library to frontend | `package.json`, `vitest.config.ts`, `tsconfig.json` | No |
| **3.5.2** | Define TypeScript types (`api/types.ts`) | new file | No |
| **3.5.3** | Create API client + mock data module | `api/client.ts`, `api/mock-data.ts` | No (mocks only) |
| **3.5.4** | Build shared primitives: `HeatSquare`, `RamGauge`, `TabBar`, `Tooltip`, `NoDataSquare` | `components/primitives/` | No |
| **3.5.5** | Build column components: `NodeCell`, `DiskColumn`, `NetworkColumn`, `CpuRamColumn`, stubbed `GpuColumn`, `RdmaColumn`, `PcieColumn` | `components/columns/` | No |
| **3.5.6** | Build `NodeRow`, `ClusterTable` (sticky header + tab state), `FilterBar`, `DashboardHeader` | `components/` | No |
| **3.5.7** | Build `ClusterDashboard` page — data fetching, polling interval, loading/error states | `pages/ClusterDashboard.tsx` | **Soft** — works with mocks now, real endpoints after merge |
| **3.5.8** | Build `MetricsModal` — time-series chart (use a lightweight lib, e.g. `recharts` or raw `<canvas>`) | `components/MetricsModal.tsx` | **Soft** — same pattern |
| **3.5.9** | Port CSS from `docs/cluster-view.html` — match the exact visual design | `*.css` or CSS modules | No |
| **3.5.10** | Write full test suite (see §3.7) | `__tests__/` | No |
| **3.5.11** | Wire to real backend (post-merge with Phase 2 branch) | `api/client.ts` — remove mock fallback | **Yes** |

---

### 3.6 Reconciliation with Phase 2 branch

Phase 2 introduces:
- `GET /api/nodes` — returns `NodesResponse`
- `GET /api/nodes/{node}/history` — returns `NodeHistoryResponse`
- Mimir client (`cs_backend/mimir.py`)

**Reconciliation strategy**:
1. Phase 3 defines the TypeScript types (§3.2) as the contract. Phase 2 must produce responses matching these types.
2. Phase 3 uses `api/client.ts` which abstracts `fetch()` calls. In dev/test it can use mocks; after merge it hits real endpoints.
3. After merging Phase 2 into this branch:
   - Verify `GET /api/nodes` response matches `NodesResponse` type — run `tsc --noEmit`
   - Run the full test suite (§3.7) against the real backend using `CS_BACKEND_BASE_URL`
   - If the Phase 2 response shape differs from the types defined here, update the types and fix any breaking tests

**Merge conflict risk**: Low. Phase 3 only touches `frontend/` and adds no backend code. Phase 2 only touches `backend/`. The only shared surface is `routes.py` (Phase 2 adds new routes) and `schemas.py` (Phase 2 adds new Pydantic models). No overlapping edits expected.

---

### 3.7 Test plan — fully isolated, CI-ready

All tests run **without network access** to Mimir, K8s, or a running backend. The frontend test suite uses Vitest + React Testing Library with mock data injected at the API client boundary.

#### 3.7.1 Test infrastructure setup

**New dev dependencies** (add to `frontend/package.json`):
```json
{
  "devDependencies": {
    "@testing-library/react": "^16.x",
    "@testing-library/jest-dom": "^6.x",
    "@testing-library/user-event": "^14.x",
    "vitest": "^3.x",
    "jsdom": "^26.x",
    "@vitest/coverage-v8": "^3.x"
  }
}
```

**`frontend/vitest.config.ts`**:
```typescript
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
    css: true,
    coverage: { provider: "v8", reporter: ["text", "lcov"] },
  },
});
```

**`frontend/src/test-setup.ts`**:
```typescript
import "@testing-library/jest-dom/vitest";
```

**Mock strategy**: Every test file imports mock data from `api/mock-data.ts` and stubs the API client module using `vi.mock("../api/client")`. No HTTP requests are made. No backend, Mimir, or K8s access needed.

#### 3.7.2 Test suite — component tests

| # | Test file | What it verifies | Mock inputs |
|---|-----------|-----------------|-------------|
| 1 | `HeatSquare.test.tsx` | Renders with correct fill height (%) and color class (green/yellow/red) based on value and thresholds | `value=25` → green, `value=55` → yellow, `value=85` → red |
| 2 | `HeatSquare.test.tsx` | Shows tooltip on hover with formatted content | Mouse enter → tooltip visible |
| 3 | `RamGauge.test.tsx` | Renders gauge with correct height and label | `percent=45, label="920 / 2048 GB"` |
| 4 | `TabBar.test.tsx` | Renders tabs, highlights active tab, calls onChange on click | `tabs=["Space","IOPS","Tput"], active="Space"` |
| 5 | `NoDataSquare.test.tsx` | Renders grayed-out square with "No data" accessible label | — |
| 6 | `NodeCell.test.tsx` | Displays hostname, IP, health badge color | `id="node-1", ip="10.0.0.1", health="ok"` |
| 7 | `NodeCell.test.tsx` | Shows K8s labels in tooltip on hover | `labels={"topology.kubernetes.io/zone": "us-west-2a"}` |
| 8 | `DiskColumn.test.tsx` | Renders one square per disk device | 2 disks → 2 squares |
| 9 | `DiskColumn.test.tsx` | Square fill reflects disk usage (100 - free) | `free=78` → fill height ~22% |
| 10 | `DiskColumn.test.tsx` | Tab switch changes displayed metric (Space → IOPS → Tput) | Click IOPS tab → squares show IOPS values |
| 11 | `NetworkColumn.test.tsx` | Renders one square per NIC | 2 NICs → 2 squares |
| 12 | `NetworkColumn.test.tsx` | BW tab: fill reflects bandwidth % | `bw=50` → 50% fill |
| 13 | `NetworkColumn.test.tsx` | Drops tab: color reflects drop severity | `drops=0` → green, `drops=1247` → red |
| 14 | `CpuRamColumn.test.tsx` | CPU tab: heat square fill matches `cpu.util` | `util=35` → 35% fill |
| 15 | `CpuRamColumn.test.tsx` | CPU tab: shows core count label | `cores=128` → "128c" text |
| 16 | `CpuRamColumn.test.tsx` | Swap tab: shows swap gauge and PSI value | `swap=12, psi=14.8` |
| 17 | `GpuColumn.test.tsx` | Renders "No data" stub state when `gpus=null` | `gpus=null` |
| 18 | `RdmaColumn.test.tsx` | Renders "No data" stub state when `rdma=null` | `rdma=null` |
| 19 | `PcieColumn.test.tsx` | Renders "No data" stub state when `pcie=null` | `pcie=null` |

#### 3.7.3 Test suite — integration tests (page-level)

| # | Test file | What it verifies | Mock setup |
|---|-----------|-----------------|------------|
| 20 | `ClusterDashboard.test.tsx` | Renders one `<NodeRow>` per node in mock data | Mock `fetchNodes()` → 3 nodes → 3 rows |
| 21 | `ClusterDashboard.test.tsx` | Shows loading spinner before data arrives | Mock `fetchNodes()` with delayed resolve |
| 22 | `ClusterDashboard.test.tsx` | Shows error banner when fetch fails | Mock `fetchNodes()` → reject |
| 23 | `ClusterDashboard.test.tsx` | Disk tab switching is global (all rows update) | Click "IOPS" in header → all DiskColumns reflect IOPS |
| 24 | `ClusterDashboard.test.tsx` | Network tab switching is global | Click "Drops" in header → all NetworkColumns reflect drops |
| 25 | `FilterBar.test.tsx` | Renders label key suggestions from mock `/api/labels` | Mock `fetchLabels()` → label keys appear in dropdown |
| 26 | `FilterBar.test.tsx` | Selecting a filter chip hides non-matching nodes | Filter `zone=us-west-2a` → only matching nodes visible |
| 27 | `FilterBar.test.tsx` | Removing a filter chip restores hidden nodes | Remove chip → all nodes visible again |
| 28 | `FilterBar.test.tsx` | Search input filters suggestions as user types | Type "zone" → only zone-related suggestions shown |
| 29 | `MetricsModal.test.tsx` | Modal opens when a square is clicked | Click square → modal renders with node name in title |
| 30 | `MetricsModal.test.tsx` | Modal fetches history for the clicked metric | Click CPU square → `fetchNodeHistory(node, "cpu", ...)` called |
| 31 | `MetricsModal.test.tsx` | Modal closes on backdrop click or Escape | Click backdrop → modal unmounts |
| 32 | `MetricsModal.test.tsx` | Renders a chart/sparkline with time-series data | Mock history response → `<canvas>` or SVG path rendered |

#### 3.7.4 Test suite — data flow & edge cases

| # | Test file | What it verifies | Mock setup |
|---|-----------|-----------------|------------|
| 33 | `ClusterDashboard.test.tsx` | Handles empty node list gracefully | Mock `fetchNodes()` → `{ nodes: [] }` → "No nodes" message |
| 34 | `ClusterDashboard.test.tsx` | Handles node with 0 disks (no crash) | Node with `disks: []` → DiskColumn renders empty |
| 35 | `ClusterDashboard.test.tsx` | Handles node with 0 NICs (no crash) | Node with `nics: []` → NetworkColumn renders empty |
| 36 | `DiskColumn.test.tsx` | Boundary: 0% free disk → 100% filled, red | `free=0` → full square, red color |
| 37 | `DiskColumn.test.tsx` | Boundary: 100% free disk → 0% filled, green | `free=100` → empty square, green |
| 38 | `CpuRamColumn.test.tsx` | Boundary: 0% CPU util → empty square | `util=0` |
| 39 | `CpuRamColumn.test.tsx` | Boundary: 100% CPU util → full square, red | `util=100` |
| 40 | `NodeCell.test.tsx` | Health badge: "ok" → green, "warn" → yellow, "crit" → red | All 3 states |

#### 3.7.5 Running tests in CI

Add to `frontend/package.json` scripts:
```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage"
  }
}
```

**GitHub Actions job** (add to existing CI workflow):
```yaml
  test-frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: cluster-stats-ui/frontend
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with:
          version: 10
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: pnpm
          cache-dependency-path: cluster-stats-ui/frontend/pnpm-lock.yaml
      - run: pnpm install --frozen-lockfile
      - run: pnpm run test:coverage
      - run: pnpm run lint
      - run: pnpm run build
```

**Isolation guarantees**:
- `jsdom` environment — no real browser needed
- All API calls mocked via `vi.mock()` — no network access
- No Docker, Mimir, K8s, or backend process required
- CSS is included (`css: true` in vitest config) so class-based assertions work
- Runs in ~10s on CI

---

### 3.8 Manual verification checklist

After implementation, start backend + frontend in dev mode and verify in browser:

- [ ] Table renders with one row per node
- [ ] Disk squares fill proportionally to usage
- [ ] Network BW squares fill proportionally
- [ ] CPU square fills proportionally
- [ ] RAM gauge shows correct percentage
- [ ] Tab switching works (Disk: Space → IOPS → Tput; Net: BW → Drops; CPU/RAM: CPU → Swap)
- [ ] Filter dropdown shows K8s labels and filters rows
- [ ] Hovering a square shows tooltip with actual values
- [ ] GPU/RDMA/PCIe columns show "No data" state
- [ ] Metrics modal opens and shows time-series charts for available metrics
- [ ] Page handles backend being down (error state, not blank screen)

---

## Phase 4: Mock DCGM exporter for GPU metrics

**Goal**: Since there are no GPUs on this cluster, deploy a lightweight service that exposes fake DCGM metrics in Prometheus format so the full UI pipeline can be tested end-to-end.

### 4.0 Mocking options research

| Option | DCGM_FI_ names? | No GPU needed? | Deploy ready? | Notes |
|--------|:---:|:---:|:---:|-------|
| **dcgm-exporter** (official) | Yes | **No** — crashes with "NVML doesn't exist" ([#385](https://github.com/NVIDIA/dcgm-exporter/issues/385), [#416](https://github.com/NVIDIA/dcgm-exporter/issues/416)) | Yes (with GPU) | No `--fake`, `--mock`, or `--test` flag exists |
| **[run-ai/fake-gpu-operator](https://github.com/run-ai/fake-gpu-operator)** | **Yes** | **Yes** | **Yes** (Helm) | Emits `DCGM_FI_DEV_GPU_UTIL`, `DCGM_FI_DEV_FB_USED`, `DCGM_FI_DEV_FB_FREE` on port 9400 with correct labels. RBAC bug fixed in PR #94. **Only 3 metrics** — no temp, power, PCIe. |
| **DCGM `CreateFakeEntities()` + `InjectFieldValue()`** | Yes | No (needs driver) | No (write Go) | Low-level go-dcgm test API ([dcgm_test_apis.h](https://github.com/NVIDIA/go-dcgm/blob/main/pkg/dcgm/dcgm_test_apis.h)). Full metric control but requires DCGM host engine. |
| **[intel/fakedev-exporter](https://github.com/intel/fakedev-exporter)** | No (Intel names) | Yes | Yes | Generic device simulator. Would need significant reconfiguration for DCGM metric names. |
| **NVIDIA Fake GPU Operator** (docs.nvidia.com) | No | Yes | Yes | KWOK-based. Simulates `nvidia.com/gpu` scheduling resources only, no telemetry. |
| **Custom Python exporter** | Yes (configurable) | Yes | Build it | ~100 LOC with `prometheus_client`. Full control over metric names, labels, and values. |

**Recommended approach: run-ai/fake-gpu-operator + supplemental custom exporter**

1. Deploy `run-ai/fake-gpu-operator` via Helm — gives us the 3 core metrics (`GPU_UTIL`, `FB_USED`, `FB_FREE`) with correct labels, zero custom code
2. For the additional metrics the UI needs (`GPU_TEMP`, `POWER_USAGE`), extend with a small sidecar exporter (~50 LOC) that reads the fake-gpu-operator's topology config and emits the extra gauges

This gives us an officially-maintained base with minimal custom code only for the gaps.

### 4.1 What DCGM exporter metrics look like

The real [NVIDIA DCGM Exporter](https://github.com/NVIDIA/dcgm-exporter) exposes metrics like:

```
# HELP DCGM_FI_DEV_GPU_UTIL GPU utilization (in %).
# TYPE DCGM_FI_DEV_GPU_UTIL gauge
DCGM_FI_DEV_GPU_UTIL{gpu="0",UUID="GPU-abc123",device="nvidia0",modelName="NVIDIA H100 80GB HBM3",Hostname="node-1"} 72
DCGM_FI_DEV_GPU_UTIL{gpu="1",UUID="GPU-def456",device="nvidia1",modelName="NVIDIA H100 80GB HBM3",Hostname="node-1"} 95

# HELP DCGM_FI_DEV_FB_USED Framebuffer memory used (in MiB).
# TYPE DCGM_FI_DEV_FB_USED gauge
DCGM_FI_DEV_FB_USED{gpu="0",UUID="GPU-abc123",device="nvidia0",modelName="NVIDIA H100 80GB HBM3",Hostname="node-1"} 58000
DCGM_FI_DEV_FB_USED{gpu="1",UUID="GPU-def456",device="nvidia1",modelName="NVIDIA H100 80GB HBM3",Hostname="node-1"} 71000

# HELP DCGM_FI_DEV_FB_FREE Framebuffer memory free (in MiB).
# TYPE DCGM_FI_DEV_FB_FREE gauge
DCGM_FI_DEV_FB_FREE{gpu="0",...} 23920
DCGM_FI_DEV_FB_FREE{gpu="1",...} 10920

# HELP DCGM_FI_DEV_GPU_TEMP GPU temperature (in C).
# TYPE DCGM_FI_DEV_GPU_TEMP gauge
DCGM_FI_DEV_GPU_TEMP{gpu="0",...} 68
DCGM_FI_DEV_GPU_TEMP{gpu="1",...} 74

# HELP DCGM_FI_DEV_POWER_USAGE Power draw (in W).
# TYPE DCGM_FI_DEV_POWER_USAGE gauge
DCGM_FI_DEV_POWER_USAGE{gpu="0",...} 420.5
DCGM_FI_DEV_POWER_USAGE{gpu="1",...} 680.2

# HELP DCGM_FI_DEV_PCIE_TX_THROUGHPUT Total PCIe TX bytes (in KB).
# TYPE DCGM_FI_DEV_PCIE_TX_THROUGHPUT counter
DCGM_FI_DEV_PCIE_TX_THROUGHPUT{gpu="0",...} 123456789

# HELP DCGM_FI_DEV_PCIE_RX_THROUGHPUT Total PCIe RX bytes (in KB).
# TYPE DCGM_FI_DEV_PCIE_RX_THROUGHPUT counter
DCGM_FI_DEV_PCIE_RX_THROUGHPUT{gpu="0",...} 987654321
```

### 4.2 Deploy run-ai/fake-gpu-operator

```bash
helm repo add fake-gpu-operator oci://ghcr.io/run-ai/fake-gpu-operator
helm upgrade -i gpu-operator oci://ghcr.io/run-ai/fake-gpu-operator/fake-gpu-operator \
  --namespace gpu-operator --create-namespace \
  --set topology.nodePools.default.gpuProduct="NVIDIA-H100-80GB-HBM3" \
  --set topology.nodePools.default.gpuCount=4 \
  --set topology.nodePools.default.gpuMemory=81920
```

This gives us `DCGM_FI_DEV_GPU_UTIL`, `DCGM_FI_DEV_FB_USED`, `DCGM_FI_DEV_FB_FREE` on port 9400 with labels `gpu`, `UUID`, `device`, `modelName`, `Hostname`.

### 4.3 Supplemental exporter for temp + power

The fake-gpu-operator doesn't emit temperature or power metrics. Create `mock-dcgm-supplement/main.py` (~50 lines) using `prometheus_client` that:

1. Reads the same topology config (GPU count, model) from env vars
2. On each `/metrics` scrape, emits:
   - `DCGM_FI_DEV_GPU_TEMP` — correlated with utilization (idle ~30C, load ~80C)
   - `DCGM_FI_DEV_POWER_USAGE` — correlated with utilization (idle ~45W, load ~700W)
3. Uses matching labels (`gpu`, `UUID`, `device`, `modelName`, `Hostname`) so Mimir can join them with the operator's metrics
4. Expose on port 9401 (separate from the operator's 9400)

Deploy as a DaemonSet alongside the fake-gpu-operator pods.

### 4.4 Add Alloy scrape configs

```river
// Scrape fake-gpu-operator's status-exporter (port 9400)
discovery.relabel "dcgm_exporter" {
  targets = discovery.kubernetes.endpoints.targets
  rule {
    source_labels = ["__meta_kubernetes_service_name"]
    regex         = "nvidia-dcgm-exporter"  // name used by fake-gpu-operator
    action        = "keep"
  }
}

prometheus.scrape "dcgm_exporter" {
  targets         = discovery.relabel.dcgm_exporter.output
  job_name        = "dcgm-exporter"
  scrape_interval = "30s"
  forward_to      = [prometheus.remote_write.mimir.receiver]
}

// Scrape supplemental temp+power exporter (port 9401)
discovery.relabel "dcgm_supplement" {
  targets = discovery.kubernetes.endpoints.targets
  rule {
    source_labels = ["__meta_kubernetes_service_name"]
    regex         = "dcgm-supplement"
    action        = "keep"
  }
}

prometheus.scrape "dcgm_supplement" {
  targets         = discovery.relabel.dcgm_supplement.output
  job_name        = "dcgm-exporter"  // same job_name so metrics merge naturally
  scrape_interval = "30s"
  forward_to      = [prometheus.remote_write.mimir.receiver]
}
```

### 4.5 Verify mock GPU metrics in Mimir

```bash
kubectl port-forward -n monitoring svc/mimir-gateway 8080:80
curl -s 'http://localhost:8080/prometheus/api/v1/query?query=DCGM_FI_DEV_GPU_UTIL' | jq '.data.result | length'
curl -s 'http://localhost:8080/prometheus/api/v1/query?query=DCGM_FI_DEV_GPU_TEMP' | jq '.data.result | length'
curl -s 'http://localhost:8080/prometheus/api/v1/query?query=DCGM_FI_DEV_FB_USED' | jq '.data.result | length'
curl -s 'http://localhost:8080/prometheus/api/v1/query?query=DCGM_FI_DEV_POWER_USAGE' | jq '.data.result | length'
```

**PASS criteria**: Each query returns `result | length` equal to (number of nodes × fake GPU count).

### 4.6 Wire GPU metrics into backend + UI

1. Add PromQL queries to the backend:

   | UI Field | PromQL |
   |----------|--------|
   | GPU util (%) | `DCGM_FI_DEV_GPU_UTIL` |
   | GPU VRAM used (%) | `100 * DCGM_FI_DEV_FB_USED / (DCGM_FI_DEV_FB_USED + DCGM_FI_DEV_FB_FREE)` |
   | GPU temp (C) | `DCGM_FI_DEV_GPU_TEMP` |
   | GPU power (W) | `DCGM_FI_DEV_POWER_USAGE` |

2. Un-stub the GPU column in the React UI
3. Verify: GPU squares now fill with data, tooltips show values

---

## Local Verification Strategy (applies to all phases)

Each phase needs to be testable locally before deploying to EKS. There are two modes:

### Mode A: Port-forward to real EKS Mimir

For phases that only read from Mimir (Phases 0, 2, 3), you can point at the real cluster:

```bash
# Terminal 1: port-forward Mimir
kubectl port-forward -n monitoring svc/mimir-gateway 8080:80

# Terminal 2: run backend (Phase 2+)
cd cluster-stats-ui
MIMIR_URL=http://localhost:8080 uv run uvicorn cs_backend.app:create_app --factory --reload --port 8000

# Terminal 3: run frontend dev server (Phase 3+)
cd cluster-stats-ui/frontend
pnpm run dev
```

The backend uses `~/.kube/config` for K8s API calls (node labels) when running outside the cluster. This just works if you have `kubectl` access.

### Mode B: Docker-compose (fully local, no cluster needed)

For CI and offline dev. Built incrementally — each phase adds services:

```yaml
# docker-compose.yaml
services:
  mimir:
    image: grafana/mimir:latest
    command: ["-config.file=/etc/mimir/mimir.yaml", "-target=all"]
    volumes:
      - ./docker/mimir.yaml:/etc/mimir/mimir.yaml
    ports: ["8080:8080"]

  node-exporter:
    image: prom/node-exporter:latest
    ports: ["9100:9100"]
    # scrapes real host metrics from your dev machine

  alloy:
    image: grafana/alloy:latest
    volumes:
      - ./docker/alloy-config.river:/etc/alloy/config.river
    command: ["run", "/etc/alloy/config.river"]
    depends_on: [mimir, node-exporter]
    # scrapes node-exporter, remote_writes to mimir

  # Phase 4 adds:
  mock-dcgm-supplement:
    build: ./mock-dcgm-supplement
    ports: ["9401:9401"]
    # note: run-ai/fake-gpu-operator only runs in k8s,
    # so in docker-compose we use the supplement exporter
    # for ALL GPU metrics (util, fb, temp, power)

  backend:
    build: ./cluster-stats-ui/backend
    environment:
      MIMIR_URL: http://mimir:8080
      # In docker-compose, no K8s API available.
      # Backend falls back to returning a single "localhost" node
      # with no K8s labels (label filtering disabled).
    ports: ["8000:8000"]
    volumes:
      - ./cluster-stats-ui/backend/src:/app/src
    depends_on: [mimir]
```

### Per-phase local verification checklist

| Phase | What to verify locally | Mode |
|-------|----------------------|------|
| **0** | `curl localhost:8080/prometheus/api/v1/query?query=node_cpu_seconds_total` returns results | A (port-forward) |
| **1** | Metrics have `node` label: `curl ... \| jq '.data.result[0].metric.node'` is non-null | A (redeploy Alloy, port-forward) |
| **2** | `curl localhost:8000/api/nodes` returns nodes with metrics; `curl localhost:8000/api/labels` returns label map | A or B |
| **3** | Open `http://localhost:5173` in browser, see table with filled squares, click tabs, hover tooltips | A or B |
| **4** | `curl localhost:8080/.../query?query=DCGM_FI_DEV_GPU_UTIL` returns results; GPU column in UI shows data | A (after EKS deploy) or B |
| **5** | `docker compose up` from scratch → full UI working at `localhost:8000` | B |
| **6** | `npx playwright test` passes against docker-compose stack | B |

---

## Phase 5: Docker-compose local development stack

**Goal**: Enable fully local development with all dependencies (see Mode B above).

### 5.1 Minimal Mimir config for local dev

Create `docker/mimir.yaml`:
```yaml
multitenancy_enabled: false
server:
  http_listen_port: 8080
blocks_storage:
  backend: filesystem
  filesystem:
    dir: /tmp/mimir/blocks
  tsdb:
    dir: /tmp/mimir/tsdb
compactor:
  data_dir: /tmp/mimir/compactor
ruler_storage:
  backend: filesystem
  filesystem:
    dir: /tmp/mimir/rules
```

### 5.2 Local Alloy config

Create `docker/alloy-config.river` — same scrape logic as the Helm values but with static targets instead of k8s discovery:
```river
prometheus.scrape "node_exporter" {
  targets    = [{"__address__" = "node-exporter:9100"}]
  job_name   = "node-exporter"
  scrape_interval = "15s"
  forward_to = [prometheus.remote_write.mimir.receiver]
}

prometheus.scrape "dcgm_supplement" {
  targets    = [{"__address__" = "mock-dcgm-supplement:9401"}]
  job_name   = "dcgm-exporter"
  scrape_interval = "15s"
  forward_to = [prometheus.remote_write.mimir.receiver]
}

prometheus.remote_write "mimir" {
  endpoint {
    url = "http://mimir:8080/api/v1/push"
  }
}
```

### 5.3 Verify

```bash
docker compose up -d
# Wait ~30s for scrape cycles
curl -s 'http://localhost:8080/prometheus/api/v1/query?query=up' | jq '.data.result[].metric'
# Should show node-exporter and dcgm-exporter targets
curl -s http://localhost:8000/api/nodes | jq '.nodes | length'
# Open http://localhost:8000 in browser
```

---

## Phase 6: Playwright end-to-end tests

**Goal**: Automated browser tests that validate the UI renders correctly with real metric data.

### 6.1 Test setup

- `docker compose up` starts the full stack (Mimir + Alloy + node-exporter + mock-dcgm-supplement + backend)
- Wait for Alloy to scrape at least 2 cycles (~30s with 15s interval)
- Playwright connects to the frontend at `http://localhost:8000`

### 6.2 Test cases

```
test("table renders at least one node row")
test("disk space squares have non-zero fill height")
test("network BW squares have non-zero fill height")
test("CPU square has non-zero fill height")
test("RAM gauge shows a percentage")
test("GPU squares have non-zero fill height")  # from mock DCGM
test("tab switching changes displayed metric")
test("filter dropdown contains K8s label values")  # only in port-forward mode
test("tooltip appears on square hover with numeric value")
test("metrics modal opens and shows chart")
```

### 6.3 Add to GitHub Actions

```yaml
- name: Run Playwright tests
  run: |
    docker compose up -d
    sleep 45  # wait for scrape cycles
    npx playwright test
    docker compose down
```

Run this job in parallel with existing unit test jobs.

---

## Execution Order (Incremental)

```
Phase 0: Verify existing metrics          ← 30 min, zero code changes, port-forward only
    ↓
Phase 1: Alloy relabel + K8s API labels  ← small, alloy.yaml + RBAC manifest, redeploy
    ↓
Phase 2: FastAPI backend endpoints        ← largest chunk, verify with curl against port-forwarded Mimir
    ↓
Phase 3: React UI (node-exporter only)    ← largest chunk, verify in browser against port-forwarded Mimir
    ↓
Phase 4: Mock DCGM (fake-gpu-operator    ← deploy to EKS + supplement exporter, un-stub GPU column
         + supplement exporter)
    ↓
Phase 5: Docker-compose local dev         ← devex, enables offline development
    ↓
Phase 6: Playwright e2e tests             ← CI hardening, runs against docker-compose
```

Phases 2 and 3 are the biggest. Phases 4–6 can be parallelized across team members.
