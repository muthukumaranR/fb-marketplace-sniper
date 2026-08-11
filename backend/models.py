from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class DealQuality(str, Enum):
    great = "great"
    good = "good"
    fair = "fair"
    none = "none"


class PriceSource(str, Enum):
    ebay = "ebay"
    llm = "llm"


class ScanStatus(str, Enum):
    running = "running"
    completed = "completed"
    failed = "failed"


# --- Request models ---


class WatchItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    max_price: float | None = None
    location: str | None = None
    radius: int | None = None


class WatchItemUpdate(BaseModel):
    name: str | None = None
    max_price: float | None = None
    location: str | None = None
    radius: int | None = None


# --- Response models ---


class WatchItem(BaseModel):
    id: int
    name: str
    max_price: float | None = None
    location: str
    radius: int
    created_at: datetime


class Listing(BaseModel):
    id: int
    fb_id: str
    title: str
    price: float
    fair_price: float | None = None
    discount_pct: float | None = None
    deal_quality: DealQuality = DealQuality.none
    link: str
    thumbnail: str | None = None
    location: str | None = None
    item_name: str
    first_seen: datetime
    relevance_score: float | None = None
    final_score: float | None = None
    match_details: str | None = None


class PriceEstimate(BaseModel):
    """
    A fair-price estimate. Every deal decision divides by `median_price`, so an
    implausible value here becomes a week of wrong alerts — it is validated at
    construction regardless of which source produced it.
    """
    item_name: str
    median_price: float = Field(..., gt=0)
    low_price: float | None = Field(None, ge=0)
    high_price: float | None = Field(None, ge=0)
    sample_count: int
    source: PriceSource
    estimated_at: datetime
    sold_prices: list[float] = []

    @model_validator(mode="after")
    def _check_band(self):
        if self.low_price is not None and self.low_price > self.median_price:
            raise ValueError(
                f"low_price {self.low_price} exceeds median_price {self.median_price}"
            )
        if self.high_price is not None and self.high_price < self.median_price:
            raise ValueError(
                f"high_price {self.high_price} is below median_price {self.median_price}"
            )
        return self


class ScanResult(BaseModel):
    id: int
    started_at: datetime
    completed_at: datetime | None = None
    items_scanned: int = 0
    deals_found: int = 0
    new_listings: int = 0
    status: ScanStatus


class DashboardStats(BaseModel):
    active_watches: int
    total_listings: int
    total_deals: int
    last_scan: ScanResult | None = None
    recent_deals: list[Listing] = []
