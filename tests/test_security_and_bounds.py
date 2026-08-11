"""Regression tests for the price bound, image proxy, and listing insert race."""

import asyncio

import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient

from backend import db as db_module
from backend.main import app, is_allowed_image_url
from backend.models import PriceEstimate, PriceSource
from backend.pricer import MAX_ESTIMATE_DRIFT, _validate_estimate


class TestPriceBound:
    def test_normal_estimate_passes(self):
        assert _validate_estimate("x", {"low": 200, "median": 275, "high": 350}, None) == (200.0, 275.0, 350.0)

    def test_injected_price_rejected_against_previous(self):
        """The prompt-injection payload: a page telling the model to say 99999."""
        with pytest.raises(ValueError, match="Implausible price"):
            _validate_estimate("x", {"median": 99999}, 300.0)

    def test_collapse_rejected(self):
        """A crashed estimate makes everything look like a bad deal, not just a good one."""
        with pytest.raises(ValueError, match="Implausible price"):
            _validate_estimate("x", {"median": 75}, 300.0)

    def test_drift_at_limit_allowed(self):
        assert _validate_estimate("x", {"median": 300 * MAX_ESTIMATE_DRIFT}, 300.0)[1] == 900.0

    def test_drift_just_past_limit_rejected(self):
        with pytest.raises(ValueError, match="Implausible price"):
            _validate_estimate("x", {"median": 300 * MAX_ESTIMATE_DRIFT + 1}, 300.0)

    def test_zero_and_negative_rejected(self):
        for bad in (0, -50):
            with pytest.raises(ValueError, match="Non-positive"):
                _validate_estimate("x", {"median": bad}, None)

    def test_inverted_band_drops_bounds_but_keeps_median(self):
        assert _validate_estimate("x", {"low": 500, "median": 275, "high": 100}, None) == (None, 275.0, None)

    def test_first_estimate_is_unbounded(self):
        """Known gap: with no prior price there is nothing to compare against."""
        assert _validate_estimate("x", {"median": 99999}, None)[1] == 99999.0


class TestPriceEstimateModel:
    def test_rejects_non_positive_median(self):
        for bad in (0, -10):
            with pytest.raises(ValidationError):
                PriceEstimate(item_name="x", median_price=bad, sample_count=0,
                              source=PriceSource.llm, estimated_at="2026-01-01T00:00:00")

    def test_rejects_low_above_median(self):
        with pytest.raises(ValidationError):
            PriceEstimate(item_name="x", median_price=100, low_price=200, sample_count=0,
                          source=PriceSource.ebay, estimated_at="2026-01-01T00:00:00")

    def test_rejects_high_below_median(self):
        with pytest.raises(ValidationError):
            PriceEstimate(item_name="x", median_price=100, high_price=50, sample_count=0,
                          source=PriceSource.ebay, estimated_at="2026-01-01T00:00:00")

    def test_accepts_valid_band(self):
        e = PriceEstimate(item_name="x", median_price=100, low_price=80, high_price=150,
                          sample_count=5, source=PriceSource.ebay, estimated_at="2026-01-01T00:00:00")
        assert e.median_price == 100


class TestImageProxyAllowlist:
    @pytest.mark.parametrize("url", [
        "http://169.254.169.254/latest/meta-data/",   # cloud metadata
        "https://169.254.169.254/x",
        "http://localhost:8000/api/health",
        "https://redis:6379/",
        "file:///etc/passwd",
        "https://evil.com/x.png",
        "https://fbcdn.net.evil.com/x.jpg",           # suffix spoof
        "http://scontent.fbcdn.net/x.jpg",            # plain http
        "https://evil.com/#.fbcdn.net",               # fragment spoof
        "https://user@evil.com/x?.facebook.com",      # userinfo spoof
        "",
    ])
    def test_blocked(self, url):
        assert is_allowed_image_url(url) is False

    @pytest.mark.parametrize("url", [
        "https://scontent-atl3-1.xx.fbcdn.net/v/t45.jpg",
        "https://z-p3.www.facebook.com/img.png",
        "https://scontent.cdninstagram.com/a.jpg",
    ])
    def test_allowed(self, url):
        assert is_allowed_image_url(url) is True

    def test_endpoint_rejects_ssrf_without_fetching(self):
        client = TestClient(app)
        assert client.get("/api/proxy-image", params={"url": "http://169.254.169.254/"}).status_code == 400


class TestConcurrentUpsert:
    """Reviewer reproduced 8 concurrent inserts -> 6 IntegrityErrors aborting the scan."""

    @pytest.mark.asyncio
    async def test_same_id_race_inserts_once_without_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "race.db"))
        await db_module.init_db()

        async def insert(i):
            return await db_module.upsert_listing(
                fb_id="dup", title=f"w{i}", price=10.0, link="u", item_name="x"
            )

        results = await asyncio.gather(*[insert(i) for i in range(8)], return_exceptions=True)
        assert not any(isinstance(r, Exception) for r in results)
        assert sum(r is not None for r in results) == 1
        assert len(await db_module.get_listings(limit=100)) == 1

    @pytest.mark.asyncio
    async def test_distinct_ids_all_insert(self, tmp_path, monkeypatch):
        monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "distinct.db"))
        await db_module.init_db()

        async def insert(i):
            return await db_module.upsert_listing(
                fb_id=f"u{i}", title=f"w{i}", price=10.0, link="u", item_name="x"
            )

        results = await asyncio.gather(*[insert(i) for i in range(8)], return_exceptions=True)
        assert not any(isinstance(r, Exception) for r in results)
        assert len(await db_module.get_listings(limit=100)) == 8

    @pytest.mark.asyncio
    async def test_wal_enabled(self, tmp_path, monkeypatch):
        monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "wal.db"))
        await db_module.init_db()
        conn = await db_module.get_db()
        try:
            rows = await conn.execute_fetchall("PRAGMA journal_mode")
            assert rows[0][0].lower() == "wal"
        finally:
            await conn.close()
