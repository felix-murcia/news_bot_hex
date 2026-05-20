interface Tab {
  id: string;
  label: string;
}

interface TabsProps {
  tabs: Tab[];
  active: string;
  onChange: (id: string) => void;
}

export function Tabs({ tabs, active, onChange }: TabsProps) {
  return (
    <div className="flex gap-1 border-b border-surface-border mb-8">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`px-5 py-2.5 text-sm font-medium rounded-t transition-colors ${
            active === tab.id
              ? "text-white border-b-2 border-accent -mb-px bg-surface-card"
              : "text-gray-400 hover:text-gray-200 hover:bg-surface-hover"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
