import { priceScore, type Listing } from "../api";

interface Props {
  listing: Listing;
  /** 5px in the listing row, 7px in the drawer. */
  height?: number;
  /** The drawer pins a tick at the fair-price end. */
  showFairTick?: boolean;
}

/**
 * Price as a fraction of fair price. Over fair reads red; a genuinely
 * attractive price (price_score >= .3) reads strong, otherwise amber.
 */
export default function PriceVsFair({
  listing,
  height = 5,
  showFairTick = false,
}: Props) {
  const fair = listing.fair_price;
  const hasFair = !!fair && fair > 0;
  const ratio = hasFair ? listing.price / fair : 0;
  const over = ratio > 1;
  const ps = priceScore(listing);

  const fill = over
    ? "var(--color-weak)"
    : (ps ?? 0) >= 0.3
      ? "var(--color-strong)"
      : "var(--color-middling)";

  return (
    <div className="w-full">
      <div
        className="relative w-full overflow-hidden rounded-full bg-track-deep"
        style={{ height }}
      >
        <div
          className="h-full rounded-full transition-[width] duration-300"
          style={{
            width: hasFair ? `${Math.min(100, ratio * 100)}%` : 0,
            background: hasFair ? fill : "transparent",
          }}
        />
        {showFairTick && hasFair && (
          <div
            className="absolute top-0 h-full w-0.5 bg-fg2"
            style={{ right: 0 }}
          />
        )}
      </div>
      <div className="mt-1 font-mono text-[11px] text-fg3">
        {hasFair ? `fair $${Math.round(fair)}` : "no estimate"}
      </div>
    </div>
  );
}
