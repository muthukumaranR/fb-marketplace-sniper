import { useEffect, useState } from "react";
import { api, type ScanResult } from "../api";

export default function History() {
  const [scans, setScans] = useState<ScanResult[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getScans(50).then(setScans).finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-gray-400 py-12 text-center">Loading...</p>;

  const statusColor: Record<string, string> = {
    completed: "bg-green-100 text-green-700",
    running: "bg-yellow-100 text-yellow-700",
    failed: "bg-red-100 text-red-700",
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-left text-gray-500">
            <th className="py-3 px-4 font-medium">ID</th>
            <th className="py-3 px-4 font-medium">Status</th>
            <th className="py-3 px-4 font-medium">Started</th>
            <th className="py-3 px-4 font-medium">Completed</th>
            <th className="py-3 px-4 font-medium text-right">Items Scanned</th>
            <th className="py-3 px-4 font-medium text-right">New Listings</th>
            <th className="py-3 px-4 font-medium text-right">Deals Found</th>
          </tr>
        </thead>
        <tbody>
          {scans.length === 0 ? (
            <tr>
              <td colSpan={7} className="py-12 text-center text-gray-400">
                No scan history yet. Trigger a scan from the Dashboard.
              </td>
            </tr>
          ) : (
            scans.map((s) => (
              <tr key={s.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="py-3 px-4 font-mono text-gray-400">#{s.id}</td>
                <td className="py-3 px-4">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusColor[s.status] || ""}`}>
                    {s.status}
                  </span>
                </td>
                <td className="py-3 px-4 text-gray-600">
                  {new Date(s.started_at).toLocaleString()}
                </td>
                <td className="py-3 px-4 text-gray-600">
                  {s.completed_at ? new Date(s.completed_at).toLocaleString() : "—"}
                </td>
                <td className="py-3 px-4 text-right font-mono">{s.items_scanned}</td>
                <td className="py-3 px-4 text-right font-mono">{s.new_listings}</td>
                <td className="py-3 px-4 text-right font-mono font-bold text-green-600">
                  {s.deals_found}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
