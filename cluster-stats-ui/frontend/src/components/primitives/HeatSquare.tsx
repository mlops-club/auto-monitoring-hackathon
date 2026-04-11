import { useState } from "react";

interface Props {
  value: number;
  tooltip: string;
  thresholds?: [number, number];
}

function colorClass(value: number, thresholds: [number, number]): string {
  if (value >= thresholds[1]) return "red";
  if (value >= thresholds[0]) return "yellow";
  return "green";
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
      {show && (
        <span className="sq-tooltip" role="tooltip">
          {tooltip}
        </span>
      )}
    </span>
  );
}
