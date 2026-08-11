"""
Which listings get their full body read.

Fetching a detail page costs a page load and bot-detection risk, so the scan
must fetch only listings whose outcome the body can change.
"""

import pytest

from backend import tasks
from backend.relevance import Facet, FacetSpec
from backend.scraper_fb import FBListing


@pytest.fixture
def spec():
    return FacetSpec(
        query="PS5",
        facets=[Facet("model", ["PlayStation 5", "PS5"], weight=3, required=True)],
        exclude=["controller", "game", "stand"],
    )


@pytest.fixture
def listings():
    return [
        FBListing("1", "Sony PS5 Console", 200.0, "u"),        # deal + relevant -> fetch
        FBListing("2", "PS5 Controller", 20.0, "u"),           # excluded by title
        FBListing("3", "Sony PS5 Console", 395.0, "u"),        # relevant but not a deal
        FBListing("4", "Xbox Series X", 150.0, "u"),           # deal but wrong product
        FBListing("5", "PlayStation 5 console", 210.0, "u"),   # deal + relevant -> fetch
    ]


@pytest.fixture
def captured(monkeypatch):
    """Record which fb_ids the scraper is asked for, without touching the network."""
    calls = {}

    async def fake_fetch(fb_ids, limit=20):
        calls["requested"] = list(fb_ids)
        return {i: "body text" for i in fb_ids}

    async def fake_existing(fb_ids):
        return set()

    monkeypatch.setattr(tasks, "fetch_listing_descriptions", fake_fetch)
    monkeypatch.setattr(tasks.db, "existing_fb_ids", fake_existing)
    return calls


@pytest.mark.asyncio
async def test_only_deal_worthy_relevant_listings_are_fetched(spec, listings, captured):
    result = await tasks._fetch_candidate_descriptions(listings, spec, 400.0, {"name": "PS5"})
    assert sorted(captured["requested"]) == ["1", "5"]
    assert set(result) == {"1", "5"}


@pytest.mark.asyncio
async def test_already_stored_listings_are_not_refetched(spec, listings, monkeypatch):
    calls = {}

    async def fake_fetch(fb_ids, limit=20):
        calls["requested"] = list(fb_ids)
        return {}

    async def fake_existing(fb_ids):
        return {"1"}  # listing 1 already seen on a previous scan

    monkeypatch.setattr(tasks, "fetch_listing_descriptions", fake_fetch)
    monkeypatch.setattr(tasks.db, "existing_fb_ids", fake_existing)

    await tasks._fetch_candidate_descriptions(listings, spec, 400.0, {"name": "PS5"})
    assert calls["requested"] == ["5"]


@pytest.mark.asyncio
async def test_no_candidates_means_no_browser_launch(spec, monkeypatch):
    launched = False

    async def fake_fetch(fb_ids, limit=20):
        nonlocal launched
        launched = True
        return {}

    monkeypatch.setattr(tasks, "fetch_listing_descriptions", fake_fetch)
    only_accessories = [FBListing("9", "PS5 Controller", 10.0, "u")]
    result = await tasks._fetch_candidate_descriptions(only_accessories, spec, 400.0, {"name": "PS5"})
    assert result == {}
    assert launched is False


@pytest.mark.asyncio
async def test_max_price_excludes_from_fetch(spec, captured):
    listings = [FBListing("1", "Sony PS5 Console", 200.0, "u")]
    await tasks._fetch_candidate_descriptions(listings, spec, 400.0, {"name": "PS5", "max_price": 100})
    assert captured.get("requested") is None


@pytest.mark.asyncio
async def test_scraper_failure_degrades_to_titles(spec, listings, monkeypatch):
    """A failed description fetch must not abort the scan."""
    async def boom(fb_ids, limit=20):
        raise RuntimeError("Facebook session expired")

    async def fake_existing(fb_ids):
        return set()

    monkeypatch.setattr(tasks, "fetch_listing_descriptions", boom)
    monkeypatch.setattr(tasks.db, "existing_fb_ids", fake_existing)

    result = await tasks._fetch_candidate_descriptions(listings, spec, 400.0, {"name": "PS5"})
    assert result == {}


class TestPickDescription:
    """
    Text blocks captured live from a real FB listing page (id 1036749165988655).
    'Longest block wins' picked the sidebar's patio table over the real body.
    """

    REAL_PAGE_TEXTS = [
        "Electronics\n › \nVideo Game Consoles",
        "$425",
        "Listed 3 weeks ago in Huntsville, AL",
        "PS5 with 2 PS5 controllers and a media remote",
        "Seller details",
        "Huntsville, AL · Location is approximate",
        "Related listings",
        "playstation 5 pro digital console",
        "Purple Extendable Tripod for Phone",
        "Patio Bar Height Table with Chairs - local pick up/cash only",
        "🧳 Brand New 3-Piece Luggage Set – Navy Blue & Tan – $80",
    ]

    def test_picks_the_real_description_not_the_longer_sidebar_item(self):
        from backend.scraper_fb import pick_description
        assert pick_description(self.REAL_PAGE_TEXTS) == "PS5 with 2 PS5 controllers and a media remote"

    def test_returns_none_without_anchors(self):
        from backend.scraper_fb import pick_description
        assert pick_description(["some", "unrelated", "text"]) is None

    def test_returns_none_when_anchors_are_inverted(self):
        from backend.scraper_fb import pick_description
        assert pick_description(["Location is approximate", "Listed 2 days ago"]) is None

    def test_returns_none_when_block_is_empty(self):
        from backend.scraper_fb import pick_description
        assert pick_description(["Listed 2 days ago", "Location is approximate"]) is None

    def test_truncates_very_long_descriptions(self):
        from backend.scraper_fb import pick_description
        texts = ["Listed 1 day ago", "x" * 9000, "Location is approximate"]
        assert len(pick_description(texts)) == 4000
