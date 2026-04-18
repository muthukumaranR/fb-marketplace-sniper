import json
import os
import statistics
from datetime import datetime

from litellm import acompletion
from loguru import logger

from backend import db
from backend.config import settings
from backend.models import PriceEstimate, PriceSource
from backend.scraper_ebay import scrape_ebay_sold_prices
from backend.scraper_prices import search_price_context


def _configure_llm_env():
    """Push API keys into env so litellm can pick them up."""
    if settings.gemini_api_key:
        os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
    if settings.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key


async def _estimate_with_search(item_name: str) -> PriceEstimate:
    """
    Primary method: search the web for price data, then ask LLM to interpret.
    The LLM sees real search results and extracts a fair used price.
    """
    _configure_llm_env()
    model = settings.resolved_llm_model

    # Gather web context
    context = await search_price_context(item_name)

    if not context.strip():
        logger.warning("No search context found for '{}', using LLM knowledge only", item_name)
        context = "(No web results available — use your knowledge)"

    prompt = f"""I need to know the fair USED price for: "{item_name}"

Here are web search results about this item's pricing:

{context}

Based on these search results and your knowledge, what is the typical price someone pays for a USED "{item_name}" in good condition on the secondhand market (Facebook Marketplace, Craigslist, eBay, etc)?

Return ONLY a JSON object: {{"low": <number>, "median": <number>, "high": <number>}}
- low = bargain/great deal price
- median = typical fair used price
- high = top end used price
Prices in USD. No explanation, just the JSON."""

    logger.info("Asking {} to estimate price for '{}' with {} chars of context", model, item_name, len(context))

    response = await acompletion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        timeout=30,
    )
    text = response.choices[0].message.content.strip()

    # Extract JSON
    if "```" in text:
        text = text.split("```")[1].strip()
        if text.startswith("json"):
            text = text[4:].strip()
    parsed = json.loads(text)

    estimate = PriceEstimate(
        item_name=item_name,
        median_price=parsed["median"],
        low_price=parsed.get("low"),
        high_price=parsed.get("high"),
        sample_count=0,
        source=PriceSource.llm,
        estimated_at=datetime.utcnow(),
    )

    await db.save_price_cache(
        item_name=item_name,
        median_price=estimate.median_price,
        sample_count=0,
        source="llm",
        low_price=estimate.low_price,
        high_price=estimate.high_price,
    )
    logger.info(
        "Search-grounded estimate for '{}': ${:.0f} (range ${:.0f}-${:.0f}) via {}",
        item_name, estimate.median_price,
        estimate.low_price or 0, estimate.high_price or 0, model,
    )
    return estimate


async def get_fair_price(item_name: str, force_refresh: bool = False) -> PriceEstimate:
    """
    Get fair market price for an item.
    Chain: cache → search-grounded LLM → eBay Playwright → bare LLM.
    """
    if not force_refresh:
        cached = await db.get_cached_price(item_name)
        if cached:
            logger.info("Using cached price for '{}': ${:.2f}", item_name, cached["median_price"])
            sold_prices = json.loads(cached["sold_prices"]) if cached.get("sold_prices") else []
            return PriceEstimate(
                item_name=cached["item_name"],
                median_price=cached["median_price"],
                low_price=cached.get("low_price"),
                high_price=cached.get("high_price"),
                sample_count=cached["sample_count"],
                source=PriceSource(cached["source"]),
                estimated_at=datetime.fromisoformat(cached["estimated_at"]),
                sold_prices=sold_prices,
            )

    # Primary: search-grounded LLM (web search + LLM interpretation)
    try:
        return await _estimate_with_search(item_name)
    except Exception as e:
        logger.warning("Search-grounded estimation failed for '{}': {}", item_name, e)

    # Fallback: eBay Playwright (works locally, may fail in Docker)
    try:
        prices = await scrape_ebay_sold_prices(item_name)
        if len(prices) >= 3:
            median = statistics.median(prices)
            est = PriceEstimate(
                item_name=item_name,
                median_price=median,
                low_price=min(prices),
                high_price=max(prices),
                sample_count=len(prices),
                source=PriceSource.ebay,
                estimated_at=datetime.utcnow(),
                sold_prices=prices,
            )
            try:
                await db.save_price_cache(
                    item_name=item_name,
                    median_price=median,
                    sample_count=len(prices),
                    source="ebay",
                    low_price=min(prices),
                    high_price=max(prices),
                    sold_prices=json.dumps(prices),
                )
            except Exception:
                pass  # Cache write failure shouldn't block returning the estimate
            logger.info("eBay price for '{}': ${:.2f} (n={})", item_name, median, len(prices))
            return est
    except Exception as e:
        logger.warning("eBay scraping failed for '{}': {}", item_name, e)

    raise RuntimeError(f"Could not estimate price for '{item_name}': all sources failed")


def evaluate_deal(listing_price: float, fair_price: float) -> tuple[str, float]:
    """Evaluate deal quality. Returns (quality, discount_pct)."""
    if fair_price <= 0:
        return "none", 0.0

    ratio = listing_price / fair_price
    discount_pct = round((1 - ratio) * 100, 1)

    if ratio <= settings.great_deal_threshold:
        return "great", discount_pct
    elif ratio <= settings.good_deal_threshold:
        return "good", discount_pct
    elif ratio <= 1.0:
        return "fair", discount_pct
    else:
        return "none", discount_pct
