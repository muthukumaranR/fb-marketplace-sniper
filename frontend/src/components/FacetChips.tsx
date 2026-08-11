import type { MatchDetails } from "../api";

interface Props {
  details: MatchDetails | null;
  unscored: boolean;
  size?: "row" | "drawer";
}

/**
 * Matched / missed facet chips, plus the excluded and not-yet-scored variants.
 * A null `details` with unscored=false means match_details failed to parse — we
 * render nothing rather than blanking the row.
 */
export default function FacetChips({ details, unscored, size = "row" }: Props) {
  const pad = size === "drawer" ? "px-2 py-1 text-[10.5px]" : "px-1.5 py-0.5 text-[10px]";
  const base = `inline-flex items-center rounded-[5px] font-mono font-bold tracking-[.06em] ${pad}`;

  if (unscored) {
    return (
      <span className={`${base} bg-sunken text-fg3`}>not yet scored</span>
    );
  }

  if (!details) return null;

  if (details.excluded_by) {
    return (
      <span className={`${base} bg-excluded-bg text-excluded-fg`}>
        EXCLUDED · {details.excluded_by}
      </span>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-1">
      {details.matched.map((f) => (
        <span key={`m-${f}`} className={`${base} bg-matched-bg text-matched-fg`}>
          ✓ {f}
        </span>
      ))}
      {details.missed.map((f) => (
        <span
          key={`x-${f}`}
          className={`${base} border border-line bg-transparent text-fg3`}
        >
          ✗ {f}
        </span>
      ))}
    </div>
  );
}
