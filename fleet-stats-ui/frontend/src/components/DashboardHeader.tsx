interface Props {
  nodeCount: number;
}

export function DashboardHeader({ nodeCount }: Props) {
  return (
    <div className="header" data-testid="dashboard-header">
      <div className="header-left">
        <h1>Cluster Overview</h1>
        <p>{nodeCount} node{nodeCount !== 1 ? "s" : ""}</p>
      </div>
    </div>
  );
}
