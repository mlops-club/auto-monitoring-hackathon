import { useState } from "react";
import type { NodeMetrics } from "../../api/types";

interface Props {
  node: Pick<NodeMetrics, "id" | "ip" | "health" | "labels">;
}

export function NodeCell({ node }: Props) {
  const [showLabels, setShowLabels] = useState(false);
  const labelText = Object.entries(node.labels)
    .map(([k, v]) => `${k}=${v}`)
    .join("\n");

  return (
    <td>
      <div className="node-cell">
        <span
          className="node-name"
          onMouseEnter={() => setShowLabels(true)}
          onMouseLeave={() => setShowLabels(false)}
          data-testid="node-name"
        >
          {node.id}
          {showLabels && labelText && (
            <span className="sq-tooltip" role="tooltip">{labelText}</span>
          )}
        </span>
        <span className="node-ip">{node.ip}</span>
      </div>
    </td>
  );
}
