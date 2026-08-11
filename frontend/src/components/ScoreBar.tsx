import { finalScore, priceScore, type Listing } from "../api";

/** Score → signal color. Matches the handoff bands: ≥.5 strong, ≥.25 middling. */
export function scoreColor(score: number): string {
  if (score >= 0.5) return "var(--color-strong)";
  if (score >= 0.25) return "var(--color-middling)";
  return "var(--color-weak)";
}

interface Props {
  listing: Listing;
  /** Row uses 6px; the drawer uses 7px (10px for the final bar). */
  height?: number;
}

/**
 * Match percentage, the colored bar, and the `rel × price` factor line.
 * Owns the unscored rendering: an em dash and a zero-width bar, never 0% or NaN.
 */
export default function ScoreBar({ listing, height = 6 }: Props) {
  const rel = listing.relevance_score;
  const price = priceScore(listing);
  const final = finalScore(listing);
  const unscored = rel == null;

  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-mono text-[10px] font-bold tracking-[.06em] text-fg3">
          {unscored ? "UNSCORED" : "MATCH"}
        </span>
        <span
          className="font-mono text-[13px] font-bold"
          style={{ color: unscored ? "var(--color-fg3)" : scoreColor(rel) }}
        >
          {unscored ? "—" : `${Math.round(rel * 100)}%`}
        </span>
      </div>

      <div
        className="mt-1.5 w-full overflow-hidden rounded-full bg-sunken"
        style={{ height }}
      >
        <div
          className="h-full rounded-full transition-[width] duration-300"
          style={{
            width: unscored ? 0 : `${Math.round(rel * 100)}%`,
            background: unscored ? "transparent" : scoreColor(rel),
          }}
        />
      </div>

      <div className="mt-1 font-mono text-[10px] text-fg3">
        {unscored || price == null || final == null ? (
          "not yet scored"
        ) : (
          <>
            rel {rel.toFixed(2)} &nbsp;×&nbsp; price {price.toFixed(2)}
          </>
        )}
      </div>
    </div>
  );
}
