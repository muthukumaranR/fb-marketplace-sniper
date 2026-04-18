import re
from urllib.parse import quote_plus

from loguru import logger
from playwright.async_api import async_playwright


async def scrape_ebay_sold_prices(query: str, max_results: int = 20) -> list[float]:
    """Scrape eBay completed/sold listings for a query. Returns list of sold prices."""
    url = (
        f"https://www.ebay.com/sch/i.html?_nkw={quote_plus(query)}"
        f"&LH_Complete=1&LH_Sold=1&_sop=13&rt=nc"
    )
    logger.info("Scraping eBay sold prices for: {}", query)

    prices: list[float] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--single-process",
            ],
        )
        try:
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                java_script_enabled=True,
            )
            page = await context.new_page()

            # Block images/fonts/media to reduce memory
            await page.route("**/*.{png,jpg,jpeg,gif,svg,webp,woff,woff2,ttf}", lambda route: route.abort())

            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(5000)

            # eBay 2025+ uses s-card__price class
            price_els = await page.query_selector_all(".s-card__price")

            # Fallback to legacy s-item__price
            if not price_els:
                price_els = await page.query_selector_all(".s-item__price")

            for el in price_els[:max_results]:
                try:
                    price_text = await el.inner_text()
                    if "delivery" in price_text.lower() or "shipping" in price_text.lower():
                        continue
                    nums = re.findall(r"\$?([\d,]+\.?\d*)", price_text)
                    if not nums:
                        continue
                    parsed = [float(n.replace(",", "")) for n in nums]
                    price = sum(parsed) / len(parsed)
                    if price > 0:
                        prices.append(price)
                except Exception as e:
                    logger.debug("Failed to parse eBay item: {}", e)
                    continue

            logger.info("Found {} sold prices for '{}'", len(prices), query)
        finally:
            await browser.close()

    return prices
