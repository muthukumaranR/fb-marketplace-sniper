import type { Listing } from "../api";

const styles: Record<Listing["deal_quality"], { cls: string; label: string } | null> = {
  great: { cls: "bg-great-bg text-great-fg", label: "GREAT" },
  good: { cls: "bg-good-bg text-good-fg", label: "GOOD" },
  fair: { cls: "bg-fair-bg text-fair-fg", label: "FAIR" },
  none: null,
};

/** Deal-quality pill. `none` renders nothing, per the handoff. */
export default function DealBadge({ quality }: { quality: Listing["deal_quality"] }) {
  const s = styles[quality];
  if (!s) return null;
  return (
    <span
      className={`inline-flex items-center rounded-[5px] px-1.5 py-0.5 font-mono text-[10px] font-bold tracking-[.06em] ${s.cls}`}
    >
      {s.label}
    </span>
  );
}
