import type { NodesResponse, NodeHistoryResponse, NodeLabelsResponse } from "./types";

export async function fetchNodes(): Promise<NodesResponse> {
  const res = await fetch("/api/nodes");
  if (!res.ok) throw new Error(`fetchNodes failed: ${res.status}`);
  return res.json();
}

export async function fetchNodeHistory(
  node: string,
  metric: string,
  start?: number,
  end?: number,
  step?: string,
): Promise<NodeHistoryResponse> {
  const params = new URLSearchParams({ metric });
  if (start != null) params.set("start", String(start));
  if (end != null) params.set("end", String(end));
  if (step) params.set("step", step);
  const res = await fetch(`/api/nodes/${encodeURIComponent(node)}/history?${params}`);
  if (!res.ok) throw new Error(`fetchNodeHistory failed: ${res.status}`);
  return res.json();
}

export async function fetchLabels(): Promise<NodeLabelsResponse> {
  const res = await fetch("/api/labels");
  if (!res.ok) throw new Error(`fetchLabels failed: ${res.status}`);
  return res.json();
}
