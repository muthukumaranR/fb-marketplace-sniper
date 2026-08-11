import { useEffect } from "react";
import {
  finalScore,
  isUnscored,
  parseApiDate,
  parseMatchDetails,
  priceScore,
  proxyImageUrl,
  type Listing,
} from "../api";
import DealBadge from "./DealBadge";
import FacetChips from "./FacetChips";
import { scoreColor } from "./ScoreBar";

interface Props {
  listing: Listing;
  saved: boolean;
  dismissed: boolean;
  /** Global NOTIFY_MIN_RELEVANCE, until per-item thresholds exist server-side. */
  notifyThreshold?: number;
  onClose: () => void;
  onToggleSave: (id: number) => void;
  onToggleDismiss: (id: number) => void;
}

function Bar({
  label,
  hint,
  value,
  height,
  bold,
}: {
  label: string;
  hint: string;
  value: number | null;
  height: number;
  bold?: boolean;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <span
          className={`text-[12px] text-fg ${bold ? "font-bold" : "font-medium"}`}
        >
          {label}
        </span>
        <span className="font-mono text-[12px] font-bold text-fg">
          {value == null ? "—" : value.toFixed(2)}
        </span>
      </div>
      <div
        className="mt-1.5 w-full overflow-hidden rounded-full bg-sunken"
        style={{ height }}
      >
        <div
          className="h-full rounded-full transition-[width] duration-300"
          style={{
            width: value == null ? 0 : `${Math.round(value * 100)}%`,
            background: value == null ? "transparent" : scoreColor(value),
          }}
        />
      </div>
      <p className="mt-1 text-[11px] text-fg3">{hint}</p>
    </div>
  );
}

export default function ListingDrawer({
  listing,
  saved,
  dismissed,
  notifyThreshold = 0.5,
  onClose,
  onToggleSave,
  onToggleDismiss,
}: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const details = parseMatchDetails(listing.match_details);
  const unscored = isUnscored(listing);
  const rel = listing.relevance_score;
  const ps = priceScore(listing);
  const fs = finalScore(listing);
  const img = proxyImageUrl(listing.thumbnail);
  const fair = listing.fair_price;
  const under = fair && fair > 0 ? fair - listing.price : null;

  const alertFires = !unscored && (rel ?? 0) >= notifyThreshold;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div
        className="absolute inset-0"
        style={{ background: "rgba(8,9,12,.5)" }}
        onClick={onClose}
      />

      <aside className="drawer-in relative flex h-full w-[460px] max-w-[94vw] flex-col overflow-y-auto bg-surface">
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-line bg-surface px-5 py-3">
          <span className="font-mono text-[10px] font-bold tracking-[.1em] text-fg3">
            LISTING DETAIL
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="flex h-7 w-7 items-center justify-center rounded-[7px] border border-line text-fg2 hover:border-line-hover hover:text-fg"
          >
            ✕
          </button>
        </header>

        <div className="space-y-5 px-5 py-4">
          <div className="flex h-[190px] items-center justify-center overflow-hidden rounded-[9px] bg-sunken font-mono text-[11px] text-fg3">
            {img ? (
              <img
                src={img}
                alt=""
                className="h-full w-full object-cover"
                onError={(e) => {
                  // Expired FB CDN signatures 502 through the proxy; fall back
                  // to the placeholder rather than a broken-image icon.
                  (e.target as HTMLImageElement).style.display = "none";
                }}
              />
            ) : (
              "IMG"
            )}
          </div>

          <div>
            <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
              <DealBadge quality={listing.deal_quality} />
              {details?.excluded_by && (
                <span className="inline-flex items-center rounded-[5px] bg-excluded-bg px-2 py-1 font-mono text-[10.5px] font-bold tracking-[.06em] text-excluded-fg">
                  EXCLUDED · {details.excluded_by}
                </span>
              )}
            </div>
            <h2 className="text-[19px] font-bold leading-tight tracking-[-.01em] text-fg">
              {listing.title}
            </h2>
            <p className="mt-1 text-[12px] text-fg3">
              {listing.location ? `${listing.location} · ` : ""}
              {parseApiDate(listing.first_seen).toLocaleString(undefined, {
                month: "short",
                day: "numeric",
                hour: "numeric",
                minute: "2-digit",
              })}
            </p>
          </div>

          {/* Price block */}
          <div className="rounded-[13px] bg-sunken p-4">
            <div className="flex items-end justify-between">
              <div>
                <p className="font-mono text-[10px] font-bold tracking-[.1em] text-fg3">
                  ASKING
                </p>
                <p className="font-mono text-[30px] font-bold tracking-[-.03em] text-fg">
                  ${listing.price.toFixed(0)}
                </p>
              </div>
              <div className="text-right">
                <p className="font-mono text-[10px] font-bold tracking-[.1em] text-fg3">
                  FAIR USED
                </p>
                <p className="font-mono text-[15px] font-bold text-fg2">
                  {fair && fair > 0 ? `$${fair.toFixed(0)}` : "—"}
                </p>
              </div>
            </div>

            {fair && fair > 0 && (
              <>
                <div className="relative mt-3 h-[7px] w-full overflow-hidden rounded-full bg-track-deep">
                  <div
                    className="h-full rounded-full transition-[width] duration-300"
                    style={{
                      width: `${Math.min(100, (listing.price / fair) * 100)}%`,
                      background:
                        listing.price > fair
                          ? "var(--color-weak)"
                          : (ps ?? 0) >= 0.3
                            ? "var(--color-strong)"
                            : "var(--color-middling)",
                    }}
                  />
                  <div className="absolute right-0 top-0 h-full w-0.5 bg-fg2" />
                </div>
                {under != null && under > 0 && (
                  <p className="mt-2 font-mono text-[11.5px] text-fg2">
                    ${under.toFixed(0)} below fair used price (
                    {Math.round((under / fair) * 100)}% under)
                  </p>
                )}
              </>
            )}
          </div>

          {/* Why it ranks here */}
          <div>
            <p className="mb-3 font-mono text-[10px] font-bold uppercase tracking-[.1em] text-fg3">
              Why it ranks here
            </p>
            <div className="space-y-4">
              <Bar
                label="Relevance"
                hint="Facet match against the extracted spec."
                value={rel}
                height={7}
              />
              <Bar
                label="Price attractiveness"
                hint="1 − price ÷ fair price, clamped to [0,1]."
                value={ps}
                height={7}
              />
              <Bar
                label="Final score"
                hint="Relevance × price. They multiply so a great price on the wrong item collapses to ~0."
                value={fs}
                height={10}
                bold
              />
            </div>
          </div>

          {/* Facet match */}
          <div>
            <p className="mb-2 font-mono text-[10px] font-bold uppercase tracking-[.1em] text-fg3">
              Facet match
            </p>
            <FacetChips details={details} unscored={unscored} size="drawer" />
            <p className="mt-2 text-[11.5px] leading-snug text-fg3">
              {details?.excluded_by ? (
                <>
                  Disqualified by the exclusion term &ldquo;{details.excluded_by}
                  &rdquo; — relevance forced to 0 regardless of price.
                </>
              ) : unscored ? (
                <>
                  This listing predates relevance scoring. Rescans won&rsquo;t
                  backfill it — only new listings get scored.
                </>
              ) : null}
            </p>
          </div>

          {/* Alert panel */}
          <div
            className="rounded-[13px] border p-3"
            style={
              alertFires
                ? {
                    borderColor: "var(--color-matched-bg)",
                    background: "var(--color-matched-bg)",
                  }
                : { borderColor: "var(--color-line)", background: "var(--color-sunken)" }
            }
          >
            <p
              className="text-[12.5px] font-bold"
              style={{ color: alertFires ? "var(--color-matched-fg)" : "var(--color-fg2)" }}
            >
              {unscored
                ? "Unscored listings never notify"
                : alertFires
                  ? "Email alert would fire"
                  : "No email for this listing"}
            </p>
            <p className="mt-1 text-[11.5px] leading-snug text-fg3">
              {unscored ? (
                "Without a relevance score there is nothing to compare against the threshold."
              ) : alertFires ? (
                <>
                  Relevance {Math.round((rel ?? 0) * 100)}% clears the{" "}
                  {Math.round(notifyThreshold * 100)}% threshold for{" "}
                  {listing.item_name}.
                </>
              ) : (
                <>
                  Relevance {Math.round((rel ?? 0) * 100)}% is under the{" "}
                  {Math.round(notifyThreshold * 100)}% threshold. The listing is
                  stored and shown, just not emailed.
                </>
              )}
            </p>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2 pb-4">
            <a
              href={listing.link}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 rounded-[10px] bg-fg px-4 py-2.5 text-center text-[12.5px] font-bold text-bg"
            >
              Open on Marketplace ↗
            </a>
            <button
              type="button"
              onClick={() => onToggleSave(listing.id)}
              className="rounded-[10px] border border-line px-3 py-2.5 text-[12.5px] font-semibold text-fg2 hover:border-line-hover"
              style={saved ? { background: "var(--color-strong)", color: "var(--color-fg)" } : undefined}
            >
              ★ Save
            </button>
            <button
              type="button"
              onClick={() => onToggleDismiss(listing.id)}
              className="rounded-[10px] border border-line px-3 py-2.5 text-[12.5px] font-semibold text-fg2 hover:border-line-hover"
              style={dismissed ? { background: "var(--color-weak)", color: "#fff" } : undefined}
            >
              Dismiss
            </button>
          </div>
        </div>
      </aside>
    </div>
  );
}
