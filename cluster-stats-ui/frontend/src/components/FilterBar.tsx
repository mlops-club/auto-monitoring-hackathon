import { useState, useMemo } from "react";
import type { NodeLabelsResponse } from "../api/types";

interface Props {
  labelsData: NodeLabelsResponse | null;
  activeFilters: string[];
  onAddFilter: (filter: string) => void;
  onRemoveFilter: (index: number) => void;
  groupBy: string | null;
  onGroupByChange: (key: string | null) => void;
}

export function FilterBar({ labelsData, activeFilters, onAddFilter, onRemoveFilter, groupBy, onGroupByChange }: Props) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);

  const { suggestions, labelKeys } = useMemo(() => {
    if (!labelsData) return { suggestions: [] as string[], labelKeys: [] as string[] };
    const pairs: string[] = [];
    const keys = new Set<string>();
    for (const labels of Object.values(labelsData.nodes)) {
      for (const [k, v] of Object.entries(labels)) {
        keys.add(k);
        const pair = `${k}=${v}`;
        if (!pairs.includes(pair)) pairs.push(pair);
      }
    }
    return { suggestions: pairs.sort(), labelKeys: [...keys].sort() };
  }, [labelsData]);

  const filtered = query
    ? suggestions.filter((s) => s.toLowerCase().includes(query.toLowerCase()))
    : suggestions;

  return (
    <div className="search-bar" data-testid="filter-bar">
      <div className="search-wrap">
        <input
          className="search-input"
          placeholder="Filter by label..."
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          data-testid="filter-input"
        />
        {open && filtered.length > 0 && (
          <div className="autocomplete-dropdown open" data-testid="filter-dropdown">
            {filtered.map((s) => (
              <div
                key={s}
                className="ac-item"
                onMouseDown={() => { onAddFilter(s); setQuery(""); setOpen(false); }}
              >
                {s}
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="filter-chips" data-testid="filter-chips">
        {activeFilters.map((f, i) => (
          <span key={f} className="filter-chip">
            {f}
            <span className="filter-chip-x" onClick={() => onRemoveFilter(i)} data-testid="remove-filter">
              &times;
            </span>
          </span>
        ))}
      </div>
      <select
        className="group-by-select"
        value={groupBy ?? ""}
        onChange={(e) => onGroupByChange(e.target.value || null)}
        data-testid="group-by-select"
      >
        <option value="">No grouping</option>
        {labelKeys.map((k) => (
          <option key={k} value={k}>{k}</option>
        ))}
      </select>
    </div>
  );
}
