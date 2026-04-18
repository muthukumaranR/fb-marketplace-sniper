"""Tests for backend/relevance.py — facet extraction (mocked LLM) and scoring."""

import asyncio
import json
import os
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import pytest

# Override DB_PATH before importing db (mirrors test_db.py / test_api.py pattern)
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DB_PATH"] = _tmp.name

from backend import db
from backend import relevance
from backend.relevance import (
    Facet,
    FacetSpec,
    MatchResult,
    _facet_matches,
    _tokens,
    combine_scores,
    extract_query_facets,
    price_score,
    score_listing,
)

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
            await conn.execute("DELETE FROM query_facets_cache")
            await conn.commit()
        finally:
            await conn.close()

    run(cleanup())


# ---------- tokenization + single-facet match ----------


class TestTokenize:
    def test_basic(self):
        assert _tokens("iPhone 15 Pro 256GB") == ["iphone", "15", "pro", "256gb"]

    def test_punct(self):
        assert _tokens("Apple, iPhone-15 (Pro)") == ["apple", "iphone", "15", "pro"]

    def test_empty(self):
        assert _tokens("") == []


class TestFacetMatches:
    def _ctx(self, title: str):
        return title.lower(), set(_tokens(title))

    def test_exact_substring(self):
        low, toks = self._ctx("Apple iPhone 15 Pro 256GB")
        assert _facet_matches("iPhone 15 Pro", low, toks) is True

    def test_storage_glued(self):
        low, toks = self._ctx("iPhone 15 256GB mint")
        assert _facet_matches("256GB", low, toks) is True

    def test_storage_spaced_value_glued_title(self):
        low, toks = self._ctx("iPhone 15 256GB mint")
        assert _facet_matches("256 GB", low, toks) is True

    def test_storage_glued_value_spaced_title(self):
        low, toks = self._ctx("iPhone 15 256 GB mint")
        assert _facet_matches("256gb", low, toks) is True

    def test_token_reorder(self):
        low, toks = self._ctx("Pro iPhone 15 (Max)")
        assert _facet_matches("iPhone 15 Pro", low, toks) is True

    def test_miss(self):
        low, toks = self._ctx("iPhone 14 128GB")
        assert _facet_matches("256GB", low, toks) is False

    def test_empty_value(self):
        low, toks = self._ctx("anything")
        assert _facet_matches("", low, toks) is False


# ---------- score_listing ----------


def _spec(*facets: tuple[str, str, float, bool]) -> FacetSpec:
    return FacetSpec(
        query="test",
        facets=[Facet(key=k, value=v, weight=w, required=r) for k, v, w, r in facets],
    )


class TestScoreListing:
    def test_full_match_no_required(self):
        spec = _spec(
            ("model", "iPhone 15 Pro", 0.5, False),
            ("storage", "256GB", 0.3, False),
            ("color", "black", 0.2, False),
        )
        r = score_listing(spec, "Apple iPhone 15 Pro 256GB black mint condition")
        assert r.score == 1.0
        assert set(r.matched) == {"model", "storage", "color"}
        assert r.missed == []
        assert r.rejected is False

    def test_partial_match(self):
        spec = _spec(
            ("model", "iPhone 15 Pro", 0.5, False),
            ("storage", "256GB", 0.3, False),
            ("color", "black", 0.2, False),
        )
        r = score_listing(spec, "iPhone 15 Pro 128GB white")
        # Only model matches: 0.5 / 1.0
        assert r.score == 0.5
        assert r.matched == ["model"]
        assert set(r.missed) == {"storage", "color"}
        assert r.rejected is False

    def test_required_miss_rejects(self):
        spec = _spec(
            ("model", "iPhone 15 Pro", 0.6, True),  # required
            ("storage", "256GB", 0.4, False),
        )
        r = score_listing(spec, "iPhone 14 256GB")  # wrong model
        assert r.rejected is True
        assert r.score == 0.0
        assert "model" in r.missed
        assert r.reject_reason and "model" in r.reject_reason

    def test_price_cap_rejects(self):
        spec = _spec(("model", "PS5", 1.0, False))
        r = score_listing(spec, "PS5 Console", price=500.0, max_price=300.0)
        assert r.rejected is True
        assert r.score == 0.0
        assert r.reject_reason and "over cap" in r.reject_reason

    def test_price_cap_ok(self):
        spec = _spec(("model", "PS5", 1.0, False))
        r = score_listing(spec, "PS5 Console", price=250.0, max_price=300.0)
        assert r.rejected is False
        assert r.score == 1.0

    def test_empty_spec(self):
        r = score_listing(FacetSpec(query="q", facets=[]), "anything")
        assert r.score == 0.0
        assert r.matched == []


# ---------- price_score + combine_scores ----------


class TestPriceScore:
    def test_great_discount_saturates(self):
        # 50% of fair → at or below great threshold → 1.0
        assert price_score(50.0, 100.0) == 1.0

    def test_at_fair_price_zero(self):
        assert price_score(100.0, 100.0) == 0.0

    def test_above_fair_zero(self):
        assert price_score(150.0, 100.0) == 0.0

    def test_linear_midway(self):
        # 80% of fair → (1 - 0.8) / (1 - 0.6) = 0.5
        assert price_score(80.0, 100.0) == 0.5

    def test_missing_fair_neutral(self):
        assert price_score(100.0, None) == 0.5
        assert price_score(100.0, 0.0) == 0.5


class TestCombineScores:
    def test_both_present(self):
        assert combine_scores(0.8, 0.5) == 0.4

    def test_missing_relevance_passthrough(self):
        assert combine_scores(None, 0.7) == 0.7

    def test_zero_relevance_zeros_final(self):
        assert combine_scores(0.0, 1.0) == 0.0


# ---------- extract_query_facets (mock LLM) ----------


def _mock_acompletion_factory(payload: dict):
    async def _mock(*args, **kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
        )
    return _mock


class TestExtractQueryFacets:
    def test_extracts_and_caches(self):
        payload = {
            "facets": [
                {"key": "model", "value": "iPhone 15 Pro", "weight": 0.5, "required": True},
                {"key": "storage", "value": "256GB", "weight": 0.3, "required": False},
                {"key": "color", "value": "black", "weight": 0.2, "required": False},
            ]
        }
        with patch("backend.relevance.acompletion", _mock_acompletion_factory(payload)):
            spec = run(extract_query_facets("iPhone 15 Pro 256GB black"))

        assert spec.query == "iPhone 15 Pro 256GB black"
        assert len(spec.facets) == 3
        assert spec.facets[0].key == "model"
        assert spec.facets[0].required is True

        # Cache: second call should NOT invoke LLM
        def _blow_up(*a, **kw):
            raise AssertionError("should be cached")
        with patch("backend.relevance.acompletion", _blow_up):
            spec2 = run(extract_query_facets("iPhone 15 Pro 256GB black"))
        assert len(spec2.facets) == 3

    def test_fenced_json_tolerated(self):
        payload_text = '```json\n{"facets": [{"key": "model", "value": "PS5", "weight": 1.0, "required": true}]}\n```'

        async def _mock(*args, **kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=payload_text))]
            )

        with patch("backend.relevance.acompletion", _mock):
            spec = run(extract_query_facets("PS5"))
        assert len(spec.facets) == 1
        assert spec.facets[0].key == "model"

    def test_prose_wrapped_json_tolerated(self):
        payload_text = 'Sure! Here is the JSON:\n{"facets": [{"key": "model", "value": "Xbox", "weight": 1.0, "required": true}]}\nHope this helps.'

        async def _mock(*args, **kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=payload_text))]
            )

        with patch("backend.relevance.acompletion", _mock):
            spec = run(extract_query_facets("Xbox"))
        assert len(spec.facets) == 1
        assert spec.facets[0].value == "Xbox"

    def test_empty_value_filtered(self):
        payload = {
            "facets": [
                {"key": "model", "value": "Dyson V11", "weight": 0.7, "required": True},
                {"key": "color", "value": "", "weight": 0.3, "required": False},  # dropped
            ]
        }
        with patch("backend.relevance.acompletion", _mock_acompletion_factory(payload)):
            spec = run(extract_query_facets("Dyson V11 vacuum"))
        assert len(spec.facets) == 1
        assert spec.facets[0].key == "model"


# ---------- FacetSpec serialization ----------


class TestFacetSpecSerde:
    def test_roundtrip(self):
        spec = FacetSpec(
            query="test",
            facets=[Facet("model", "PS5", 0.8, True), Facet("color", "white", 0.2, False)],
        )
        text = spec.to_json()
        spec2 = FacetSpec.from_json(text)
        assert spec2.query == "test"
        assert spec2.facets[0].key == "model"
        assert spec2.facets[0].required is True
        assert spec2.facets[1].weight == 0.2


class TestMatchResultSerde:
    def test_to_dict(self):
        mr = MatchResult(score=0.75, matched=["a"], missed=["b"], rejected=False)
        d = mr.to_dict()
        assert d["score"] == 0.75
        assert d["matched"] == ["a"]
        assert d["missed"] == ["b"]
        assert d["rejected"] is False
