export interface TabItem<T extends string> {
  value: T;
  label: string;
  count?: number;
}

interface TabsProps<T extends string> {
  tabs: TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
  label: string;
}

export default function Tabs<T extends string>({ tabs, value, onChange, label }: TabsProps<T>) {
  return (
    <div role="tablist" aria-label={label} className="flex flex-wrap gap-1">
      {tabs.map((t) => {
        const selected = t.value === value;
        return (
          <button
            key={t.value}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(t.value)}
            className={`border-b-2 px-3 py-4 text-sm font-medium transition ${
              selected
                ? "border-accent text-accent"
                : "border-transparent text-muted hover:text-foreground"
            }`}
          >
            {t.label}
            {t.count !== undefined && <span className="ml-1 text-xs">{t.count}</span>}
          </button>
        );
      })}
    </div>
  );
}
