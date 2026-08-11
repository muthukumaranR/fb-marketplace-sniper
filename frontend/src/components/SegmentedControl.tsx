export interface Segment<T extends string> {
  value: T;
  label: string;
  /** Optional mono count rendered after the label. */
  count?: number;
}

interface Props<T extends string> {
  segments: Segment<T>[];
  value: T;
  onChange: (value: T) => void;
}

/**
 * The 3px-padded sunken container from the handoff. The active item is the only
 * element in the design carrying a shadow.
 */
export default function SegmentedControl<T extends string>({
  segments,
  value,
  onChange,
}: Props<T>) {
  return (
    <div className="inline-flex gap-0.5 rounded-[9px] bg-sunken p-[3px]">
      {segments.map((s) => {
        const active = s.value === value;
        return (
          <button
            key={s.value}
            type="button"
            onClick={() => onChange(s.value)}
            className={`flex items-center gap-1.5 rounded-[7px] px-3 py-1.5 text-[12.5px] font-semibold transition-colors duration-150 ${
              active ? "bg-surface text-fg" : "text-fg2 hover:text-fg"
            }`}
            style={active ? { boxShadow: "0 1px 2px rgba(0,0,0,.10)" } : undefined}
          >
            {s.label}
            {s.count != null && (
              <span className="font-mono text-[10.5px] font-bold text-fg3">
                {s.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
