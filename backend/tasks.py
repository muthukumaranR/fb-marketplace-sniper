import asyncio

from loguru import logger

from backend import db
from backend.celery_app import app
from backend.notifier import send_deal_email
from backend.config import settings
from backend.pricer import evaluate_deal, get_fair_price
from backend.relevance import (
    combine_scores,
    extract_query_facets,
    price_score,
    score_listing,
)
from backend.scraper_fb import fetch_listing_descriptions, scrape_fb_marketplace


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


async def _fetch_candidate_descriptions(
    fb_listings: list, spec, fair_price: float, item: dict
) -> dict[str, str]:
    """
    Read the full listing body — but only where it can change the outcome.

    A detail page per listing is a page load and a bot-detection risk, so this
    skips listings already stored, already disqualified by title, or not priced
    like a deal. Those keep their title-only score; nothing about them turns on
    the body. What is left is exactly the set about to trigger an email, which
    is where a "controller only" buried in the description matters.
    """
    candidates = [
        fl for fl in fb_listings
        if evaluate_deal(fl.price, fair_price)[0] in ("great", "good")
        and not (item.get("max_price") and fl.price > item["max_price"])
        and score_listing(fl.title, spec).score >= settings.notify_min_relevance
    ]
    if not candidates:
        return {}

    already_seen = await db.existing_fb_ids([fl.fb_id for fl in candidates])
    to_fetch = [fl.fb_id for fl in candidates if fl.fb_id not in already_seen]
    if not to_fetch:
        return {}

    logger.info(
        "Reading full listing body for {} of {} results for '{}'",
        len(to_fetch), len(fb_listings), item["name"],
    )
    try:
        return await fetch_listing_descriptions(to_fetch)
    except Exception as e:
        logger.warning("Description fetch failed for '{}': {} — scoring on titles", item["name"], e)
        return {}


async def _scan_single_item(item: dict) -> tuple[int, int]:
    """Scan FB Marketplace for a single watchlist item. Returns (deals_found, new_listings)."""
    name = item["name"]
    location = item["location"]
    radius = item["radius"]

    # Get fair price
    price_est = await get_fair_price(name)
    fair_price = price_est.median_price

    # One LLM call per watch term, cached 30 days — scoring below is offline
    spec = await extract_query_facets(name)

    # Scrape FB
    fb_listings = await scrape_fb_marketplace(name, location, radius)

    descriptions = await _fetch_candidate_descriptions(fb_listings, spec, fair_price, item)

    deals_found = 0
    new_listings = 0

    for fl in fb_listings:
        deal_quality, discount_pct = evaluate_deal(fl.price, fair_price)

        # Check max_price constraint too
        if item.get("max_price") and fl.price > item["max_price"]:
            deal_quality = "none"
            discount_pct = 0.0

        match = score_listing(fl.title, spec, descriptions.get(fl.fb_id))
        final = combine_scores(match.score, price_score(fl.price, fair_price))

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
            relevance_score=match.score,
            final_score=final,
            match_details=match.as_json(),
        )

        if result is None:
            continue  # Already seen

        new_listings += 1

        # A great price on the wrong item is not a deal. Persist it either way
        # so it stays visible in the UI, but do not spend an email on it.
        if match.score < settings.notify_min_relevance:
            logger.info(
                "Skipping notification for '{}' — relevance {:.2f} < {:.2f}{}",
                fl.title, match.score, settings.notify_min_relevance,
                f" (excluded by '{match.excluded_by}')" if match.excluded_by else "",
            )
            continue

        if deal_quality in ("great", "good"):
            deals_found += 1
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
