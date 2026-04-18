import { useCallback, useEffect, useState } from "react";
import { api, type PriceEstimate, type WatchItem } from "../api";

export default function Watchlist() {
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
      // Auto-fetch price for newly added item
      fetchPrice(item.name);
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (id: number) => {
    await api.deleteWatchItem(id);
    await load();
  };

  if (loading)
    return <p className="text-gray-400 py-12 text-center">Loading...</p>;

  return (
    <div className="space-y-6">
      {/* Add form */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">
          Add Item to Watch
        </h2>
        <p className="text-sm text-gray-400 mb-4">
          We'll search FB Marketplace for this item and notify you of deals.
          Fair price is estimated automatically from eBay sold data.
        </p>
        <form onSubmit={handleAdd} className="space-y-3">
          <div className="flex gap-3 flex-wrap">
            <input
              type="text"
              placeholder='What are you looking for? (e.g., "Herman Miller Aeron")'
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="flex-1 min-w-[300px] px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              required
            />
            <input
              type="number"
              placeholder="Max price ($)"
              value={maxPrice}
              onChange={(e) => setMaxPrice(e.target.value)}
              className="w-36 px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div className="flex gap-3 items-center">
            <input
              type="text"
              placeholder="Location (default: Huntsville, AL)"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              className="w-64 px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <input
              type="number"
              placeholder="Radius (mi)"
              value={radius}
              onChange={(e) => setRadius(e.target.value)}
              className="w-32 px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              type="submit"
              disabled={adding || !name.trim()}
              className="px-6 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {adding ? "Adding..." : "Add to Watchlist"}
            </button>
          </div>
        </form>
      </div>

      {/* Items list */}
      {items.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <p className="text-gray-400 text-lg">Your watchlist is empty</p>
          <p className="text-gray-300 text-sm mt-1">
            Add items above to start monitoring deals
          </p>
        </div>
      ) : (
        <div className="grid gap-4">
          {items.map((item) => {
            const pe = prices[item.name];
            const isLoading = loadingPrices.has(item.name);
            const priceError = priceErrors[item.name];
            return (
              <div
                key={item.id}
                className="bg-white rounded-xl border border-gray-200 p-5"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="text-lg font-semibold text-gray-900">
                      {item.name}
                    </h3>
                    <div className="flex items-center gap-4 mt-1 text-sm text-gray-500">
                      <span>{item.location}</span>
                      <span>{item.radius} mi radius</span>
                      {item.max_price && (
                        <span>
                          Max: <span className="font-mono">${item.max_price}</span>
                        </span>
                      )}
                      <span className="text-gray-300">
                        Added {new Date(item.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(item.id)}
                    className="text-gray-300 hover:text-red-500 transition-colors text-sm"
                  >
                    Remove
                  </button>
                </div>

                {/* Price estimate section */}
                <div className="mt-4 pt-4 border-t border-gray-100">
                  {isLoading ? (
                    <div className="flex items-center gap-2 text-sm text-gray-400">
                      <span className="animate-spin inline-block w-4 h-4 border-2 border-gray-300 border-t-blue-500 rounded-full" />
                      Estimating fair price from eBay sold data...
                    </div>
                  ) : pe ? (
                    <div className="flex items-center gap-6">
                      <div>
                        <p className="text-xs text-gray-400 uppercase tracking-wide">
                          Fair Price
                        </p>
                        <p className="text-2xl font-bold text-gray-900">
                          ${pe.median_price.toFixed(0)}
                        </p>
                      </div>
                      {pe.low_price != null && pe.high_price != null && (
                        <div>
                          <p className="text-xs text-gray-400 uppercase tracking-wide">
                            Range
                          </p>
                          <p className="text-sm font-mono text-gray-600">
                            ${pe.low_price.toFixed(0)} &ndash; $
                            {pe.high_price.toFixed(0)}
                          </p>
                        </div>
                      )}
                      <div>
                        <p className="text-xs text-gray-400 uppercase tracking-wide">
                          Source
                        </p>
                        <p className="text-sm text-gray-600">
                          {pe.source === "ebay"
                            ? `eBay (${pe.sample_count} sold)`
                            : "AI estimate"}
                        </p>
                      </div>
                      <button
                        onClick={() => fetchPrice(item.name)}
                        className="ml-auto text-xs text-gray-400 hover:text-blue-600"
                      >
                        Refresh
                      </button>
                    </div>
                  ) : priceError ? (
                    <div className="flex items-center justify-between">
                      <p className="text-sm text-red-500">
                        Price check failed
                      </p>
                      <button
                        onClick={() => fetchPrice(item.name)}
                        className="text-xs text-blue-600 hover:underline"
                      >
                        Retry
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => fetchPrice(item.name)}
                      className="text-sm text-blue-600 hover:underline"
                    >
                      Check fair market price
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
