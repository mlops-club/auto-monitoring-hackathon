import type { NodesResponse, NodeHistoryResponse, NodeLabelsResponse } from "./types";
import { MOCK_NODES, MOCK_LABELS, mockNodeHistory } from "./mock-data";

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === "true";

export async function fetchNodes(): Promise<NodesResponse> {
  if (USE_MOCKS) return MOCK_NODES;
  const res = await fetch("/api/nodes");
  if (!res.ok) throw new Error(`fetchNodes failed: ${res.status}`);
  return res.json();
}

export async function fetchNodeHistory(
  node: string,
  metric: string,
  start: string,
  end: string,
): Promise<NodeHistoryResponse> {
  if (USE_MOCKS) return mockNodeHistory(metric);
  const params = new URLSearchParams({ metric, start, end });
  const res = await fetch(`/api/nodes/${encodeURIComponent(node)}/history?${params}`);
  if (!res.ok) throw new Error(`fetchNodeHistory failed: ${res.status}`);
  return res.json();
}

export async function fetchLabels(): Promise<NodeLabelsResponse> {
  if (USE_MOCKS) return MOCK_LABELS;
  const res = await fetch("/api/labels");
  if (!res.ok) throw new Error(`fetchLabels failed: ${res.status}`);
  return res.json();
}
