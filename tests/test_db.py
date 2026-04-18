import asyncio
import os
import tempfile

import pytest

# Override DB_PATH before importing db module
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DB_PATH"] = _tmp.name

from backend import db

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
            await conn.commit()
        finally:
            await conn.close()

    run(cleanup())


class TestWatchlist:
    def test_add_and_list(self):
        item = run(db.add_watch_item("PS5", 300.0, "Huntsville, AL", 20))
        assert item["name"] == "PS5"
        assert item["max_price"] == 300.0
        assert item["location"] == "Huntsville, AL"
        assert item["radius"] == 20

        items = run(db.get_watch_items())
        assert len(items) == 1
        assert items[0]["name"] == "PS5"

    def test_add_without_max_price(self):
        item = run(db.add_watch_item("KitchenAid Mixer", None, "Nashville, TN", 30))
        assert item["max_price"] is None

    def test_delete(self):
        item = run(db.add_watch_item("Test Item", None, "Location", 10))
        assert run(db.delete_watch_item(item["id"])) is True
        assert run(db.get_watch_items()) == []

    def test_delete_nonexistent(self):
        assert run(db.delete_watch_item(9999)) is False

    def test_get_single(self):
        item = run(db.add_watch_item("Chair", 500.0, "NYC", 15))
        fetched = run(db.get_watch_item(item["id"]))
        assert fetched is not None
        assert fetched["name"] == "Chair"

    def test_get_single_nonexistent(self):
        assert run(db.get_watch_item(9999)) is None


class TestListings:
    def test_upsert_new(self):
        result = run(
            db.upsert_listing(
                fb_id="123456",
                title="PS5 Console",
                price=250.0,
                link="https://facebook.com/marketplace/item/123456/",
                item_name="PS5",
                fair_price=400.0,
                discount_pct=37.5,
                deal_quality="good",
            )
        )
        assert result is not None
        assert result["fb_id"] == "123456"
        assert result["deal_quality"] == "good"

    def test_upsert_duplicate_returns_none(self):
        run(
            db.upsert_listing(
                fb_id="123456", title="PS5", price=250.0,
                link="https://link", item_name="PS5",
            )
        )
        result = run(
            db.upsert_listing(
                fb_id="123456", title="PS5 Updated", price=200.0,
                link="https://link", item_name="PS5",
            )
        )
        assert result is None

    def test_filter_by_item_name(self):
        run(db.upsert_listing(fb_id="1", title="PS5 A", price=200, link="l", item_name="PS5"))
        run(db.upsert_listing(fb_id="2", title="Chair B", price=500, link="l", item_name="Chair"))
        ps5_listings = run(db.get_listings(item_name="PS5"))
        assert len(ps5_listings) == 1
        assert ps5_listings[0]["item_name"] == "PS5"

    def test_filter_by_deal_quality(self):
        run(db.upsert_listing(fb_id="1", title="A", price=100, link="l", item_name="X", deal_quality="great"))
        run(db.upsert_listing(fb_id="2", title="B", price=200, link="l", item_name="X", deal_quality="none"))
        great = run(db.get_listings(deal_quality="great"))
        assert len(great) == 1


class TestPriceCache:
    def test_save_and_retrieve(self):
        run(db.save_price_cache("PS5", 350.0, 15, "ebay", 200.0, 500.0, "[200,350,500]"))
        cached = run(db.get_cached_price("PS5"))
        assert cached is not None
        assert cached["median_price"] == 350.0
        assert cached["source"] == "ebay"
        assert cached["sample_count"] == 15

    def test_cache_miss(self):
        assert run(db.get_cached_price("nonexistent")) is None


class TestScans:
    def test_create_and_update(self):
        scan = run(db.create_scan())
        assert scan["status"] == "running"

        updated = run(db.update_scan(scan["id"], status="completed", items_scanned=5, deals_found=2, new_listings=10))
        assert updated["status"] == "completed"
        assert updated["items_scanned"] == 5
        assert updated["deals_found"] == 2
        assert updated["completed_at"] is not None

    def test_list_scans(self):
        run(db.create_scan())
        run(db.create_scan())
        scans = run(db.get_scans(limit=10))
        assert len(scans) == 2
