import { useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  isDeal,
  isExcluded,
  isUnscored,
  parseApiDate,
  proxyImageUrl,
  type Listing,
} from "../api";
import DealBadge from "../components/DealBadge";
import { scoreColor } from "../components/ScoreBar";
import { SCAN_STEPS } from "../hooks/useScan";
import { useShell } from "../shell";

/** Composition of a watch item's listings, in the order the stacked bar draws. */
function composition(listings: Listing[]) {
  let strong = 0;
  let weak = 0;
  let excluded = 0;
  let unscored = 0;
  for (const l of listings) {
    if (isUnscored(l)) unscored++;
    else if (isExcluded(l)) excluded++;
    else if (isDeal(l)) strong++;
    else weak++;
  }
  return { strong, weak, excluded, unscored };
}

function DealCard({ listing }: { listing: Listing }) {
  const img = proxyImageUrl(listing.thumbnail);
  const rel = listing.relevance_score;

  return (
    <a
      href={listing.link}
      target="_blank"
      rel="noopener noreferrer"
      className="block overflow-hidden rounded-[13px] border border-line bg-surface transition-colors duration-150 hover:border-line-hover"
    >
      <div className="flex h-[118px] items-center justify-center bg-sunken font-mono text-[10px] text-fg3">
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
      <div className="p-3">
        <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
          <DealBadge quality={listing.deal_quality} />
          <span className="font-mono text-[10px] font-bold uppercase tracking-[.06em] text-fg3">
            {listing.item_name}
          </span>
        </div>
        <p
          className="text-[13.5px] font-semibold leading-snug text-fg"
          style={{
            minHeight: 39,
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}
        >
          {listing.title}
        </p>
        <div className="mt-2 flex items-end justify-between">
          <div>
            <p className="font-mono text-[17px] font-bold text-fg">
              ${listing.price.toFixed(0)}
            </p>
            {listing.fair_price ? (
              <p className="font-mono text-[10.5px] text-fg3">
                fair ${listing.fair_price.toFixed(0)}
              </p>
            ) : null}
          </div>
          <div className="text-right">
            <p
              className="font-mono text-[15px] font-bold"
              style={{ color: rel != null ? scoreColor(rel) : "var(--color-fg3)" }}
            >
              {rel != null ? `${Math.round(rel * 100)}%` : "—"}
            </p>
            <p className="font-mono text-[9.5px] font-bold tracking-[.06em] text-fg3">
              MATCH
            </p>
          </div>
        </div>
      </div>
    </a>
  );
}

function ScannerPanel() {
  const { stats, setup, scan } = useShell();
  const canScan = !!setup?.fb_logged_in && !!setup?.has_watch_items;

  // Real next-scan time: last scan start + the configured interval, both from
  // the API. Null when nothing has run yet, rather than an invented countdown.
  const nextIn = useMemo(() => {
    if (!stats?.last_scan || !setup?.scan_interval_minutes) return null;
    const next =
      parseApiDate(stats.last_scan.started_at).getTime() +
      setup.scan_interval_minutes * 60_000;
    const mins = Math.round((next - Date.now()) / 60_000);
    return mins > 0 ? `in ${mins} min` : "due now";
  }, [stats, setup]);

  const activeIndex = scan.step ? SCAN_STEPS.indexOf(scan.step) : -1;

  return (
    <aside className="w-full flex-shrink-0 rounded-[13px] border border-line bg-surface p-4 lg:w-[320px]">
      <div className="mb-3 flex items-center justify-between">
        <span className="font-mono text-[10px] font-bold uppercase tracking-[.1em] text-fg3">
          Scanner
        </span>
        <span
          className="rounded-[5px] px-2 py-0.5 font-mono text-[10px] font-bold tracking-[.06em]"
          style={
            scan.scanning
              ? { background: "var(--color-matched-bg)", color: "var(--color-matched-fg)" }
              : { background: "var(--color-sunken)", color: "var(--color-fg3)" }
          }
        >
          {scan.scanning ? "RUNNING" : "IDLE"}
        </span>
      </div>

      <ol className="space-y-2">
        {SCAN_STEPS.map((s, i) => {
          const done = scan.scanning && activeIndex > i;
          const active = scan.scanning && activeIndex === i;
          return (
            <li key={s} className="flex items-center gap-2.5">
              <span
                className={`flex h-3.5 w-3.5 flex-shrink-0 items-center justify-center rounded-full text-[8px] ${active ? "pulse-dot" : ""}`}
                style={
                  done
                    ? { background: "var(--color-strong)", color: "var(--color-fg)" }
                    : active
                      ? { border: "2px solid var(--color-strong)" }
                      : { background: "var(--color-sunken)" }
                }
              >
                {done ? "✓" : ""}
              </span>
              <span
                className={`text-[12.5px] ${active || done ? "text-fg" : "text-fg3"}`}
              >
                {s}
              </span>
            </li>
          );
        })}
      </ol>

      <div className="my-4 border-t border-line" />

      <p className="font-mono text-[10px] font-bold uppercase tracking-[.1em] text-fg3">
        Next automatic scan
      </p>
      <p className="mt-0.5 text-[13px] text-fg">
        {nextIn ?? "after the first run"}
      </p>

      {scan.error && (
        <p className="mt-2 text-[11.5px]" style={{ color: "var(--color-weak)" }}>
          {scan.error}
        </p>
      )}

      <button
        type="button"
        onClick={scan.trigger}
        disabled={scan.scanning || !canScan}
        className={`mt-4 w-full rounded-[10px] px-4 py-2.5 text-[12.5px] font-bold transition-colors duration-150 ${
          scan.scanning || !canScan
            ? "cursor-not-allowed bg-sunken text-fg3"
            : "bg-fg text-bg"
        }`}
      >
        {scan.scanning ? "Scanning…" : "Scan now"}
      </button>
      {!canScan && (
        <p className="mt-1.5 text-center text-[11px] text-fg3">
          {!setup?.fb_logged_in
            ? "Connect Facebook first"
            : "Add watchlist items first"}
        </p>
      )}
    </aside>
  );
}

export default function Dashboard() {
  const { listings, stats, setup, loading, error } = useShell();
  const navigate = useNavigate();

  const deals = useMemo(() => listings.filter(isDeal), [listings]);
  const scored = useMemo(
    () => listings.filter((l) => !isUnscored(l)).length,
    [listings]
  );

  const byItem = useMemo(() => {
    const groups: Record<string, Listing[]> = {};
    for (const l of listings) {
      (groups[l.item_name] ||= []).push(l);
    }
    return groups;
  }, [listings]);

  if (loading) {
    return <p className="py-12 text-center text-[13px] text-fg3">Loading…</p>;
  }
  if (error) {
    return (
      <p className="py-12 text-center text-[13px]" style={{ color: "var(--color-weak)" }}>
        {error}
      </p>
    );
  }

  const setupComplete =
    !!setup?.fb_logged_in &&
    !!setup?.has_watch_items &&
    !!setup?.has_scans &&
    !!setup?.has_email;

  const itemNames = Object.keys(byItem);

  return (
    <div className="mx-auto max-w-[1180px] px-5 py-6">
      {!setupComplete && setup && <Onboarding />}

      <div className="flex flex-col gap-6 lg:flex-row">
        <div className="min-w-0 flex-1">
          {/* Headline */}
          <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="text-[26px] font-bold tracking-[-.02em] text-fg">
                {deals.length > 0
                  ? `${deals.length} listing${deals.length === 1 ? "" : "s"} worth a look`
                  : "Nothing new worth acting on"}
              </h1>
              <p className="mt-1 max-w-[560px] text-[13px] text-fg2">
                Ranked by relevance × price. Accessories and parts listings are
                pushed down, not deleted.
              </p>
            </div>
            <div className="flex gap-6">
              {[
                { label: "Watching", value: stats?.active_watches ?? 0 },
                { label: "Listings", value: stats?.total_listings ?? 0 },
                { label: "Scored", value: scored },
                { label: "Deals", value: deals.length, lime: true },
              ].map((s) => (
                <div key={s.label}>
                  <p className="font-mono text-[10px] font-bold uppercase tracking-[.1em] text-fg3">
                    {s.label}
                  </p>
                  <p
                    className="font-mono text-[24px] font-bold"
                    style={s.lime ? { color: "var(--color-strong)" } : undefined}
                  >
                    {s.value}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Worth acting on */}
          <section className="mb-8">
            <h2 className="mb-3 font-mono text-[13px] font-bold uppercase tracking-[.08em] text-fg">
              Worth acting on
            </h2>
            {deals.length > 0 ? (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {deals.slice(0, 9).map((l) => (
                  <DealCard key={l.id} listing={l} />
                ))}
              </div>
            ) : (
              <div className="rounded-[13px] border border-dashed border-line p-10 text-center">
                <p className="text-[13.5px] font-semibold text-fg">
                  Nothing clears the bar yet
                </p>
                <p className="mt-1 text-[12.5px] text-fg2">
                  A listing needs relevance × price of 0.30 or better to show up
                  here.
                </p>
              </div>
            )}
          </section>

          {/* By watch item */}
          <section>
            <h2 className="mb-3 font-mono text-[13px] font-bold uppercase tracking-[.08em] text-fg">
              By watch item
            </h2>
            {itemNames.length === 0 ? (
              <div className="rounded-[13px] border border-dashed border-line p-10 text-center">
                <p className="text-[13.5px] font-semibold text-fg">
                  No listings yet
                </p>
                <p className="mt-1 text-[12.5px] text-fg2">
                  Add items to your watchlist and run a scan.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {itemNames.map((name) => {
                  const group = byItem[name];
                  const c = composition(group);
                  const segments = [
                    { key: "strong", n: c.strong, color: "var(--color-strong)" },
                    { key: "weak", n: c.weak, color: "var(--color-middling)" },
                    { key: "excluded", n: c.excluded, color: "var(--color-weak)" },
                    { key: "unscored", n: c.unscored, color: "var(--color-bar-muted)" },
                  ].filter((s) => s.n > 0);

                  return (
                    <div
                      key={name}
                      className="rounded-[13px] border border-line bg-surface p-4"
                    >
                      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                        <div>
                          <p className="text-[15px] font-bold text-fg">{name}</p>
                          <p className="font-mono text-[11.5px] text-fg3">
                            {group.length} listing{group.length === 1 ? "" : "s"} ·{" "}
                            {c.strong} strong
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={() =>
                            navigate(`/listings?item=${encodeURIComponent(name)}`)
                          }
                          className="rounded-lg border border-line px-3 py-1.5 text-[12px] font-semibold text-fg2 transition-colors duration-150 hover:border-line-hover hover:text-fg"
                        >
                          Browse →
                        </button>
                      </div>

                      <div className="flex h-2 gap-0.5 overflow-hidden">
                        {segments.map((s) => (
                          <div
                            key={s.key}
                            className="rounded-full"
                            style={{ flex: s.n, background: s.color }}
                          />
                        ))}
                      </div>

                      <div className="mt-2 flex flex-wrap gap-3 font-mono text-[10.5px] text-fg3">
                        {segments.map((s) => (
                          <span key={s.key} className="flex items-center gap-1.5">
                            <span
                              className="h-2 w-2 rounded-full"
                              style={{ background: s.color }}
                            />
                            {s.key} {s.n}
                          </span>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        </div>

        <ScannerPanel />
      </div>
    </div>
  );
}

/** Only rendered while setup is incomplete — not a permanent fixture. */
function Onboarding() {
  const { stats, setup } = useShell();
  if (!setup) return null;

  const steps = [
    {
      done: setup.fb_logged_in,
      title: "Connect Facebook",
      description: setup.fb_logged_in
        ? "Facebook session active"
        : "Run the login command on your host machine",
      command: setup.fb_logged_in
        ? undefined
        : 'cd /Users/mramasub/misc/marketswipe && VIRTUAL_ENV= uv run python -c "import asyncio; from backend.scraper_fb import init_fb_login; asyncio.run(init_fb_login())"',
    },
    {
      done: setup.has_watch_items,
      title: "Add items to watch",
      description: setup.has_watch_items
        ? `${stats?.active_watches ?? 0} item(s) in watchlist`
        : "Tell us what you're looking for",
      linkTo: setup.has_watch_items ? undefined : "/watchlist",
    },
    {
      done: setup.has_scans,
      title: "Run your first scan",
      description: setup.has_scans
        ? `Scans run automatically every ${setup.scan_interval_minutes} minutes`
        : "Search Facebook Marketplace for your items",
    },
    {
      done: setup.has_email,
      title: "Set up email alerts",
      description: setup.has_email
        ? "Email notifications enabled"
        : "Add SMTP_USER and SMTP_PASS to .env to get deal alerts",
    },
  ];

  return (
    <div className="mb-6 rounded-[13px] border border-line bg-surface p-5">
      <h2 className="text-[15px] font-bold text-fg">Get started</h2>
      <p className="mt-0.5 text-[12.5px] text-fg2">
        Complete these steps to start finding deals automatically.
      </p>
      <div className="mt-4 space-y-3">
        {steps.map((s, i) => (
          <div key={s.title} className="flex items-start gap-3">
            <span
              className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full font-mono text-[11px] font-bold"
              style={
                s.done
                  ? { background: "var(--color-strong)", color: "var(--color-fg)" }
                  : { background: "var(--color-sunken)", color: "var(--color-fg3)" }
              }
            >
              {s.done ? "✓" : i + 1}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-semibold text-fg">{s.title}</p>
              <p className="mt-0.5 text-[12px] text-fg3">{s.description}</p>
              {s.command && (
                <pre className="mt-2 overflow-x-auto rounded-lg bg-sunken p-3 font-mono text-[11px] text-fg2">
                  {s.command}
                </pre>
              )}
              {s.linkTo && (
                <Link
                  to={s.linkTo}
                  className="mt-1.5 inline-block text-[12px] font-semibold text-fg hover:underline"
                >
                  Go to Watchlist →
                </Link>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
