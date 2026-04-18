import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, type Listing, type WatchItem } from "../api";
import ListingsTable from "../components/ListingsTable";

type SortKey = "newest" | "price-low" | "price-high" | "discount";

export default function Listings() {
  const [searchParams] = useSearchParams();
  const [allListings, setAllListings] = useState<Listing[]>([]);
  const [watchItems, setWatchItems] = useState<WatchItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters — initialize from URL params
  const [filterItem, setFilterItem] = useState(searchParams.get("item") || "");
  const [filterDeal, setFilterDeal] = useState("");
  const [search, setSearch] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [localOnly, setLocalOnly] = useState(false);
  const [sort, setSort] = useState<SortKey>("newest");

  const load = useCallback(async () => {
    try {
      const [l, w] = await Promise.all([
        api.getListings({ limit: 500 }),
        api.getWatchlist(),
      ]);
      setAllListings(l);
      setWatchItems(w);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Derive the default location from watchlist items
  const defaultLocation = useMemo(() => {
    if (watchItems.length === 0) return "";
    // Most common location across watch items
    const counts: Record<string, number> = {};
    for (const w of watchItems) {
      const loc = w.location.toLowerCase();
      counts[loc] = (counts[loc] || 0) + 1;
    }
    return Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] || "";
  }, [watchItems]);

  // Client-side filtering + sorting
  const filtered = useMemo(() => {
    let result = allListings;

    if (filterItem) {
      result = result.filter((l) => l.item_name === filterItem);
    }
    if (filterDeal) {
      result = result.filter((l) => l.deal_quality === filterDeal);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (l) =>
          l.title.toLowerCase().includes(q) ||
          l.item_name.toLowerCase().includes(q)
      );
    }
    if (maxPrice) {
      const max = parseFloat(maxPrice);
      if (!isNaN(max)) {
        result = result.filter((l) => l.price <= max);
      }
    }
    if (localOnly && defaultLocation) {
      result = result.filter((l) => {
        if (!l.location) return false;
        return l.location.toLowerCase().includes(defaultLocation);
      });
    }

    // Sort
    switch (sort) {
      case "price-low":
        result = [...result].sort((a, b) => a.price - b.price);
        break;
      case "price-high":
        result = [...result].sort((a, b) => b.price - a.price);
        break;
      case "discount":
        result = [...result].sort(
          (a, b) => (b.discount_pct ?? 0) - (a.discount_pct ?? 0)
        );
        break;
      case "newest":
      default:
        result = [...result].sort(
          (a, b) =>
            new Date(b.first_seen).getTime() - new Date(a.first_seen).getTime()
        );
    }

    return result;
  }, [allListings, filterItem, filterDeal, search, maxPrice, localOnly, defaultLocation, sort]);

  if (loading)
    return <p className="text-gray-400 py-12 text-center">Loading...</p>;

  if (watchItems.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-16 text-center">
        <p className="text-gray-400 text-lg">No watchlist items yet</p>
        <p className="text-gray-300 text-sm mt-1 mb-4">
          Add items to your watchlist first, then run a scan to find listings
        </p>
        <Link
          to="/watchlist"
          className="inline-block px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700"
        >
          Go to Watchlist
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Search bar */}
      <input
        type="text"
        placeholder="Search listings..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full px-4 py-3 border border-gray-300 rounded-xl text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
      />

      {/* Filter bar */}
      <div className="flex gap-3 items-center flex-wrap">
        <select
          value={filterItem}
          onChange={(e) => setFilterItem(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All items</option>
          {watchItems.map((w) => (
            <option key={w.id} value={w.name}>
              {w.name}
            </option>
          ))}
        </select>

        <select
          value={filterDeal}
          onChange={(e) => setFilterDeal(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Any deal quality</option>
          <option value="great">Great deals</option>
          <option value="good">Good deals</option>
          <option value="fair">Fair</option>
        </select>

        <input
          type="number"
          placeholder="Max price"
          value={maxPrice}
          onChange={(e) => setMaxPrice(e.target.value)}
          className="w-28 px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        />

        <button
          onClick={() => setLocalOnly(!localOnly)}
          className={`px-3 py-2 rounded-lg text-sm font-medium border transition-colors ${
            localOnly
              ? "bg-blue-600 text-white border-blue-600"
              : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"
          }`}
        >
          Local only
        </button>

        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as SortKey)}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="newest">Newest first</option>
          <option value="price-low">Price: low to high</option>
          <option value="price-high">Price: high to low</option>
          <option value="discount">Best discount</option>
        </select>

        <span className="text-sm text-gray-400 ml-auto">
          {filtered.length} of {allListings.length} listings
        </span>
      </div>

      <ListingsTable listings={filtered} />
    </div>
  );
}
