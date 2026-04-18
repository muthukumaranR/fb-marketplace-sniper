import { proxyImageUrl, type Listing } from "../api";

interface Props {
  listings: Listing[];
  showItemName?: boolean;
  emptyMessage?: string;
  compact?: boolean;
}

const dealStyles: Record<string, { border: string; bg: string; badge: string; label: string }> = {
  great: {
    border: "border-red-200",
    bg: "bg-red-50/40",
    badge: "bg-red-600 text-white",
    label: "GREAT DEAL",
  },
  good: {
    border: "border-amber-200",
    bg: "bg-amber-50/30",
    badge: "bg-amber-500 text-white",
    label: "Good Deal",
  },
  fair: {
    border: "border-gray-200",
    bg: "bg-white",
    badge: "bg-blue-100 text-blue-700",
    label: "Fair",
  },
  none: {
    border: "border-gray-200",
    bg: "bg-white",
    badge: "bg-gray-100 text-gray-400",
    label: "",
  },
};

export default function ListingsTable({
  listings,
  showItemName = true,
  emptyMessage,
  compact = false,
}: Props) {
  if (listings.length === 0) {
    return (
      <div className="text-center py-16">
        <p className="text-gray-400 text-lg">No listings found</p>
        <p className="text-gray-300 text-sm mt-1">
          {emptyMessage || "Run a scan to search for listings matching your watchlist items"}
        </p>
      </div>
    );
  }

  return (
    <div className={`grid gap-3 ${compact ? "" : "sm:grid-cols-2"}`}>
      {listings.map((l) => {
        const style = dealStyles[l.deal_quality] || dealStyles.none;
        const imgSrc = proxyImageUrl(l.thumbnail);
        return (
          <a
            key={l.id}
            href={l.link}
            target="_blank"
            rel="noopener noreferrer"
            className={`flex gap-4 p-4 rounded-xl border transition-all hover:shadow-md ${style.border} ${style.bg}`}
          >
            {/* Thumbnail */}
            <div className={`${compact ? "w-16 h-16" : "w-24 h-24"} rounded-lg bg-gray-100 flex-shrink-0 overflow-hidden`}>
              {imgSrc ? (
                <img
                  src={imgSrc}
                  alt=""
                  className="w-full h-full object-cover"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = "none";
                  }}
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-gray-300 text-xl">
                  ?
                </div>
              )}
            </div>

            {/* Info */}
            <div className="flex-1 min-w-0">
              {/* Watch item tag + deal badge */}
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                {showItemName && (
                  <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-indigo-100 text-indigo-700">
                    {l.item_name}
                  </span>
                )}
                {style.label && (
                  <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${style.badge}`}>
                    {style.label}
                  </span>
                )}
              </div>
              <h3 className={`font-medium text-gray-900 ${compact ? "text-sm truncate" : "line-clamp-2"}`}>
                {l.title}
              </h3>
              <div className="flex items-center gap-3 mt-1.5 text-xs text-gray-400">
                {l.location && <span>{l.location}</span>}
                <span>{new Date(l.first_seen).toLocaleDateString()}</span>
              </div>
            </div>

            {/* Price column */}
            <div className="text-right flex-shrink-0 flex flex-col justify-center">
              <p className={`${compact ? "text-xl" : "text-2xl"} font-bold text-gray-900`}>
                ${l.price.toFixed(0)}
              </p>
              {l.fair_price != null && l.fair_price > 0 && (
                <p className="text-xs text-gray-400 mt-0.5">
                  Fair ${l.fair_price.toFixed(0)}
                </p>
              )}
              {l.discount_pct != null && l.discount_pct > 0 && (
                <p className="text-xs font-bold text-green-600">
                  {l.discount_pct.toFixed(0)}% off
                </p>
              )}
            </div>
          </a>
        );
      })}
    </div>
  );
}
