import type { Listing } from "../api";
import ListingRow, { type Density } from "./ListingRow";

interface Props {
  listings: Listing[];
  density: Density;
  loading: boolean;
  error: string | null;
  saved: Record<number, boolean>;
  dismissed: Record<number, boolean>;
  emptyKicker: string;
  emptyTitle: string;
  emptyBody: string;
  onClearFilters?: () => void;
  onOpen: (listing: Listing) => void;
  onToggleSave: (id: number) => void;
  onToggleDismiss: (id: number) => void;
}

function SkeletonRow() {
  return (
    <div className="flex items-center gap-[14px] rounded-xl border border-line bg-surface p-[14px]">
      <div className="shimmer relative h-[72px] w-[72px] flex-shrink-0 overflow-hidden rounded-[9px] bg-sunken" />
      <div className="min-w-0 flex-1 space-y-2">
        <div className="shimmer relative h-3 w-24 overflow-hidden rounded bg-sunken" />
        <div className="shimmer relative h-3.5 w-3/4 overflow-hidden rounded bg-sunken" />
        <div className="shimmer relative h-3 w-1/2 overflow-hidden rounded bg-sunken" />
      </div>
      <div className="shimmer relative h-10 w-[150px] flex-shrink-0 overflow-hidden rounded bg-sunken" />
      <div className="shimmer relative h-10 w-[118px] flex-shrink-0 overflow-hidden rounded bg-sunken" />
    </div>
  );
}

export default function ListingList({
  listings,
  density,
  loading,
  error,
  saved,
  dismissed,
  emptyKicker,
  emptyTitle,
  emptyBody,
  onClearFilters,
  onOpen,
  onToggleSave,
  onToggleDismiss,
}: Props) {
  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }, (_, i) => (
          <SkeletonRow key={i} />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-[14px] border border-dashed border-line p-12 text-center">
        <p className="font-mono text-[10px] font-bold tracking-[.1em] text-weak">
          ERROR
        </p>
        <p className="mt-2 text-[15px] font-semibold text-fg">
          Could not load listings
        </p>
        <p className="mt-1 text-[13px] text-fg2">{error}</p>
      </div>
    );
  }

  if (listings.length === 0) {
    return (
      <div className="rounded-[14px] border border-dashed border-line p-12 text-center">
        <p className="font-mono text-[10px] font-bold tracking-[.1em] text-fg3">
          {emptyKicker}
        </p>
        <p className="mt-2 text-[15px] font-semibold text-fg">{emptyTitle}</p>
        <p className="mt-1 text-[13px] text-fg2">{emptyBody}</p>
        {onClearFilters && (
          <button
            type="button"
            onClick={onClearFilters}
            className="mt-4 rounded-lg bg-fg px-4 py-2 text-[12.5px] font-bold text-bg"
          >
            Clear all filters
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {listings.map((l) => (
        <ListingRow
          key={l.id}
          listing={l}
          density={density}
          saved={!!saved[l.id]}
          dismissed={!!dismissed[l.id]}
          onOpen={onOpen}
          onToggleSave={onToggleSave}
          onToggleDismiss={onToggleDismiss}
        />
      ))}
    </div>
  );
}
