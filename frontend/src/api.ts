const BASE = "/api";

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

// Proxy images through backend to bypass FB referrer restrictions
export function proxyImageUrl(url: string | null): string | null {
  if (!url) return null;
  return `/api/proxy-image?url=${encodeURIComponent(url)}`;
}

// Types

export interface WatchItem {
  id: number;
  name: string;
  max_price: number | null;
  location: string;
  radius: number;
  created_at: string;
}

export type ListingSort = "final" | "relevance" | "deal" | "price" | "recent";

// Parsed shape of Listing.match_details, which arrives as a JSON-encoded string.
export interface MatchDetails {
  score: number;
  matched: string[];
  missed: string[];
  excluded_by: string | null;
}

export interface Listing {
  id: number;
  fb_id: string;
  title: string;
  price: number;
  fair_price: number | null;
  discount_pct: number | null;
  deal_quality: "great" | "good" | "fair" | "none";
  link: string;
  thumbnail: string | null;
  location: string | null;
  item_name: string;
  first_seen: string;
  // Null on every listing scanned before relevance scoring shipped.
  relevance_score: number | null;
  final_score: number | null;
  match_details: string | null;
}

// match_details is a JSON string, not an object. A malformed value degrades to
// "no details" rather than taking the row down with it.
export function parseMatchDetails(raw: string | null): MatchDetails | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as MatchDetails;
  } catch {
    return null;
  }
}

/**
 * The API serializes naive datetimes with no timezone designator (e.g.
 * "2026-08-11T01:23:09") but the values are UTC — SQLite's datetime('now').
 * `new Date()` would read them as local time, putting every timestamp hours off
 * and pushing the next-scan countdown into the future. Treat a bare timestamp
 * as UTC; leave anything already carrying an offset alone.
 */
export function parseApiDate(raw: string): Date {
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(raw);
  return new Date(hasZone ? raw : `${raw}Z`);
}

// --- Derived score helpers ---
//
// Defined once here so the 0.3 deal gate has exactly one definition. The Deals
// headline, the nav badge and the "worth acting on" list all read isDeal(); if
// they diverge the page contradicts itself.

export const DEAL_THRESHOLD = 0.3;

/** Price attractiveness in [0,1]. Null when there is no fair-price estimate. */
export function priceScore(l: Listing): number | null {
  if (!l.fair_price || l.fair_price <= 0) return null;
  return Math.max(0, Math.min(1, 1 - l.price / l.fair_price));
}

/**
 * Recomputed from the same inputs the row displays, rather than read from the
 * persisted `final_score` column. The backend computes the column identically
 * at scan time, so for real data the two agree — but deriving it here keeps the
 * "rel × price" factor line and the final bar from ever contradicting each
 * other if the stored value drifts. The stored column is what the server sorts
 * by; this is what the user sees.
 */
export function finalScore(l: Listing): number | null {
  const p = priceScore(l);
  if (l.relevance_score == null || p == null) return null;
  return l.relevance_score * p;
}

export function isUnscored(l: Listing): boolean {
  return l.relevance_score == null;
}

export function isExcluded(l: Listing): boolean {
  return !!parseMatchDetails(l.match_details)?.excluded_by;
}

export function isDeal(l: Listing): boolean {
  return (finalScore(l) ?? 0) >= DEAL_THRESHOLD;
}

export interface PriceEstimate {
  item_name: string;
  median_price: number;
  low_price: number | null;
  high_price: number | null;
  sample_count: number;
  source: "ebay" | "llm";
  estimated_at: string;
  sold_prices: number[];
}

export interface ScanResult {
  id: number;
  started_at: string;
  completed_at: string | null;
  items_scanned: number;
  deals_found: number;
  new_listings: number;
  status: "running" | "completed" | "failed";
}

export interface DashboardStats {
  active_watches: number;
  total_listings: number;
  total_deals: number;
  last_scan: ScanResult | null;
  recent_deals: Listing[];
}

export interface SetupStatus {
  fb_logged_in: boolean;
  has_watch_items: boolean;
  has_scans: boolean;
  has_email: boolean;
  scan_interval_minutes: number;
  notify_min_relevance: number;
}

// API functions

export const api = {
  // Watchlist
  getWatchlist: () => request<WatchItem[]>("/watchlist"),
  addWatchItem: (data: {
    name: string;
    max_price?: number | null;
    location?: string | null;
    radius?: number | null;
  }) =>
    request<WatchItem>("/watchlist", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  deleteWatchItem: (id: number) =>
    request<{ deleted: boolean }>(`/watchlist/${id}`, { method: "DELETE" }),

  // Listings
  getListings: (params?: {
    item_name?: string;
    deal_quality?: string;
    limit?: number;
    offset?: number;
    sort?: ListingSort;
  }) => {
    const qs = new URLSearchParams();
    if (params?.item_name) qs.set("item_name", params.item_name);
    if (params?.deal_quality) qs.set("deal_quality", params.deal_quality);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    if (params?.sort) qs.set("sort", params.sort);
    const q = qs.toString();
    return request<Listing[]>(`/listings${q ? `?${q}` : ""}`);
  },

  // Dashboard
  getDashboard: () => request<DashboardStats>("/dashboard"),

  // Scans
  getScans: (limit = 20) => request<ScanResult[]>(`/scans?limit=${limit}`),
  triggerScan: () =>
    request<ScanResult>("/scans/trigger", { method: "POST" }),

  // Prices
  getPrice: (itemName: string, forceRefresh = false) =>
    request<PriceEstimate>(
      `/prices/${encodeURIComponent(itemName)}?force_refresh=${forceRefresh}`
    ),

  // Status
  getFbStatus: () => request<{ logged_in: boolean }>("/auth/fb-status"),
  getSetupStatus: () => request<SetupStatus>("/setup-status"),
};
