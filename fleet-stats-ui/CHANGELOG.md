# Fleet Stats UI — Changelog

## 2026-04-11

### Phase 3: React UI for cluster dashboard

- Ported HTML prototype to React with Vitest test suite (47 tests, fully isolated, no network)
- Components: ClusterDashboard, ClusterTable, NodeRow, FilterBar, DiskColumn, NetworkColumn, CpuRamColumn, stubbed GPU/RDMA/PCIe
- API client layer with TypeScript types matching Phase 2 backend schemas

### User requests

| Request | Resolution |
|---------|-----------|
| Do not color-code rows or tag with OK/WARN/CRIT | Removed alternating row colors, health bars, and health badges |
| RAM box renders weirdly — horizontally squished | Replaced RamGauge with a standard HeatSquare |
| Add group-by label support | Added "Group by" dropdown in FilterBar; ClusterTable renders group header rows |
| Clean up OK/Warn/Crit legend in header | Removed legend from DashboardHeader |
| Update tooltips to match reference HTML | Matched tooltip content to `docs/cluster-view.html` (disk space/IOPS/tput, net BW/drops, CPU/RAM/swap/PSI) |
| Too many network squares (eni*, lo) | Filtered to physical NICs only (eth*); disk tabs now show partitions for Space, whole devices for IOPS/Tput |
| Tooltips not appearing on hover | Removed `overflow: hidden` from `.sq-batt` that was clipping the tooltip |
| Tooltips need prettier formatting with label/value distinction | Structured tooltips with bold title, divider, and label (gray) / value (white monospace) rows |
| Disk tooltip should show used/total in GiB or TiB | Added `disk_size` PromQL query + `size_bytes` field to backend; tooltip shows "X GiB / Y GiB" |

### Wiring to real backend

- Merged Phase 2 (Mimir query endpoints) from main
- Updated frontend types to match backend Pydantic schemas (nullable fields, raw bytes)
- Removed mock toggle — API client hits real `/api/nodes`, `/api/labels` endpoints
