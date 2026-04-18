"""
Integration tests for backend/tasks.py _scan_single_item — the pipeline fix
checkpoints. Scraper, pricer, facet extractor, and notifier are all patched.
"""

import asyncio
import json
import os
import tempfile
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DB_PATH"] = _tmp.name

from backend import db
from backend.models import PriceEstimate, PriceSource
from backend.relevance import Facet, FacetSpec
from backend.scraper_fb import FBListing

db.DB_PATH = _tmp.name


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def setup_db():
    run(db.init_db())
    yield

    async def cleanup():
        conn = await db.get_db()
        try:
            await conn.execute("DELETE FROM watchlist")
            await conn.execute("DELETE FROM listings")
            await conn.execute("DELETE FROM price_cache")
            await conn.execute("DELETE FROM scans")
            await conn.execute("DELETE FROM query_facets_cache")
            await conn.commit()
        finally:
            await conn.close()

    run(cleanup())


def _fake_price(item_name: str = "iPhone 15 Pro") -> PriceEstimate:
    return PriceEstimate(
        item_name=item_name,
        median_price=800.0,
        low_price=500.0,
        high_price=1100.0,
        sample_count=10,
        source=PriceSource.ebay,
        estimated_at=datetime.now(UTC),
    )


def _fake_spec() -> FacetSpec:
    return FacetSpec(
        query="iPhone 15 Pro 256GB",
        facets=[
            Facet(key="model", value="iPhone 15 Pro", weight=0.6, required=True),
            Facet(key="storage", value="256GB", weight=0.4, required=False),
        ],
    )


def _fb(fb_id: str, title: str, price: float) -> FBListing:
    return FBListing(fb_id=fb_id, title=title, price=price, link=f"https://fb/{fb_id}")


class TestScanSingleItemFixes:
    """Verifies the three post-implementation bug fixes."""

    def test_rejected_listing_gets_no_deal_badge(self):
        """Listing with wrong model (required-facet miss) must NOT carry deal_quality."""

        item = run(db.add_watch_item("iPhone 15 Pro 256GB", None, "Huntsville, AL", 20))

        fb_listings = [
            # Wrong model but great price — should be rejected + deal_quality="none"
            _fb("1", "iPhone 14 256GB mint", 350.0),
            # Correct model and storage, great price — should be great deal
            _fb("2", "iPhone 15 Pro 256GB sealed", 350.0),
        ]

        async def scenario():
            from backend import tasks
            with (
                patch.object(tasks, "get_fair_price", AsyncMock(return_value=_fake_price())),
                patch.object(tasks, "extract_query_facets", AsyncMock(return_value=_fake_spec())),
                patch.object(tasks, "scrape_fb_marketplace", AsyncMock(return_value=fb_listings)),
                patch.object(tasks, "send_deal_email"),
            ):
                return await tasks._scan_single_item(item)

        deals_found, new_listings = run(scenario())
        assert new_listings == 2
        # Only the correctly-matching listing counts as a deal
        assert deals_found == 1

        rows = run(db.get_listings(item_name="iPhone 15 Pro 256GB"))
        by_id = {r["fb_id"]: r for r in rows}
        assert by_id["1"]["deal_quality"] == "none"
        assert by_id["1"]["discount_pct"] == 0.0
        assert by_id["1"]["relevance_score"] == 0.0
        md1 = json.loads(by_id["1"]["match_details"])
        assert md1["rejected"] is True
        assert md1["reject_reason"] and "model" in md1["reject_reason"]

        assert by_id["2"]["deal_quality"] == "great"
        assert by_id["2"]["relevance_score"] == 1.0
        assert by_id["2"]["final_score"] == 1.0

    def test_deals_found_counts_pre_gating(self):
        """deals_found should count deal-quality listings even when email is suppressed."""

        item = run(db.add_watch_item("iPhone 15 Pro 256GB", None, "Huntsville, AL", 20))

        # Listing: model matches (required passes) but storage misses → relevance=0.6
        # Price at 40% off fair price → deal_quality="great"
        # 0.6 > default notify_min_relevance (0.5) — so this actually DOES notify. Test a stricter threshold.
        fb_listings = [_fb("3", "iPhone 15 Pro 128GB", 320.0)]

        async def scenario():
            from backend import tasks
            from backend.config import settings
            orig = settings.notify_min_relevance
            settings.notify_min_relevance = 0.8  # raise the bar so 0.6 is suppressed
            try:
                email = AsyncMock()
                with (
                    patch.object(tasks, "get_fair_price", AsyncMock(return_value=_fake_price())),
                    patch.object(tasks, "extract_query_facets", AsyncMock(return_value=_fake_spec())),
                    patch.object(tasks, "scrape_fb_marketplace", AsyncMock(return_value=fb_listings)),
                    patch.object(tasks, "send_deal_email", email),
                ):
                    result = await tasks._scan_single_item(item)
                return result, email
            finally:
                settings.notify_min_relevance = orig

        (deals_found, new_listings), email = run(scenario())
        assert new_listings == 1
        # Still counted as a deal (price is great), email was suppressed by gating
        assert deals_found == 1
        email.assert_not_called()

        rows = run(db.get_listings(item_name="iPhone 15 Pro 256GB"))
        assert rows[0]["deal_quality"] == "great"
        # 0.4 (storage miss only) → wait: storage weight is 0.4; matched model (0.6) → 0.6
        assert rows[0]["relevance_score"] == 0.6

    def test_empty_facet_spec_falls_back_to_price(self):
        """If the LLM returns no facets, final_score should track price, not be zeroed."""

        item = run(db.add_watch_item("weird obscure thing", None, "Huntsville, AL", 20))

        empty_spec = FacetSpec(query="weird obscure thing", facets=[])
        fb_listings = [_fb("4", "Whatever", 200.0)]  # 25% of fair → great price

        async def scenario():
            from backend import tasks
            with (
                patch.object(tasks, "get_fair_price", AsyncMock(return_value=_fake_price())),
                patch.object(tasks, "extract_query_facets", AsyncMock(return_value=empty_spec)),
                patch.object(tasks, "scrape_fb_marketplace", AsyncMock(return_value=fb_listings)),
                patch.object(tasks, "send_deal_email"),
            ):
                await tasks._scan_single_item(item)

        run(scenario())
        rows = run(db.get_listings(item_name="weird obscure thing"))
        # Relevance is unknown (None) — should not be persisted as zero
        assert rows[0]["relevance_score"] is None
        # Final score falls through to price attractiveness (not zero)
        assert rows[0]["final_score"] is not None
        assert rows[0]["final_score"] > 0
        # match_details is None because scoring was skipped
        assert rows[0]["match_details"] is None
