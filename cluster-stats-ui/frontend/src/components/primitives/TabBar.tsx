interface Props {
  tabs: string[];
  active: string;
  onChange: (tab: string) => void;
}

export function TabBar({ tabs, active, onChange }: Props) {
  return (
    <span className="col-tabs" data-testid="tab-bar">
      {tabs.map((tab) => (
        <button
          key={tab}
          className={`col-tab${tab === active ? " active" : ""}`}
          onClick={() => onChange(tab)}
        >
          {tab}
        </button>
      ))}
    </span>
  );
}
