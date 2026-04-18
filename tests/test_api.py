import asyncio
import os
import tempfile

import pytest
from httpx import ASGITransport, AsyncClient

# Override DB before importing app
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DB_PATH"] = _tmp.name

from backend import db

db.DB_PATH = _tmp.name

from backend.main import app

transport = ASGITransport(app=app)


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


class TestHealth:
    def test_health(self):
        async def _test():
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/health")
                assert resp.status_code == 200
                assert resp.json() == {"status": "ok"}
        run(_test())


class TestWatchlistAPI:
    def test_add_and_list(self):
        async def _test():
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/api/watchlist", json={"name": "PS5", "max_price": 300})
                assert resp.status_code == 200
                data = resp.json()
                assert data["name"] == "PS5"
                assert data["max_price"] == 300.0

                resp = await client.get("/api/watchlist")
                assert resp.status_code == 200
                items = resp.json()
                assert len(items) == 1
        run(_test())

    def test_delete(self):
        async def _test():
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/api/watchlist", json={"name": "Chair"})
                item_id = resp.json()["id"]

                resp = await client.delete(f"/api/watchlist/{item_id}")
                assert resp.status_code == 200

                resp = await client.get("/api/watchlist")
                assert resp.json() == []
        run(_test())

    def test_delete_404(self):
        async def _test():
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.delete("/api/watchlist/9999")
                assert resp.status_code == 404
        run(_test())

    def test_default_location(self):
        async def _test():
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/api/watchlist", json={"name": "Test"})
                data = resp.json()
                assert data["location"] == "Huntsville, AL"
                assert data["radius"] == 20
        run(_test())


class TestDashboard:
    def test_empty_dashboard(self):
        async def _test():
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/dashboard")
                assert resp.status_code == 200
                data = resp.json()
                assert data["active_watches"] == 0
                assert data["total_listings"] == 0
                assert data["total_deals"] == 0
        run(_test())


class TestListingsAPI:
    def test_empty_listings(self):
        async def _test():
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/listings")
                assert resp.status_code == 200
                assert resp.json() == []
        run(_test())

    def test_sort_by_final_score(self):
        async def _test():
            # Seed three listings with ascending final_score
            await db.upsert_listing(
                fb_id="a", title="A", price=100, link="l", item_name="X",
                relevance_score=0.2, final_score=0.1, match_details='{"score":0.2,"matched":[],"missed":["model"],"rejected":false}',
            )
            await db.upsert_listing(
                fb_id="b", title="B", price=100, link="l", item_name="X",
                relevance_score=0.9, final_score=0.9, match_details='{"score":0.9,"matched":["model"],"missed":[],"rejected":false}',
            )
            await db.upsert_listing(
                fb_id="c", title="C", price=100, link="l", item_name="X",
                relevance_score=0.5, final_score=0.4, match_details='{"score":0.5,"matched":["model"],"missed":["storage"],"rejected":false}',
            )
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/listings?sort=final")
                assert resp.status_code == 200
                ids = [l["fb_id"] for l in resp.json()]
                assert ids == ["b", "c", "a"]
        run(_test())

    def test_sort_by_relevance(self):
        async def _test():
            await db.upsert_listing(
                fb_id="a", title="A", price=100, link="l", item_name="X", relevance_score=0.1, final_score=0.0,
            )
            await db.upsert_listing(
                fb_id="b", title="B", price=100, link="l", item_name="X", relevance_score=0.9, final_score=0.0,
            )
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/listings?sort=relevance")
                ids = [l["fb_id"] for l in resp.json()]
                assert ids == ["b", "a"]
        run(_test())

    def test_match_details_parsed(self):
        async def _test():
            await db.upsert_listing(
                fb_id="a", title="iPhone 15 Pro 256GB", price=600, link="l", item_name="iPhone",
                relevance_score=0.8, final_score=0.5,
                match_details='{"score":0.8,"matched":["model","storage"],"missed":[],"rejected":false,"reject_reason":null}',
            )
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/listings")
                data = resp.json()
                assert len(data) == 1
                md = data[0]["match_details"]
                assert md["score"] == 0.8
                assert md["matched"] == ["model", "storage"]
                assert md["rejected"] is False
        run(_test())


class TestScansAPI:
    def test_empty_scans(self):
        async def _test():
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/scans")
                assert resp.status_code == 200
                assert resp.json() == []
        run(_test())

    def test_scan_not_found(self):
        async def _test():
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/scans/9999")
                assert resp.status_code == 404
        run(_test())
