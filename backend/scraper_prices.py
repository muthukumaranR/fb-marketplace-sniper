"""
Search-grounded price research.
Uses DuckDuckGo to gather context, then LLM to interpret.
Docker-friendly — curl_cffi only, no Playwright.
"""

import re
from urllib.parse import quote_plus, unquote

from curl_cffi.requests import AsyncSession
from loguru import logger


async def search_price_context(query: str) -> str:
    """
    Search DuckDuckGo for used price data on an item.
    Returns a text summary of search snippets + scraped page excerpts
    for the LLM to interpret.
    """
    search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}+used+price+sold"
    logger.info("Gathering price context for: {}", query)

    snippets: list[str] = []

    async with AsyncSession(impersonate="chrome") as s:
        r = await s.get(search_url, timeout=15)
        r.raise_for_status()
        html = r.text

        # Extract DDG result titles + snippets
        titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL)
        bodies = re.findall(r'class="result__snippet"[^>]*>(.*?)</(?:a|td)', html, re.DOTALL)

        for i, (title, body) in enumerate(zip(titles, bodies)):
            title_clean = re.sub(r'<[^>]+>', '', title).strip()
            body_clean = re.sub(r'<[^>]+>', '', body).strip()
            if title_clean or body_clean:
                snippets.append(f"[{i+1}] {title_clean}\n{body_clean}")

        # Follow top 2 non-JS-heavy links to get more price data
        raw_urls = re.findall(r'uddg=([^&"]+)', html)
        urls = []
        for raw in raw_urls:
            url = unquote(raw)
            if any(skip in url for skip in ["ebay.com", "amazon.com", "youtube.com", "reddit.com"]):
                continue
            if url.startswith("http") and url not in urls:
                urls.append(url)

        for url in urls[:2]:
            try:
                page = await s.get(url, timeout=8)
                if page.status_code != 200:
                    continue
                # Extract price-relevant text chunks from page
                page_text = _extract_price_text(page.text)
                if page_text:
                    snippets.append(f"[Page: {url[:60]}]\n{page_text}")
            except Exception as e:
                logger.debug("Failed to fetch {}: {}", url[:50], e)

    context = "\n\n".join(snippets[:10])
    logger.info("Gathered {} snippets of price context for '{}'", len(snippets), query)
    return context


def _extract_price_text(html: str) -> str:
    """Extract text chunks near dollar amounts from HTML — gives LLM context."""
    # Strip scripts/styles
    clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', clean)
    text = re.sub(r'\s+', ' ', text)

    # Find chunks around dollar amounts
    chunks: list[str] = []
    for m in re.finditer(r'\$\d[\d,.]+', text):
        start = max(0, m.start() - 80)
        end = min(len(text), m.end() + 80)
        chunk = text[start:end].strip()
        if len(chunk) > 20:
            chunks.append(chunk)

    # Deduplicate similar chunks and limit
    seen = set()
    unique: list[str] = []
    for c in chunks:
        key = c[:40]
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return "\n".join(unique[:15])
