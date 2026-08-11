import { useEffect, useMemo, useState } from "react";
import { api, parseApiDate, type ScanResult } from "../api";

const CHART_RUNS = 14;
/** Fixed ceiling so bar heights stay comparable between visits. */
const CHART_MAX = 14;

function duration(s: ScanResult): string {
  if (!s.completed_at) return "—";
  const ms =
    parseApiDate(s.completed_at).getTime() - parseApiDate(s.started_at).getTime();
  if (ms < 0) return "—";
  const secs = Math.round(ms / 1000);
  if (secs < 60) return `${secs}s`;
  return `${Math.floor(secs / 60)}m ${secs % 60}s`;
}

function StatusBadge({ status }: { status: ScanResult["status"] }) {
  const style =
    status === "completed"
      ? { background: "var(--color-run-ok-bg)", color: "var(--color-run-ok-fg)" }
      : status === "failed"
        ? { background: "var(--color-excluded-bg)", color: "var(--color-excluded-fg)" }
        : { background: "var(--color-sunken)", color: "var(--color-fg3)" };
  return (
    <span
      className="inline-flex items-center rounded-[5px] px-1.5 py-0.5 font-mono text-[10px] font-bold tracking-[.06em]"
      style={style}
    >
      {status.toUpperCase()}
    </span>
  );
}

export default function History() {
  const [scans, setScans] = useState<ScanResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getScans(50)
      .then(setScans)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  // Oldest-to-newest across the chart, so time reads left to right.
  const chart = useMemo(
    () => scans.slice(0, CHART_RUNS).reverse(),
    [scans]
  );

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

  return (
    <div className="mx-auto max-w-[1080px] px-5 py-6 space-y-4">
      {/* Chart */}
      <section className="rounded-[13px] border border-line bg-surface p-4">
        <h2 className="font-mono text-[13px] font-bold uppercase tracking-[.08em] text-fg">
          New listings per run
        </h2>
        <p className="mt-0.5 font-mono text-[11px] text-fg3">
          last {Math.min(CHART_RUNS, chart.length)} runs
        </p>

        {chart.length === 0 ? (
          <p className="py-10 text-center text-[13px] text-fg3">No runs yet</p>
        ) : (
          <div className="mt-4 flex h-[120px] items-end gap-1.5">
            {chart.map((s) => {
              const newPct = Math.min(100, (s.new_listings / CHART_MAX) * 100);
              const dealPct = Math.min(newPct, (s.deals_found / CHART_MAX) * 100);
              return (
                <div
                  key={s.id}
                  className="flex h-full flex-1 flex-col justify-end gap-0.5"
                  title={`#${s.id}: ${s.new_listings} new, ${s.deals_found} deals`}
                >
                  {dealPct > 0 && (
                    <div
                      className="rounded-t-[3px]"
                      style={{ height: `${dealPct}%`, background: "var(--color-strong)" }}
                    />
                  )}
                  <div
                    className="rounded-[3px]"
                    style={{
                      height: `${Math.max(2, newPct - dealPct)}%`,
                      background: "var(--color-bar-muted)",
                    }}
                  />
                </div>
              );
            })}
          </div>
        )}

        <div className="mt-3 flex gap-4 font-mono text-[10.5px] text-fg3">
          <span className="flex items-center gap-1.5">
            <span
              className="h-2 w-2 rounded-full"
              style={{ background: "var(--color-strong)" }}
            />
            deals
          </span>
          <span className="flex items-center gap-1.5">
            <span
              className="h-2 w-2 rounded-full"
              style={{ background: "var(--color-bar-muted)" }}
            />
            new listings
          </span>
        </div>
      </section>

      {/* Table */}
      <section className="overflow-hidden rounded-[13px] border border-line bg-surface">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-line">
                {[
                  { label: "Run", align: "left" },
                  { label: "Status", align: "left" },
                  { label: "Started", align: "left" },
                  { label: "Duration", align: "right" },
                  { label: "Items", align: "right" },
                  { label: "New", align: "right" },
                  { label: "Deals", align: "right" },
                ].map((h) => (
                  <th
                    key={h.label}
                    className={`px-4 py-2.5 font-mono text-[10px] font-bold uppercase tracking-[.1em] text-fg3 ${
                      h.align === "right" ? "text-right" : "text-left"
                    }`}
                  >
                    {h.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {scans.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-[13px] text-fg3">
                    No scan history yet. Trigger a scan from Deals.
                  </td>
                </tr>
              ) : (
                scans.map((s) => (
                  <tr key={s.id} className="border-b border-line last:border-0">
                    <td className="px-4 py-2.5 font-mono text-[12px] text-fg3">
                      #{s.id}
                    </td>
                    <td className="px-4 py-2.5">
                      <StatusBadge status={s.status} />
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[12px] text-fg2">
                      {parseApiDate(s.started_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-[12px] text-fg2">
                      {duration(s)}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-[12px] text-fg">
                      {s.items_scanned}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-[12px] text-fg">
                      {s.new_listings}
                    </td>
                    <td
                      className="px-4 py-2.5 text-right font-mono text-[12px] font-bold"
                      style={{
                        color:
                          s.deals_found > 0
                            ? "var(--color-strong)"
                            : "var(--color-fg3)",
                      }}
                    >
                      {s.deals_found}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
