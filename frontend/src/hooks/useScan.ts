import { useCallback, useEffect, useRef, useState } from "react";
import { api, parseApiDate, type ScanResult } from "../api";

export const SCAN_STEPS = [
  "Loading Facebook session",
  "Scraping search results",
  "Estimating fair prices",
  "Scoring relevance",
] as const;

/** Median of completed scan durations, in ms. Null when nothing has completed. */
function medianDuration(scans: ScanResult[]): number | null {
  const durations = scans
    .filter((s) => s.status === "completed" && s.completed_at)
    .map(
      (s) =>
        parseApiDate(s.completed_at as string).getTime() -
        parseApiDate(s.started_at).getTime()
    )
    .filter((d) => d > 0)
    .sort((a, b) => a - b);
  if (!durations.length) return null;
  return durations[Math.floor(durations.length / 2)];
}

/**
 * Owns triggering a scan and polling it to completion, so the header button and
 * the Deals scanner panel drive the same state.
 *
 * On progress: the backend reports only running/completed/failed — never which
 * step it is on. Rather than invent a percentage, `progress` is elapsed time
 * against the median duration of this install's own completed scans, and the
 * step is derived from that fraction. When no scan has ever completed there is
 * no basis for an estimate, so `progress` is null and callers show an
 * indeterminate state instead of a fake bar.
 */
export function useScan(onComplete?: () => void) {
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [baseline, setBaseline] = useState<number | null>(null);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  // Establish the duration baseline and adopt a scan already running elsewhere.
  useEffect(() => {
    api
      .getScans(20)
      .then((scans) => {
        setBaseline(medianDuration(scans));
        const latest = scans[0];
        if (latest?.status === "running") {
          setScanning(true);
          setStartedAt(parseApiDate(latest.started_at).getTime());
        }
      })
      .catch(() => {});
  }, []);

  // Poll for completion.
  useEffect(() => {
    if (!scanning) return;
    const id = setInterval(async () => {
      try {
        const scans = await api.getScans(1);
        const latest = scans[0];
        if (latest && latest.status !== "running") {
          setScanning(false);
          setStartedAt(null);
          setElapsed(0);
          onCompleteRef.current?.();
        }
      } catch {
        // A failed poll is not a failed scan; keep polling.
      }
    }, 3000);
    return () => clearInterval(id);
  }, [scanning]);

  // Tick the elapsed clock that drives the estimate.
  useEffect(() => {
    if (!scanning || startedAt == null) return;
    const id = setInterval(() => setElapsed(Date.now() - startedAt), 500);
    return () => clearInterval(id);
  }, [scanning, startedAt]);

  const trigger = useCallback(async () => {
    setError(null);
    try {
      const scan = await api.triggerScan();
      setScanning(true);
      setStartedAt(parseApiDate(scan.started_at).getTime());
      setElapsed(0);
    } catch (e) {
      setError(String(e));
    }
  }, []);

  // Capped just under 1 so the bar never reads "done" while still running.
  const progress =
    scanning && baseline
      ? Math.min(0.97, elapsed / baseline)
      : null;

  const step =
    progress == null
      ? null
      : SCAN_STEPS[Math.min(SCAN_STEPS.length - 1, Math.floor(progress * SCAN_STEPS.length))];

  return { scanning, progress, step, error, trigger, hasEstimate: baseline != null };
}
