import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  api,
  isExcluded,
  isUnscored,
  type Listing,
  type ListingSort,
  type WatchItem,
} from "../api";
import ListingDrawer from "../components/ListingDrawer";
import ListingList from "../components/ListingList";
import type { Density } from "../components/ListingRow";
import SegmentedControl from "../components/SegmentedControl";

type Bucket = "results" | "saved" | "dismissed";

// Labels map directly onto the backend `sort` values, so the select can only
// ever emit something the API accepts (an unknown value would 422).
const SORT_OPTIONS: { value: ListingSort; label: string }[] = [
  { value: "final", label: "Best match" },
  { value: "relevance", label: "Most relevant" },
  { value: "deal", label: "Biggest discount" },
  { value: "price", label: "Lowest price" },
  { value: "recent", label: "Newest" },
];

const DEAL_QUALITIES: { value: string; label: string }[] = [
  { value: "great", label: "Great" },
  { value: "good", label: "Good" },
  { value: "fair", label: "Fair" },
  { value: "none", label: "Priced normal" },
];

const MAX_PRICE = 2500;

interface Props {
  saved: Record<number, boolean>;
  dismissed: Record<number, boolean>;
  onToggleSave: (id: number) => void;
  onToggleDismiss: (id: number) => void;
}

export default function Listings({
  saved,
  dismissed,
  onToggleSave,
  onToggleDismiss,
}: Props) {
  const [searchParams] = useSearchParams();
  const [allListings, setAllListings] = useState<Listing[]>([]);
  const [watchItems, setWatchItems] = useState<WatchItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Only `sort` round-trips to the server; every other control filters the
  // fetched page client-side.
  const [sort, setSort] = useState<ListingSort>("final");

  const [query, setQuery] = useState("");
  const [items, setItems] = useState<string[]>(() => {
    const fromUrl = searchParams.get("item");
    return fromUrl ? [fromUrl] : [];
  });
  const [dealQualities, setDealQualities] = useState<string[]>([]);
  const [minRel, setMinRel] = useState(0);
  const [maxPrice, setMaxPrice] = useState(MAX_PRICE);
  const [showExcluded, setShowExcluded] = useState(false);
  const [showUnscored, setShowUnscored] = useState(true);
  const [hideDismissed, setHideDismissed] = useState(true);
  const [bucket, setBucket] = useState<Bucket>("results");
  const [density, setDensity] = useState<Density>("comfy");
  const [detail, setDetail] = useState<Listing | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [l, w] = await Promise.all([
        api.getListings({ limit: 500, sort }),
        api.getWatchlist(),
      ]);
      setAllListings(l);
      setWatchItems(w);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [sort]);

  // Refetches whenever sort changes — the server sorts before LIMIT, so this
  // returns the globally best N rather than reordering whatever arrived.
  useEffect(() => {
    load();
  }, [load]);

  const countsByItem = useMemo(() => {
    const c: Record<string, number> = {};
    for (const l of allListings) c[l.item_name] = (c[l.item_name] || 0) + 1;
    return c;
  }, [allListings]);

  const bucketed = useMemo(() => {
    if (bucket === "saved") return allListings.filter((l) => saved[l.id]);
    if (bucket === "dismissed") return allListings.filter((l) => dismissed[l.id]);
    return hideDismissed
      ? allListings.filter((l) => !dismissed[l.id])
      : allListings;
  }, [allListings, bucket, saved, dismissed, hideDismissed]);

  const filtered = useMemo(() => {
    let result = bucketed;

    if (query.trim()) {
      const q = query.toLowerCase();
      result = result.filter(
        (l) =>
          l.title.toLowerCase().includes(q) ||
          l.item_name.toLowerCase().includes(q)
      );
    }
    if (items.length) {
      result = result.filter((l) => items.includes(l.item_name));
    }
    if (dealQualities.length) {
      result = result.filter((l) => dealQualities.includes(l.deal_quality));
    }
    if (maxPrice < MAX_PRICE) {
      result = result.filter((l) => l.price <= maxPrice);
    }
    if (!showExcluded) {
      result = result.filter((l) => !isExcluded(l));
    }
    // A min-relevance floor has nothing to compare an unscored row against, so
    // any floor above zero necessarily excludes them.
    if (minRel > 0) {
      result = result.filter(
        (l) => !isUnscored(l) && (l.relevance_score ?? 0) * 100 >= minRel
      );
    } else if (!showUnscored) {
      result = result.filter((l) => !isUnscored(l));
    }

    return result;
  }, [
    bucketed,
    query,
    items,
    dealQualities,
    maxPrice,
    showExcluded,
    showUnscored,
    minRel,
  ]);

  const clearFilters = useCallback(() => {
    setQuery("");
    setItems([]);
    setDealQualities([]);
    setMinRel(0);
    setMaxPrice(MAX_PRICE);
    setShowExcluded(false);
    setShowUnscored(true);
    setHideDismissed(true);
    setBucket("results");
  }, []);

  const toggleIn = (list: string[], value: string) =>
    list.includes(value) ? list.filter((v) => v !== value) : [...list, value];

  if (!loading && watchItems.length === 0) {
    return (
      <div className="rounded-[14px] border border-dashed border-line p-16 text-center">
        <p className="text-[15px] font-semibold text-fg">No watchlist items yet</p>
        <p className="mt-1 text-[13px] text-fg2">
          Add items to your watchlist first, then run a scan to find listings
        </p>
        <Link
          to="/watchlist"
          className="mt-4 inline-block rounded-lg bg-fg px-4 py-2 text-[12.5px] font-bold text-bg"
        >
          Go to Watchlist
        </Link>
      </div>
    );
  }

  const emptyCopy =
    bucket === "saved"
      ? {
          kicker: "NOTHING SAVED",
          title: "No saved listings",
          body: "Star a listing to keep it here.",
        }
      : bucket === "dismissed"
        ? {
            kicker: "NOTHING DISMISSED",
            title: "No dismissed listings",
            body: "Dismissed listings are hidden from Results but never deleted.",
          }
        : {
            kicker: "NO MATCHES",
            title: "Nothing matches these filters",
            body: "Try widening the relevance floor or clearing a facet.",
          };

  return (
    <div className="grid gap-0 md:grid-cols-[264px_minmax(0,1fr)]">
      {/* Filter rail */}
      <aside className="hidden border-r border-line bg-surface p-[18px] md:block">
        <div className="sticky top-[74px] space-y-[22px]">
          <input
            type="text"
            placeholder="Search listings..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full rounded-lg border border-line bg-sunken px-3 py-2 text-[13px] text-fg outline-none placeholder:text-fg3 focus:border-line-hover"
          />

          {/* Watch items */}
          <div>
            <div className="mb-2 flex items-center justify-between">
              <span className="font-mono text-[10px] font-bold uppercase tracking-[.1em] text-fg3">
                Watch item
              </span>
              {items.length > 0 && (
                <button
                  type="button"
                  onClick={() => setItems([])}
                  className="text-[11px] text-fg2 hover:text-fg"
                >
                  reset
                </button>
              )}
            </div>
            <div className="space-y-0.5">
              {watchItems.map((w) => {
                const on = items.includes(w.name);
                return (
                  <button
                    key={w.id}
                    type="button"
                    onClick={() => setItems((l) => toggleIn(l, w.name))}
                    className="flex w-full items-center gap-2 rounded-[7px] px-2 py-1.5 text-left transition-colors duration-150 hover:bg-sunken"
                  >
                    <span
                      className="flex h-3 w-3 flex-shrink-0 items-center justify-center rounded-[3px] border border-line text-[8px] text-bg"
                      style={on ? { background: "var(--color-fg)", borderColor: "var(--color-fg)" } : undefined}
                    >
                      {on ? "✓" : ""}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-[13px] text-fg">
                      {w.name}
                    </span>
                    <span className="font-mono text-[11px] text-fg3">
                      {countsByItem[w.name] ?? 0}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Deal quality */}
          <div>
            <div className="mb-2 font-mono text-[10px] font-bold uppercase tracking-[.1em] text-fg3">
              Deal quality
            </div>
            <div className="flex flex-wrap gap-1.5">
              {DEAL_QUALITIES.map((d) => {
                const on = dealQualities.includes(d.value);
                return (
                  <button
                    key={d.value}
                    type="button"
                    onClick={() => setDealQualities((l) => toggleIn(l, d.value))}
                    className={`whitespace-nowrap rounded-[5px] border px-2 py-1 text-[11.5px] font-medium transition-colors duration-150 ${
                      on
                        ? "border-fg bg-fg text-bg"
                        : "border-line bg-surface text-fg2 hover:border-line-hover"
                    }`}
                  >
                    {d.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Min relevance */}
          <div>
            <div className="mb-2 flex items-center justify-between">
              <span className="font-mono text-[10px] font-bold uppercase tracking-[.1em] text-fg3">
                Min relevance
              </span>
              <span className="font-mono text-[11px] font-bold text-fg">
                {minRel === 0 ? "off" : `${minRel}%`}
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={100}
              step={5}
              value={minRel}
              onChange={(e) => setMinRel(Number(e.target.value))}
            />
            <p className="mt-1.5 text-[11px] leading-snug text-fg3">
              {minRel === 0
                ? "Showing everything, including unscored rows."
                : `Hides listings scoring under ${minRel}% — and all unscored rows, since they have no score to compare.`}
            </p>
          </div>

          {/* Max price */}
          <div>
            <div className="mb-2 flex items-center justify-between">
              <span className="font-mono text-[10px] font-bold uppercase tracking-[.1em] text-fg3">
                Max price
              </span>
              <span className="font-mono text-[11px] font-bold text-fg">
                {maxPrice >= MAX_PRICE ? "any" : `$${maxPrice}`}
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={MAX_PRICE}
              step={50}
              value={maxPrice}
              onChange={(e) => setMaxPrice(Number(e.target.value))}
            />
          </div>

          {/* Show */}
          <div>
            <div className="mb-2 font-mono text-[10px] font-bold uppercase tracking-[.1em] text-fg3">
              Show
            </div>
            <div className="space-y-1">
              {[
                { label: "Excluded listings", on: showExcluded, set: setShowExcluded },
                { label: "Unscored listings", on: showUnscored, set: setShowUnscored },
                { label: "Hide dismissed", on: hideDismissed, set: setHideDismissed },
              ].map((c) => (
                <button
                  key={c.label}
                  type="button"
                  onClick={() => c.set(!c.on)}
                  className="flex w-full items-center gap-2 rounded-[7px] px-2 py-1.5 text-left transition-colors duration-150 hover:bg-sunken"
                >
                  <span
                    className="flex h-3 w-3 flex-shrink-0 items-center justify-center rounded-[3px] border border-line text-[8px] text-bg"
                    style={c.on ? { background: "var(--color-fg)", borderColor: "var(--color-fg)" } : undefined}
                  >
                    {c.on ? "✓" : ""}
                  </span>
                  <span className="text-[13px] text-fg">{c.label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </aside>

      {/* Results */}
      <section className="min-w-0 p-[18px] md:p-[22px]">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <SegmentedControl<Bucket>
            value={bucket}
            onChange={setBucket}
            segments={[
              { value: "results", label: "Results", count: bucketed.length },
              {
                value: "saved",
                label: "Saved",
                count: Object.keys(saved).length,
              },
              {
                value: "dismissed",
                label: "Dismissed",
                count: Object.keys(dismissed).length,
              },
            ]}
          />

          <div className="ml-auto flex items-center gap-3">
            <span className="font-mono text-[11px] text-fg3">
              {filtered.length} / {allListings.length}
            </span>

            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as ListingSort)}
              className="rounded-lg border border-line bg-surface px-2.5 py-1.5 text-[12.5px] text-fg outline-none focus:border-line-hover"
            >
              {SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>

            <SegmentedControl<Density>
              value={density}
              onChange={setDensity}
              segments={[
                { value: "comfy", label: "Comfy" },
                { value: "dense", label: "Dense" },
              ]}
            />
          </div>
        </div>

        <ListingList
          listings={filtered}
          density={density}
          loading={loading}
          error={error}
          saved={saved}
          dismissed={dismissed}
          emptyKicker={emptyCopy.kicker}
          emptyTitle={emptyCopy.title}
          emptyBody={emptyCopy.body}
          onClearFilters={bucket === "results" ? clearFilters : undefined}
          onOpen={setDetail}
          onToggleSave={onToggleSave}
          onToggleDismiss={onToggleDismiss}
        />
      </section>

      {detail && (
        <ListingDrawer
          listing={detail}
          saved={!!saved[detail.id]}
          dismissed={!!dismissed[detail.id]}
          onClose={() => setDetail(null)}
          onToggleSave={onToggleSave}
          onToggleDismiss={onToggleDismiss}
        />
      )}
    </div>
  );
}
