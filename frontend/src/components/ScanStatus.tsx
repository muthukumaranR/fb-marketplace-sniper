import { useEffect, useRef, useState } from "react";
import { api, type ScanResult } from "../api";

interface Props {
  lastScan: ScanResult | null;
  fbConnected: boolean;
  hasWatchItems: boolean;
  onScanTriggered?: () => void;
}

export default function ScanStatus({
  lastScan,
  fbConnected,
  hasWatchItems,
  onScanTriggered,
}: Props) {
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeScanId, setActiveScanId] = useState<number | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const canScan = fbConnected && hasWatchItems;

  // Poll for scan completion when a scan is running
  useEffect(() => {
    if (!activeScanId) return;

    pollRef.current = setInterval(async () => {
      try {
        const scans = await api.getScans(1);
        const latest = scans[0];
        if (latest && latest.status !== "running") {
          setActiveScanId(null);
          onScanTriggered?.();
        }
      } catch {
        // ignore poll errors
      }
    }, 3000);

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [activeScanId, onScanTriggered]);

  const handleTrigger = async () => {
    setTriggering(true);
    setError(null);
    try {
      const scan = await api.triggerScan();
      setActiveScanId(scan.id);
      onScanTriggered?.();
    } catch (e) {
      setError(String(e));
    } finally {
      setTriggering(false);
    }
  };

  const statusColor =
    lastScan?.status === "completed"
      ? "bg-green-100 text-green-700"
      : lastScan?.status === "running"
        ? "bg-yellow-100 text-yellow-700"
        : lastScan?.status === "failed"
          ? "bg-red-100 text-red-700"
          : "bg-gray-100 text-gray-500";

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-gray-900">Marketplace Scanner</h3>
          {lastScan ? (
            <div className="flex items-center gap-2 mt-2">
              <span
                className={`px-2 py-0.5 rounded text-xs font-medium ${statusColor}`}
              >
                {lastScan.status}
              </span>
              <span className="text-sm text-gray-500">
                {new Date(lastScan.started_at).toLocaleString()} &mdash;{" "}
                {lastScan.items_scanned} items, {lastScan.new_listings} new,{" "}
                {lastScan.deals_found} deals
              </span>
            </div>
          ) : (
            <p className="text-sm text-gray-400 mt-1">
              No scans yet — run your first scan to find deals
            </p>
          )}
          {error && (
            <p className="text-sm text-red-500 mt-1">{error}</p>
          )}
        </div>
        <div className="flex flex-col items-end gap-1">
          <button
            onClick={handleTrigger}
            disabled={triggering || !!activeScanId || !canScan}
            className="px-5 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {triggering ? "Starting..." : activeScanId ? "Scanning..." : "Scan Now"}
          </button>
          {!canScan && (
            <p className="text-xs text-gray-400">
              {!fbConnected
                ? "Connect Facebook first"
                : "Add watchlist items first"}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
