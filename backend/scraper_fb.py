import random
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

from loguru import logger
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from backend.config import settings

# FB Marketplace location IDs for known cities
# You can find these by inspecting the URL when browsing marketplace in a location
LOCATION_SLUGS = {
    "huntsville, al": "huntsville",
    "birmingham, al": "birmingham",
    "nashville, tn": "nashville",
    "atlanta, ga": "atlanta",
    "new york, ny": "newyork",
    "san francisco, ca": "sanfrancisco",
    "los angeles, ca": "losangeles",
    "chicago, il": "chicago",
    "houston, tx": "houston",
    "seattle, wa": "seattle",
}


@dataclass
class FBListing:
    fb_id: str
    title: str
    price: float
    link: str
    thumbnail: str | None = None
    location: str | None = None


def _get_location_slug(location: str) -> str:
    """Convert a location string to FB marketplace URL slug."""
    normalized = location.lower().strip()
    if normalized in LOCATION_SLUGS:
        return LOCATION_SLUGS[normalized]
    # Fallback: use first word
    return normalized.split(",")[0].strip().replace(" ", "")


def _parse_price(text: str) -> float | None:
    """Extract numeric price from text like '$150' or 'Free'."""
    if not text:
        return None
    if "free" in text.lower():
        return 0.0
    match = re.search(r"\$?([\d,]+\.?\d*)", text.replace(",", ""))
    if match:
        return float(match.group(1))
    return None


def _extract_fb_id(href: str) -> str | None:
    """Extract listing ID from a marketplace URL."""
    match = re.search(r"/marketplace/item/(\d+)", href)
    return match.group(1) if match else None


async def init_fb_login():
    """Launch headed browser for user to log into Facebook. Saves session state."""
    state_path = settings.fb_state_resolved
    state_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Launching browser for Facebook login...")
    logger.info("Please log in to Facebook in the browser window.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()
        await page.goto("https://www.facebook.com/marketplace/", wait_until="domcontentloaded")

        logger.info("Waiting for you to log in... (press Enter in terminal when done)")
        input("Press Enter after logging in to Facebook...")

        await context.storage_state(path=str(state_path))
        logger.info("Facebook session saved to {}", state_path)
        await browser.close()

    return True


async def scrape_fb_marketplace(
    query: str,
    location: str | None = None,
    radius: int | None = None,
) -> list[FBListing]:
    """Scrape Facebook Marketplace listings for a query."""
    location = location or settings.default_location
    radius = radius or settings.default_radius
    state_path = settings.fb_state_resolved

    if not state_path.exists():
        logger.error("No Facebook session found. Run 'sniper init' first.")
        raise RuntimeError("Facebook session not found. Please log in first via /api/auth/fb-init")

    location_slug = _get_location_slug(location)
    search_url = (
        f"https://www.facebook.com/marketplace/{location_slug}/search?"
        f"query={quote_plus(query)}&exact=false"
    )
    logger.info("Scraping FB Marketplace: {} in {} ({}mi)", query, location, radius)

    listings: list[FBListing] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            context = await browser.new_context(
                storage_state=str(state_path),
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            page = await context.new_page()
            await Stealth().apply_stealth_async(page)

            # Intercept GraphQL responses as fallback data source
            graphql_listings: list[dict] = []

            async def handle_response(response):
                if "graphql" in response.url.lower() and response.status == 200:
                    try:
                        data = await response.json()
                        _extract_graphql_listings(data, graphql_listings)
                    except Exception:
                        pass

            page.on("response", handle_response)

            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            # Random delay for anti-bot
            await page.wait_for_timeout(random.randint(3000, 6000))

            # Check if redirected to login
            if "/login" in page.url:
                logger.error("Facebook session expired. Please re-login.")
                raise RuntimeError("Facebook session expired. Please log in again via /api/auth/fb-init")

            # Scroll to load more items
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 800)")
                await page.wait_for_timeout(random.randint(1000, 2000))

            # DOM parsing: find marketplace item links
            links = await page.query_selector_all('a[href*="/marketplace/item/"]')
            seen_ids: set[str] = set()

            for link_el in links:
                try:
                    href = await link_el.get_attribute("href") or ""
                    fb_id = _extract_fb_id(href)
                    if not fb_id or fb_id in seen_ids:
                        continue
                    seen_ids.add(fb_id)

                    # Walk up to the card container and extract text
                    card_text = await link_el.inner_text()
                    lines = [l.strip() for l in card_text.split("\n") if l.strip()]

                    price = None
                    title = ""
                    loc = None

                    for line in lines:
                        if price is None:
                            p = _parse_price(line)
                            if p is not None:
                                price = p
                                continue
                        if not title and price is not None:
                            title = line
                            continue
                        if title and not loc:
                            loc = line

                    if price is None or not title:
                        continue

                    # Get thumbnail
                    img = await link_el.query_selector("img")
                    thumbnail = None
                    if img:
                        thumbnail = await img.get_attribute("src")

                    full_link = f"https://www.facebook.com/marketplace/item/{fb_id}/"

                    listings.append(FBListing(
                        fb_id=fb_id,
                        title=title,
                        price=price,
                        link=full_link,
                        thumbnail=thumbnail,
                        location=loc,
                    ))
                except Exception as e:
                    logger.debug("Failed to parse FB listing: {}", e)
                    continue

            # If DOM parsing found nothing, try GraphQL data
            if not listings and graphql_listings:
                logger.info("DOM parsing found nothing, using GraphQL data ({} items)", len(graphql_listings))
                for gl in graphql_listings:
                    fb_id = gl.get("id", "")
                    if fb_id in seen_ids:
                        continue
                    seen_ids.add(fb_id)
                    listings.append(FBListing(
                        fb_id=fb_id,
                        title=gl.get("title", ""),
                        price=gl.get("price", 0.0),
                        link=f"https://www.facebook.com/marketplace/item/{fb_id}/",
                        thumbnail=gl.get("thumbnail"),
                        location=gl.get("location"),
                    ))

            logger.info("Found {} FB listings for '{}'", len(listings), query)
        finally:
            await browser.close()

    return listings


def _extract_graphql_listings(data: dict, results: list[dict]):
    """Recursively extract marketplace listing data from GraphQL responses."""
    if isinstance(data, dict):
        # Look for marketplace listing patterns
        if "marketplace_listing_title" in data or "listing_title" in data:
            title = data.get("marketplace_listing_title") or data.get("listing_title", "")
            price_info = data.get("listing_price", {})
            price_str = price_info.get("amount", "0") if isinstance(price_info, dict) else "0"
            listing_id = data.get("id", "")
            thumbnail = None
            if "primary_listing_photo" in data:
                photo = data["primary_listing_photo"]
                if isinstance(photo, dict):
                    thumbnail = photo.get("image", {}).get("uri")
            location_info = data.get("location", {})
            location_name = None
            if isinstance(location_info, dict):
                location_name = location_info.get("reverse_geocode", {}).get("city")

            results.append({
                "id": str(listing_id),
                "title": title,
                "price": float(price_str),
                "thumbnail": thumbnail,
                "location": location_name,
            })
        else:
            for v in data.values():
                _extract_graphql_listings(v, results)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                _extract_graphql_listings(item, results)
