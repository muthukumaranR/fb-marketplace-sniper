import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  isUnscored,
  parseApiDate,
  type Listing,
  type PriceEstimate,
  type WatchItem,
} from "../api";
import { useShell } from "../shell";

/**
 * Low / median / high on one shared scale, padded so the end labels stay inside
 * the box. Labels are positioned by percentage and centered on their own offset
 * — laying them out with space-between would not line them up with the band.
 */
function FairPriceChart({ estimate }: { estimate: PriceEstimate }) {
  const { median_price: med, low_price: low, high_price: high } = estimate;
  const lo = low ?? med;
  const hi = high ?? med;
  const span = Math.max(hi - lo, 1);
  const pad = span * 0.35;
  const min = lo - pad;
  const max = hi + pad;
  const pct = (v: number) => ((v - min) / (max - min)) * 100;

  return (
    <div className="relative h-[52px] w-full">
      <span
        className="absolute top-0 whitespace-nowrap font-mono text-[11px] font-bold text-fg"
        style={{ left: `${pct(med)}%`, transform: "translateX(-50%)" }}
      >
        ${med.toFixed(0)}
      </span>

      <div className="absolute top-[22px] h-[6px] w-full rounded-full bg-sunken">
        <div
          className="absolute h-full rounded-full"
          style={{
            left: `${pct(lo)}%`,
            width: `${pct(hi) - pct(lo)}%`,
            background: "var(--color-range-fill)",
          }}
        />
        <div
          className="absolute h-full w-[3px] rounded-full bg-fg"
          style={{ left: `${pct(med)}%`, transform: "translateX(-50%)" }}
        />
      </div>

      <span
        className="absolute top-[34px] whitespace-nowrap font-mono text-[10.5px] text-fg3"
        style={{ left: `${pct(lo)}%`, transform: "translateX(-50%)" }}
      >
        ${lo.toFixed(0)}
      </span>
      <span
        className="absolute top-[34px] whitespace-nowrap font-mono text-[10.5px] text-fg3"
        style={{ left: `${pct(hi)}%`, transform: "translateX(-50%)" }}
      >
        ${hi.toFixed(0)}
      </span>
    </div>
  );
}

export default function Watchlist() {
  const { listings, setup, reload } = useShell();
  const [items, setItems] = useState<WatchItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [location, setLocation] = useState("");
  const [radius, setRadius] = useState("");
  const [adding, setAdding] = useState(false);
  const [prices, setPrices] = useState<Record<string, PriceEstimate>>({});
  const [loadingPrices, setLoadingPrices] = useState<Set<string>>(new Set());
  const [priceErrors, setPriceErrors] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    try {
      setItems(await api.getWatchlist());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const byItem = useMemo(() => {
    const g: Record<string, Listing[]> = {};
    for (const l of listings) (g[l.item_name] ||= []).push(l);
    return g;
  }, [listings]);

  const fetchPrice = async (itemName: string) => {
    setLoadingPrices((prev) => new Set(prev).add(itemName));
    setPriceErrors((prev) => {
      const next = { ...prev };
      delete next[itemName];
      return next;
    });
    try {
      const est = await api.getPrice(itemName);
      setPrices((prev) => ({ ...prev, [itemName]: est }));
    } catch (e) {
      setPriceErrors((prev) => ({ ...prev, [itemName]: String(e) }));
    } finally {
      setLoadingPrices((prev) => {
        const next = new Set(prev);
        next.delete(itemName);
        return next;
      });
    }
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setAdding(true);
    try {
      const item = await api.addWatchItem({
        name: name.trim(),
        max_price: maxPrice ? parseFloat(maxPrice) : null,
        location: location || null,
        radius: radius ? parseInt(radius) : null,
      });
      setName("");
      setMaxPrice("");
      setLocation("");
      setRadius("");
      await load();
      reload();
      fetchPrice(item.name);
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (id: number) => {
    await api.deleteWatchItem(id);
    await load();
    reload();
  };

  if (loading) {
    return <p className="py-12 text-center text-[13px] text-fg3">Loading…</p>;
  }

  const inputCls =
    "rounded-lg border border-line bg-sunken px-3 py-2 text-[13px] text-fg outline-none placeholder:text-fg3 focus:border-line-hover";

  return (
    <div className="mx-auto max-w-[940px] space-y-4 px-5 py-6">
      {/* Add form */}
      <section className="rounded-[13px] border border-line bg-surface p-5">
        <h2 className="text-[15px] font-bold text-fg">Watch something new</h2>
        <p className="mt-0.5 max-w-[600px] text-[12.5px] text-fg2">
          Be specific — the facet extractor turns your words into a match spec.
          &ldquo;PS5 disc 1TB&rdquo; beats &ldquo;playstation&rdquo;.
        </p>
        <form onSubmit={handleAdd} className="mt-4 flex flex-wrap gap-2">
          <input
            type="text"
            placeholder="What are you looking for?"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={`${inputCls} min-w-[240px] flex-1`}
            required
          />
          <input
            type="number"
            placeholder="Max $"
            value={maxPrice}
            onChange={(e) => setMaxPrice(e.target.value)}
            className={`${inputCls} w-24`}
          />
          <input
            type="text"
            placeholder="Location"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            className={`${inputCls} w-40`}
          />
          <input
            type="number"
            placeholder="Radius"
            value={radius}
            onChange={(e) => setRadius(e.target.value)}
            className={`${inputCls} w-24`}
          />
          <button
            type="submit"
            disabled={adding || !name.trim()}
            className={`rounded-lg px-5 py-2 text-[12.5px] font-bold transition-colors duration-150 ${
              adding || !name.trim()
                ? "cursor-not-allowed bg-sunken text-fg3"
                : "bg-fg text-bg"
            }`}
          >
            {adding ? "Adding…" : "Add"}
          </button>
        </form>
      </section>

      {items.length === 0 ? (
        <div className="rounded-[13px] border border-dashed border-line p-12 text-center">
          <p className="text-[13.5px] font-semibold text-fg">
            Your watchlist is empty
          </p>
          <p className="mt-1 text-[12.5px] text-fg2">
            Add items above to start monitoring deals.
          </p>
        </div>
      ) : (
        items.map((item) => {
          const pe = prices[item.name];
          const isLoading = loadingPrices.has(item.name);
          const priceError = priceErrors[item.name];
          const group = byItem[item.name] ?? [];
          const scoredGroup = group.filter((l) => !isUnscored(l));
          const threshold = setup?.notify_min_relevance ?? 0.5;
          const wouldEmail = scoredGroup.filter(
            (l) => (l.relevance_score ?? 0) >= threshold
          ).length;
          const strong = scoredGroup.filter(
            (l) => (l.relevance_score ?? 0) >= 0.5
          ).length;

          return (
            <section
              key={item.id}
              className="rounded-[13px] border border-line bg-surface p-5"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-[18px] font-bold tracking-[-.01em] text-fg">
                      {item.name}
                    </h3>
                    <span
                      className="rounded-[5px] px-1.5 py-0.5 font-mono text-[10px] font-bold tracking-[.06em]"
                      style={
                        strong > 0
                          ? {
                              background: "var(--color-matched-bg)",
                              color: "var(--color-matched-fg)",
                            }
                          : { background: "var(--color-sunken)", color: "var(--color-fg3)" }
                      }
                    >
                      {strong > 0 ? `${strong} STRONG` : "WATCHING"}
                    </span>
                  </div>
                  <p className="mt-1 font-mono text-[11.5px] text-fg3">
                    {item.location} · {item.radius} mi
                    {item.max_price ? ` · max $${item.max_price}` : ""} · added{" "}
                    {parseApiDate(item.created_at).toLocaleDateString(undefined, {
                      month: "short",
                      day: "numeric",
                    })}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => handleDelete(item.id)}
                  className="text-[12px] text-fg3 transition-colors duration-150 hover:text-[color:var(--color-weak)]"
                >
                  Remove
                </button>
              </div>

              <div className="mt-4 grid gap-5 border-t border-line pt-4 md:grid-cols-[minmax(0,1fr)_260px]">
                {/* Fair price */}
                <div>
                  <p className="mb-2 font-mono text-[10px] font-bold uppercase tracking-[.1em] text-fg3">
                    Fair used price
                  </p>
                  {isLoading ? (
                    <p className="text-[12.5px] text-fg3">Estimating…</p>
                  ) : pe ? (
                    <>
                      <FairPriceChart estimate={pe} />
                      <div className="mt-1 flex items-center gap-3 font-mono text-[10.5px] text-fg3">
                        <span>
                          {pe.source === "ebay"
                            ? `eBay · ${pe.sample_count} sold`
                            : "LLM estimate"}
                        </span>
                        <button
                          type="button"
                          onClick={() => fetchPrice(item.name)}
                          className="hover:text-fg"
                        >
                          refresh
                        </button>
                      </div>
                    </>
                  ) : priceError ? (
                    <div className="flex items-center gap-3">
                      <p className="text-[12.5px]" style={{ color: "var(--color-weak)" }}>
                        Price check failed
                      </p>
                      <button
                        type="button"
                        onClick={() => fetchPrice(item.name)}
                        className="font-mono text-[11px] text-fg2 hover:text-fg"
                      >
                        retry
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => fetchPrice(item.name)}
                      className="rounded-lg border border-line px-3 py-1.5 text-[12px] font-semibold text-fg2 hover:border-line-hover hover:text-fg"
                    >
                      Check fair market price
                    </button>
                  )}
                </div>

                {/* Relevance threshold */}
                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <span className="font-mono text-[10px] font-bold uppercase tracking-[.1em] text-fg3">
                      Alert threshold
                    </span>
                    <span className="font-mono text-[11px] font-bold text-fg">
                      {Math.round(threshold * 100)}%
                    </span>
                  </div>
                  {/*
                    Read-only: NOTIFY_MIN_RELEVANCE is a single global setting.
                    Per-item thresholds need a nullable column on `watchlist`
                    plus notifier support, so this shows the real global value
                    rather than faking per-item state.
                  */}
                  <input
                    type="range"
                    min={0}
                    max={100}
                    step={5}
                    value={Math.round(threshold * 100)}
                    disabled
                    readOnly
                    className="opacity-60"
                  />
                  <p className="mt-1.5 text-[11px] leading-snug text-fg3">
                    {scoredGroup.length === 0 ? (
                      "No scored listings for this item yet."
                    ) : (
                      <>
                        {wouldEmail} of {scoredGroup.length} scored listing
                        {scoredGroup.length === 1 ? "" : "s"} would email you.
                      </>
                    )}
                  </p>
                  <p className="mt-1 text-[10.5px] text-fg3">
                    Global setting — per-item thresholds are not implemented yet.
                  </p>
                </div>
              </div>
            </section>
          );
        })
      )}
    </div>
  );
}
