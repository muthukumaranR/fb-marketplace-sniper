import {
  isExcluded,
  isUnscored,
  parseApiDate,
  parseMatchDetails,
  proxyImageUrl,
  type Listing,
} from "../api";
import DealBadge from "./DealBadge";
import FacetChips from "./FacetChips";
import PriceVsFair from "./PriceVsFair";
import ScoreBar from "./ScoreBar";

export type Density = "comfy" | "dense";

interface Props {
  listing: Listing;
  density: Density;
  saved: boolean;
  dismissed: boolean;
  onOpen: (listing: Listing) => void;
  onToggleSave: (id: number) => void;
  onToggleDismiss: (id: number) => void;
}

function formatSeen(iso: string): string {
  const d = parseApiDate(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function ListingRow({
  listing,
  density,
  saved,
  dismissed,
  onOpen,
  onToggleSave,
  onToggleDismiss,
}: Props) {
  const dense = density === "dense";
  const excluded = isExcluded(listing);
  const unscored = isUnscored(listing);
  const details = parseMatchDetails(listing.match_details);
  const img = proxyImageUrl(listing.thumbnail);

  // Save/dismiss must not open the drawer.
  const stop = (fn: () => void) => (e: React.MouseEvent) => {
    e.stopPropagation();
    fn();
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onOpen(listing)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpen(listing);
        }
      }}
      className={`flex cursor-pointer items-center gap-[14px] rounded-xl border border-line bg-surface transition-colors duration-150 hover:border-line-hover ${
        dense ? "px-3 py-2.5" : "p-[14px]"
      }`}
      style={excluded ? { opacity: 0.55 } : undefined}
    >
      {/* Thumbnail */}
      <div
        className="flex flex-shrink-0 items-center justify-center overflow-hidden rounded-[9px] bg-sunken font-mono text-[10px] font-bold text-fg3"
        style={{ width: dense ? 52 : 72, height: dense ? 52 : 72 }}
      >
        {img ? (
          <img
            src={img}
            alt=""
            className="h-full w-full object-cover"
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = "none";
            }}
          />
        ) : (
          "IMG"
        )}
      </div>

      {/* Main */}
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex flex-wrap items-center gap-1.5">
          <span className="inline-flex items-center rounded-[5px] bg-sunken px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-[.06em] text-fg2">
            {listing.item_name}
          </span>
          <DealBadge quality={listing.deal_quality} />
          {excluded && details?.excluded_by && (
            <span className="inline-flex items-center rounded-[5px] bg-excluded-bg px-1.5 py-0.5 font-mono text-[10px] font-bold tracking-[.06em] text-excluded-fg">
              EXCLUDED · {details.excluded_by}
            </span>
          )}
        </div>

        <h3
          className={`truncate font-semibold text-fg ${
            dense ? "text-[13.5px]" : "text-[15px] leading-[1.35]"
          }`}
        >
          {listing.title}
        </h3>

        {!excluded && (
          <div className="mt-1">
            <FacetChips details={details} unscored={unscored} />
          </div>
        )}

        <div className="mt-1 text-[11.5px] text-fg3">
          {listing.location ? `${listing.location} · ` : ""}
          {formatSeen(listing.first_seen)}
        </div>
      </div>

      {/* Score */}
      <div className="hidden flex-shrink-0 sm:block" style={{ width: 150 }}>
        <ScoreBar listing={listing} />
      </div>

      {/* Price */}
      <div className="flex-shrink-0 text-right" style={{ width: 118 }}>
        <div
          className={`font-mono font-bold text-fg ${dense ? "text-[17px]" : "text-[20px]"}`}
        >
          ${listing.price.toFixed(0)}
        </div>
        <div className="mt-1">
          <PriceVsFair listing={listing} />
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-shrink-0 flex-col gap-1">
        <button
          type="button"
          aria-label={saved ? "Unsave" : "Save"}
          onClick={stop(() => onToggleSave(listing.id))}
          className="flex h-7 w-7 items-center justify-center rounded-[7px] border border-line text-[12px] transition-colors duration-150 hover:border-line-hover"
          style={saved ? { background: "var(--color-strong)", color: "var(--color-fg)" } : undefined}
        >
          ★
        </button>
        <button
          type="button"
          aria-label={dismissed ? "Restore" : "Dismiss"}
          onClick={stop(() => onToggleDismiss(listing.id))}
          className="flex h-7 w-7 items-center justify-center rounded-[7px] border border-line text-[12px] transition-colors duration-150 hover:border-line-hover"
          style={dismissed ? { background: "var(--color-weak)", color: "#fff" } : undefined}
        >
          ✕
        </button>
      </div>
    </div>
  );
}
