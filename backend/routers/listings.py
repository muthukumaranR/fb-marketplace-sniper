from fastapi import APIRouter

from backend import db
from backend.models import DashboardStats, Listing

router = APIRouter(tags=["listings"])


@router.get("/listings", response_model=list[Listing])
async def get_listings(
    item_name: str | None = None,
    deal_quality: str | None = None,
    sort: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    """sort ∈ {final, relevance, deal, price, recent}. Default: recent."""
    return await db.get_listings(item_name, deal_quality, sort, limit, offset)


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard():
    watch_items = await db.get_watch_items()
    all_listings = await db.get_listings(limit=10000)
    deals = [l for l in all_listings if l["deal_quality"] in ("great", "good")]
    recent_deals = [l for l in all_listings if l["deal_quality"] in ("great", "good")][:10]
    scans = await db.get_scans(limit=1)
    last_scan = scans[0] if scans else None

    return DashboardStats(
        active_watches=len(watch_items),
        total_listings=len(all_listings),
        total_deals=len(deals),
        last_scan=last_scan,
        recent_deals=recent_deals,
    )
