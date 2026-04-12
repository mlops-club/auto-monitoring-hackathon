import { useState } from "react";
import type { ReactNode } from "react";

export interface TooltipRow {
  label: string;
  value: string;
}

interface Props {
  value: number;
  tooltip: { title: string; rows: TooltipRow[] };
  thresholds?: [number, number];
}

function colorClass(value: number, thresholds: [number, number]): string {
  if (value >= thresholds[1]) return "red";
  if (value >= thresholds[0]) return "yellow";
  return "green";
}

function renderTooltip(tt: Props["tooltip"]): ReactNode {
  return (
    <span className="sq-tooltip" role="tooltip">
      <div className="tt-title">{tt.title}</div>
      {tt.rows.map((r) => (
        <div className="tt-row" key={r.label}>
          <span className="tt-label">{r.label}</span>
          <span className="tt-val">{r.value}</span>
        </div>
      ))}
    </span>
  );
}

export function HeatSquare({ value, tooltip, thresholds = [40, 70] }: Props) {
  const [show, setShow] = useState(false);
  const color = colorClass(value, thresholds);

  return (
    <span
      className="sq sq-batt"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
      data-testid="heat-square"
    >
      <span
        className={`sq-batt-fill ${color}`}
        style={{ height: `${Math.min(100, Math.max(0, value))}%` }}
        data-testid="heat-square-fill"
      />
      {show && renderTooltip(tooltip)}
    </span>
  );
}
