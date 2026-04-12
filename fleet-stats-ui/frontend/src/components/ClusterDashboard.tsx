import { useEffect, useState, useCallback, useMemo } from "react";
import type { NodesResponse, NodeLabelsResponse } from "../api/types";
import { fetchNodes, fetchLabels } from "../api/client";
import { DashboardHeader } from "./DashboardHeader";
import { FilterBar } from "./FilterBar";
import { ClusterTable } from "./ClusterTable";

export function ClusterDashboard() {
  const [nodesData, setNodesData] = useState<NodesResponse | null>(null);
  const [labelsData, setLabelsData] = useState<NodeLabelsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeFilters, setActiveFilters] = useState<string[]>([]);
  const [groupBy, setGroupBy] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [nodes, labels] = await Promise.all([fetchNodes(), fetchLabels()]);
        if (!cancelled) {
          setNodesData(nodes);
          setLabelsData(labels);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to load data");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  const addFilter = useCallback((f: string) => {
    setActiveFilters((prev) => (prev.includes(f) ? prev : [...prev, f]));
  }, []);

  const removeFilter = useCallback((i: number) => {
    setActiveFilters((prev) => prev.filter((_, idx) => idx !== i));
  }, []);

  const filteredNodes = useMemo(() => {
    if (!nodesData) return [];
    if (activeFilters.length === 0) return nodesData.nodes;
    return nodesData.nodes.filter((node) =>
      activeFilters.every((f) => {
        const [key, ...rest] = f.split("=");
        const val = rest.join("=");
        return node.labels[key] === val;
      }),
    );
  }, [nodesData, activeFilters]);

  if (loading) return <div className="loading" data-testid="loading">Loading...</div>;
  if (error) return <div className="error-banner" data-testid="error-banner">{error}</div>;

  return (
    <div className="dashboard" data-testid="cluster-dashboard">
      <DashboardHeader nodeCount={filteredNodes.length} />
      <FilterBar
        labelsData={labelsData}
        activeFilters={activeFilters}
        onAddFilter={addFilter}
        onRemoveFilter={removeFilter}
        groupBy={groupBy}
        onGroupByChange={setGroupBy}
      />
      {filteredNodes.length === 0 ? (
        <p className="no-nodes" data-testid="no-nodes">No nodes match the current filters.</p>
      ) : (
        <ClusterTable nodes={filteredNodes} groupBy={groupBy} />
      )}
    </div>
  );
}
