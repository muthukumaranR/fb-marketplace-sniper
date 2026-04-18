import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api, type DashboardStats, type Listing, type SetupStatus } from "../api";
import ListingsTable from "../components/ListingsTable";
import ScanStatus from "../components/ScanStatus";

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [setup, setSetup] = useState<SetupStatus | null>(null);
  const [allListings, setAllListings] = useState<Listing[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const location = useLocation();

  const load = useCallback(async () => {
    try {
      const [d, s, l] = await Promise.all([
        api.getDashboard(),
        api.getSetupStatus(),
        api.getListings({ limit: 200 }),
      ]);
      setStats(d);
      setSetup(s);
      setAllListings(l);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load, location.key]);

  // Group listings by watch item
  const groupedByItem = useMemo(() => {
    const groups: Record<string, { deals: Listing[]; total: number }> = {};
    for (const l of allListings) {
      if (!groups[l.item_name]) {
        groups[l.item_name] = { deals: [], total: 0 };
      }
      groups[l.item_name].total++;
      if (l.deal_quality === "great" || l.deal_quality === "good") {
        groups[l.item_name].deals.push(l);
      }
    }
    return groups;
  }, [allListings]);

  if (loading)
    return <p className="text-gray-400 py-12 text-center">Loading...</p>;
  if (error)
    return <p className="text-red-500 py-12 text-center">{error}</p>;
  if (!stats || !setup) return null;

  const setupComplete =
    setup.fb_logged_in && setup.has_watch_items && setup.has_scans && setup.has_email;

  const itemNames = Object.keys(groupedByItem);
  const totalDeals = Object.values(groupedByItem).reduce((s, g) => s + g.deals.length, 0);

  return (
    <div className="space-y-6">
      {/* Onboarding */}
      {!setupComplete && (
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl border border-blue-200 p-6">
          <h2 className="text-lg font-bold text-gray-900 mb-1">Get Started</h2>
          <p className="text-sm text-gray-500 mb-4">
            Complete these steps to start finding deals automatically.
          </p>
          <div className="space-y-3">
            <SetupStep
              done={setup.fb_logged_in}
              step={1}
              title="Connect Facebook"
              description={
                setup.fb_logged_in
                  ? "Facebook session active"
                  : "Run the login command on your host machine"
              }
              command={
                !setup.fb_logged_in
                  ? 'cd /Users/mramasub/misc/fb-mktplace && VIRTUAL_ENV= uv run python -c "import asyncio; from backend.scraper_fb import init_fb_login; asyncio.run(init_fb_login())"'
                  : undefined
              }
            />
            <SetupStep
              done={setup.has_watch_items}
              step={2}
              title="Add items to watch"
              description={
                setup.has_watch_items
                  ? `${stats.active_watches} item${stats.active_watches > 1 ? "s" : ""} in watchlist`
                  : "Tell us what you're looking for"
              }
              linkTo={!setup.has_watch_items ? "/watchlist" : undefined}
              linkLabel="Go to Watchlist"
            />
            <SetupStep
              done={setup.has_scans}
              step={3}
              title="Run your first scan"
              description={
                setup.has_scans
                  ? "Scans running automatically every 30 minutes"
                  : "Search Facebook Marketplace for your items"
              }
            />
            <SetupStep
              done={setup.has_email}
              step={4}
              title="Set up email alerts"
              description={
                setup.has_email
                  ? "Email notifications enabled"
                  : "Add SMTP_USER and SMTP_PASS to .env to get deal alerts"
              }
            />
          </div>
        </div>
      )}

      {/* Scanner */}
      <ScanStatus
        lastScan={stats.last_scan}
        fbConnected={setup.fb_logged_in}
        hasWatchItems={setup.has_watch_items}
        onScanTriggered={load}
      />

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Watching" value={stats.active_watches} icon="eye" />
        <StatCard label="Listings Found" value={stats.total_listings} icon="list" />
        <StatCard label="Deals" value={totalDeals} color="text-green-600" icon="tag" />
      </div>

      {/* Per-item deal sections */}
      {itemNames.length > 0 ? (
        <div className="space-y-6">
          {itemNames.map((itemName) => {
            const group = groupedByItem[itemName];
            return (
              <div key={itemName} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                {/* Item header */}
                <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="px-3 py-1 rounded-full text-sm font-semibold bg-indigo-100 text-indigo-700">
                      {itemName}
                    </span>
                    <span className="text-sm text-gray-400">
                      {group.total} listing{group.total !== 1 ? "s" : ""} found
                      {group.deals.length > 0 && (
                        <span className="text-green-600 font-medium ml-1">
                          &middot; {group.deals.length} deal{group.deals.length !== 1 ? "s" : ""}
                        </span>
                      )}
                    </span>
                  </div>
                  <Link
                    to={`/listings?item=${encodeURIComponent(itemName)}`}
                    className="text-xs text-blue-600 hover:underline"
                  >
                    View all
                  </Link>
                </div>

                {/* Deals for this item */}
                <div className="p-4">
                  {group.deals.length > 0 ? (
                    <ListingsTable
                      listings={group.deals.slice(0, 4)}
                      showItemName={false}
                      compact
                    />
                  ) : (
                    <p className="text-sm text-gray-400 text-center py-6">
                      No deals yet for this item. Listings found at regular prices.
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <p className="text-gray-400 text-lg">No listings yet</p>
          <p className="text-gray-300 text-sm mt-1">
            Add items to your watchlist and run a scan to find deals
          </p>
        </div>
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  color,
  icon,
}: {
  label: string;
  value: number;
  color?: string;
  icon: string;
}) {
  const icons: Record<string, string> = {
    eye: "M15 12a3 3 0 11-6 0 3 3 0 016 0z M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z",
    list: "M4 6h16M4 10h16M4 14h16M4 18h16",
    tag: "M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z",
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex items-center gap-4">
      <div className="w-10 h-10 rounded-lg bg-gray-50 flex items-center justify-center">
        <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d={icons[icon]} />
        </svg>
      </div>
      <div>
        <p className="text-sm text-gray-500">{label}</p>
        <p className={`text-2xl font-bold ${color || "text-gray-900"}`}>{value}</p>
      </div>
    </div>
  );
}

function SetupStep({
  done,
  step,
  title,
  description,
  command,
  linkTo,
  linkLabel,
}: {
  done: boolean;
  step: number;
  title: string;
  description: string;
  command?: string;
  linkTo?: string;
  linkLabel?: string;
}) {
  return (
    <div className={`flex items-start gap-3 p-3 rounded-lg ${done ? "bg-green-50/50" : "bg-white"}`}>
      <div
        className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 text-sm font-bold ${
          done ? "bg-green-500 text-white" : "bg-gray-200 text-gray-500"
        }`}
      >
        {done ? "\u2713" : step}
      </div>
      <div className="flex-1 min-w-0">
        <p className={`font-medium text-sm ${done ? "text-green-700" : "text-gray-900"}`}>
          {title}
        </p>
        <p className="text-xs text-gray-500 mt-0.5">{description}</p>
        {command && (
          <pre className="mt-2 text-xs bg-gray-900 text-green-400 rounded-lg p-3 overflow-x-auto">
            {command}
          </pre>
        )}
        {linkTo && (
          <Link
            to={linkTo}
            className="inline-block mt-2 text-xs font-medium text-blue-600 hover:underline"
          >
            {linkLabel} &rarr;
          </Link>
        )}
      </div>
    </div>
  );
}
