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

export interface MatchDetails {
  score: number;
  matched: string[];
  missed: string[];
  rejected: boolean;
  reject_reason?: string | null;
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
  relevance_score: number | null;
  final_score: number | null;
  match_details: MatchDetails | null;
}

export type ListingSort = "final" | "relevance" | "deal" | "price" | "recent";

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
    sort?: ListingSort;
    limit?: number;
    offset?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.item_name) qs.set("item_name", params.item_name);
    if (params?.deal_quality) qs.set("deal_quality", params.deal_quality);
    if (params?.sort) qs.set("sort", params.sort);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
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
