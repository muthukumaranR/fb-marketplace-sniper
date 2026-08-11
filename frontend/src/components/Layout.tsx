import { useCallback, useEffect, useMemo, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  api,
  isDeal,
  type DashboardStats,
  type Listing,
  type SetupStatus,
} from "../api";
import { useScan } from "../hooks/useScan";
import { useTheme } from "../hooks/useTheme";
import type { ShellContext } from "../shell";
import SegmentedControl from "./SegmentedControl";
import ThemeToggle from "./ThemeToggle";

const NAV = [
  { path: "/", label: "Deals" },
  { path: "/listings", label: "Listings" },
  { path: "/watchlist", label: "Watchlist" },
  { path: "/history", label: "Runs" },
] as const;

type NavPath = (typeof NAV)[number]["path"];

function LogoMark() {
  // Placeholder mark — swap for a real asset when one exists.
  return (
    <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true">
      <rect width="26" height="26" rx="7" fill="var(--color-fg)" />
      <path
        d="M6 9 L13 16 L20 9"
        stroke="var(--color-strong)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      <path
        d="M6 13 L13 20 L20 13"
        stroke="var(--color-strong)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
        opacity="0.3"
      />
    </svg>
  );
}

export default function Layout() {
  const { theme, toggle } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();

  const [listings, setListings] = useState<Listing[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [setup, setSetup] = useState<SetupStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const [l, d, s] = await Promise.all([
        api.getListings({ limit: 200, sort: "final" }),
        api.getDashboard(),
        api.getSetupStatus(),
      ]);
      setListings(l);
      setStats(d);
      setSetup(s);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const scan = useScan(reload);

  const dealCount = useMemo(
    () => listings.filter(isDeal).length,
    [listings]
  );

  const active =
    (NAV.find((n) => n.path === location.pathname)?.path as NavPath) ?? "/";

  const canScan = !!setup?.fb_logged_in && !!setup?.has_watch_items;

  const context: ShellContext = {
    listings,
    stats,
    setup,
    loading,
    error,
    reload,
    scan,
  };

  return (
    <div className="min-h-screen bg-bg">
      <header className="sticky top-0 z-40 border-b border-line bg-surface">
        <div className="flex h-14 items-center gap-5 px-5">
          {/* Brand */}
          <div className="flex flex-shrink-0 items-center gap-2.5">
            <LogoMark />
            <span className="font-mono text-[14px] font-bold tracking-[.12em] text-fg">
              MARKET<span className="opacity-[.42]">SWIPE</span>
            </span>
            <span className="hidden text-[11px] uppercase text-fg3 lg:inline">
              deal finder
            </span>
          </div>

          {/* Nav */}
          <div className="hidden md:block">
            <SegmentedControl<NavPath>
              value={active}
              onChange={(p) => navigate(p)}
              segments={NAV.map((n) => ({
                value: n.path,
                label: n.label,
                count: n.path === "/" && dealCount > 0 ? dealCount : undefined,
              }))}
            />
          </div>

          {/* Right */}
          <div className="ml-auto flex items-center gap-3">
            <span className="hidden items-center gap-1.5 font-mono text-[11px] text-fg2 sm:flex">
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{
                  background: setup?.fb_logged_in
                    ? "#22c55e"
                    : setup
                      ? "var(--color-weak)"
                      : "var(--color-fg3)",
                }}
              />
              FB {setup ? (setup.fb_logged_in ? "LIVE" : "OFF") : "…"}
            </span>

            <button
              type="button"
              onClick={scan.trigger}
              disabled={scan.scanning || !canScan}
              title={
                !canScan
                  ? !setup?.fb_logged_in
                    ? "Connect Facebook first"
                    : "Add watchlist items first"
                  : undefined
              }
              className={`rounded-lg px-3 py-1.5 text-[12.5px] font-bold transition-colors duration-150 ${
                scan.scanning || !canScan
                  ? "cursor-not-allowed bg-sunken text-fg3"
                  : "bg-fg text-bg"
              }`}
            >
              {scan.scanning ? "Scanning…" : "Scan now"}
            </button>

            <ThemeToggle theme={theme} onToggle={toggle} />
          </div>
        </div>

        {/* Scan progress strip */}
        {scan.scanning && (
          <div style={{ background: "#111318" }} className="px-5 py-2">
            <div className="flex items-center gap-3">
              <span
                className="font-mono text-[10px] font-bold tracking-[.1em]"
                style={{ color: "var(--color-strong)" }}
              >
                SCANNING
              </span>
              <span className="text-[12px]" style={{ color: "#cfd3dd" }}>
                {scan.step ?? "Working…"}
              </span>
              <div
                className="h-[3px] flex-1 overflow-hidden rounded-full"
                style={{ maxWidth: 420, background: "#2a2d36" }}
              >
                <div
                  className="h-full rounded-full transition-[width] duration-[400ms] ease-out"
                  style={{
                    width:
                      scan.progress != null
                        ? `${Math.round(scan.progress * 100)}%`
                        : "100%",
                    background: "var(--color-strong)",
                    opacity: scan.progress == null ? 0.35 : 1,
                  }}
                />
              </div>
              <span className="font-mono text-[11px]" style={{ color: "#cfd3dd" }}>
                {scan.progress != null
                  ? `${Math.round(scan.progress * 100)}%`
                  : "—"}
              </span>
            </div>
          </div>
        )}
      </header>

      <main>
        <Outlet context={context} />
      </main>
    </div>
  );
}
