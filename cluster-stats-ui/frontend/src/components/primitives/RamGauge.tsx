interface Props {
  percent: number;
  label: string;
}

export function RamGauge({ percent, label }: Props) {
  return (
    <span className="ram-gauge" data-testid="ram-gauge" title={label}>
      <span
        className="ram-gauge-fill"
        style={{ height: `${Math.min(100, Math.max(0, percent))}%` }}
        data-testid="ram-gauge-fill"
      />
      <span className="ram-gauge-label">{Math.round(percent)}%</span>
    </span>
  );
}
