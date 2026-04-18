import asyncio
import json

from loguru import logger

from backend import db
from backend.celery_app import app
from backend.config import settings
from backend.notifier import send_deal_email
from backend.pricer import evaluate_deal, get_fair_price
from backend.relevance import (
    FacetSpec,
    combine_scores,
    extract_query_facets,
    price_score,
    score_listing,
)
from backend.scraper_fb import scrape_fb_marketplace


def _run_async(coro):
    """Run an async function from sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@app.task(bind=True, name="backend.tasks.scan_all")
def scan_all(self, scan_id: int | None = None):
    """Run a full scan cycle for all watchlist items."""
    logger.info("Starting full scan cycle")
    _run_async(_scan_all_async(scan_id))


async def _scan_all_async(scan_id: int | None = None):
    await db.init_db()

    if scan_id is None:
        scan = await db.create_scan()
        scan_id = scan["id"]

    watch_items = await db.get_watch_items()
    if not watch_items:
        logger.info("No watch items configured, skipping scan")
        await db.update_scan(scan_id, status="completed", items_scanned=0)
        return

    total_deals = 0
    total_new = 0

    for item in watch_items:
        try:
            item_deals, item_new = await _scan_single_item(item)
            total_deals += item_deals
            total_new += item_new
        except Exception as e:
            logger.error("Failed to scan '{}': {}", item["name"], e)

    await db.update_scan(
        scan_id,
        status="completed",
        items_scanned=len(watch_items),
        deals_found=total_deals,
        new_listings=total_new,
    )
    logger.info("Scan complete: {} items, {} new listings, {} deals", len(watch_items), total_new, total_deals)


async def _scan_single_item(item: dict) -> tuple[int, int]:
    """Scan FB Marketplace for a single watchlist item. Returns (deals_found, new_listings)."""
    name = item["name"]
    location = item["location"]
    radius = item["radius"]
    max_price = item.get("max_price")

    # Get fair price
    price_est = await get_fair_price(name)
    fair_price = price_est.median_price

    # Extract facets once per watch item (cached after first LLM call)
    facet_spec: FacetSpec | None = None
    try:
        facet_spec = await extract_query_facets(name)
    except Exception as e:
        logger.warning(
            "Facet extraction failed for '{}': {} — continuing without relevance scoring",
            name, e,
        )

    # Scrape FB
    fb_listings = await scrape_fb_marketplace(name, location, radius)

    deals_found = 0
    new_listings = 0

    for fl in fb_listings:
        deal_quality, discount_pct = evaluate_deal(fl.price, fair_price)

        # Check max_price constraint too
        if max_price and fl.price > max_price:
            deal_quality = "none"
            discount_pct = 0.0

        # Relevance scoring (title-only for now; description not in scraper output).
        # Skip when facet list is empty — the LLM gave us no structured signal, so
        # treat relevance as unknown (None) rather than zero, letting price rule.
        relevance_val: float | None = None
        match_details_json: str | None = None
        rejected = False
        if facet_spec is not None and facet_spec.facets:
            match = score_listing(facet_spec, fl.title, price=fl.price, max_price=max_price)
            relevance_val = match.score
            match_details_json = json.dumps(match.to_dict())
            rejected = match.rejected

        # If rejected (required facet miss or price cap), don't show misleading deal
        # badges — the listing is either the wrong item or over budget.
        if rejected:
            deal_quality = "none"
            discount_pct = 0.0

        p_score = price_score(fl.price, fair_price)
        final_sc = combine_scores(relevance_val, p_score)

        result = await db.upsert_listing(
            fb_id=fl.fb_id,
            title=fl.title,
            price=fl.price,
            link=fl.link,
            item_name=name,
            fair_price=fair_price,
            discount_pct=discount_pct,
            deal_quality=deal_quality,
            thumbnail=fl.thumbnail,
            location=fl.location,
            relevance_score=relevance_val,
            final_score=final_sc,
            match_details=match_details_json,
        )

        if result is None:
            continue  # Already seen

        new_listings += 1

        if deal_quality in ("great", "good"):
            deals_found += 1
            # Gate notifications by relevance — skip emails when the title
            # clearly doesn't match the watch item. Fail open if unscored.
            if relevance_val is not None and relevance_val < settings.notify_min_relevance:
                logger.info(
                    "Suppressing {} email for low-relevance listing '{}' (score={})",
                    deal_quality, fl.title, relevance_val,
                )
                continue
            try:
                send_deal_email(
                    item_name=name,
                    listing_title=fl.title,
                    listing_price=fl.price,
                    fair_price=fair_price,
                    discount_pct=discount_pct,
                    deal_quality=deal_quality,
                    link=fl.link,
                    thumbnail=fl.thumbnail,
                )
            except Exception as e:
                logger.error("Failed to send notification for '{}': {}", fl.title, e)

    logger.info("'{}': {} new listings, {} deals", name, new_listings, deals_found)
    return deals_found, new_listings


@app.task(name="backend.tasks.scan_item")
def scan_item(item_id: int):
    """Scan a single watchlist item."""
    _run_async(_scan_item_async(item_id))


async def _scan_item_async(item_id: int):
    await db.init_db()
    item = await db.get_watch_item(item_id)
    if not item:
        logger.error("Watch item {} not found", item_id)
        return
    await _scan_single_item(item)


@app.task(name="backend.tasks.refresh_prices")
def refresh_prices(item_name: str):
    """Refresh cached price for an item."""
    _run_async(_refresh_prices_async(item_name))


async def _refresh_prices_async(item_name: str):
    await db.init_db()
    await get_fair_price(item_name, force_refresh=True)
    logger.info("Refreshed price for '{}'", item_name)
