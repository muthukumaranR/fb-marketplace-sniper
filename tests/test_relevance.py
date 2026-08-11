import json

import pytest

from backend.relevance import (
    DEFAULT_EXCLUSIONS,
    excluded_by,
    Facet,
    FacetSpec,
    _fallback_spec,
    _spec_from_payload,
    combine_scores,
    matches,
    price_score,
    score_listing,
)


def ps5_spec() -> FacetSpec:
    """What the LLM should return for the watch term 'PS5'."""
    return FacetSpec(
        query="PS5",
        facets=[Facet(name="model", values=["PS5"], weight=3, required=True)],
        exclude=["controller", "game", "headset", "cover", "stand", "cable", "skin", "dock"],
    )


class TestMatches:
    def test_exact_substring(self):
        assert matches("PS5", "Sony PS5 Console Disc Edition")

    def test_case_insensitive(self):
        assert matches("ps5", "Sony PS5 Console")

    def test_punctuation_ignored(self):
        assert matches("iPhone 13", "Apple iPhone 13 (unlocked)")

    def test_compacted_units(self):
        assert matches("1TB", "PS5 1 TB Console")
        assert matches("128GB", "iPhone 13 128 GB Blue")

    def test_token_set_ignores_word_order(self):
        assert matches("iPhone 13", "Apple 13 iPhone unlocked")

    def test_absent_value(self):
        assert not matches("512GB", "iPhone 13 128GB")

    def test_empty_value_never_matches(self):
        assert not matches("", "anything")


class TestAccessoryExclusion:
    """The C3 scenario: watching 'PS5' must not price accessories as consoles."""

    @pytest.mark.parametrize("title", [
        "PS5 Controller DualSense",
        "PS5 game - Spiderman",
        "PS5 Headset Pulse 3D",
        "Cover plates for PS5",
        "PS5 charging dock",
    ])
    def test_accessories_score_zero(self, title):
        result = score_listing(title, ps5_spec())
        assert result.score == 0.0
        assert result.excluded_by is not None

    @pytest.mark.parametrize("title", [
        "Sony PS5 Console Disc Edition",
        "PlayStation PS5 Digital Edition console",
    ])
    def test_real_consoles_score_full(self, title):
        assert score_listing(title, ps5_spec()).score == 1.0

    def test_accessory_would_have_passed_without_the_gate(self):
        """Without exclusions, 'PS5 Controller' matches the model facet."""
        no_exclusions = FacetSpec(query="PS5", facets=ps5_spec().facets)
        assert score_listing("PS5 Controller DualSense", no_exclusions).score == 1.0
        assert score_listing("PS5 Controller DualSense", ps5_spec()).score == 0.0


class TestConditionExclusion:
    @pytest.mark.parametrize("title", [
        "iPhone 13 for parts",
        "iPhone 13 cracked screen",
        "iPhone 13 - as is",
        "iPhone 13 box only",
        "iPhone 13 iCloud locked",
        "iPhone 13 not working",
    ])
    def test_broken_and_partial_listings_score_zero(self, title):
        spec = FacetSpec(query="iPhone 13", facets=[Facet("model", "iPhone 13", 3, True)])
        result = score_listing(title, spec)
        assert result.score == 0.0
        assert result.excluded_by in DEFAULT_EXCLUSIONS

    def test_default_exclusions_apply_without_llm_exclusions(self):
        assert score_listing("Xbox for parts", FacetSpec(query="Xbox")).score == 0.0


class TestScoreListing:
    def test_required_facet_missing_disqualifies(self):
        spec = FacetSpec(query="iPhone 13", facets=[
            Facet("model", "iPhone 13", 3, required=True),
            Facet("storage", "128GB", 1),
        ])
        result = score_listing("Samsung Galaxy S22 128GB", spec)
        assert result.score == 0.0
        assert "model=iPhone 13" in result.missed

    def test_partial_match_is_weight_proportional(self):
        spec = FacetSpec(query="iPhone 13 128GB", facets=[
            Facet("model", "iPhone 13", 3, required=True),
            Facet("storage", "128GB", 1),
        ])
        result = score_listing("iPhone 13 512GB unlocked", spec)
        assert result.score == 0.75  # 3 of 4 weight
        assert result.matched == ["model=iPhone 13"]
        assert result.missed == ["storage=128GB"]

    def test_wrong_variant_is_penalized_not_ignored(self):
        """A 64GB unit priced against a 512GB fair price must score below 1.0."""
        spec = FacetSpec(query="iPhone 13 512GB", facets=[
            Facet("model", "iPhone 13", 3, required=True),
            Facet("storage", "512GB", 2),
        ])
        assert score_listing("iPhone 13 64GB", spec).score < 1.0

    def test_empty_spec_is_neutral(self):
        assert score_listing("literally anything", FacetSpec(query="x")).score == 1.0

    def test_zero_weights_do_not_divide_by_zero(self):
        spec = FacetSpec(query="x", facets=[Facet("a", "nope", weight=0)])
        assert score_listing("something else", spec).score == 1.0

    def test_negative_weight_clamped(self):
        spec = FacetSpec(query="x", facets=[Facet("a", "nope", weight=-5)])
        assert score_listing("something else", spec).score == 1.0

    def test_match_details_serializes(self):
        result = score_listing("PS5 Controller", ps5_spec())
        assert json.loads(result.as_json())["excluded_by"] == "controller"


class TestPriceScore:
    def test_half_price_scores_half(self):
        assert price_score(200, 400) == 0.5

    def test_at_fair_price_scores_zero(self):
        assert price_score(400, 400) == 0.0

    def test_above_fair_price_clamps_to_zero(self):
        assert price_score(800, 400) == 0.0

    def test_free_listing_scores_one(self):
        assert price_score(0, 400) == 1.0

    @pytest.mark.parametrize("fair", [None, 0, -100])
    def test_unusable_fair_price_scores_zero(self, fair):
        assert price_score(200, fair) == 0.0

    def test_negative_listing_price_scores_zero(self):
        assert price_score(-50, 400) == 0.0


class TestCombineScores:
    def test_great_price_on_wrong_item_zeroes_out(self):
        assert combine_scores(0.0, 1.0) == 0.0

    def test_right_item_at_bad_price_zeroes_out(self):
        assert combine_scores(1.0, 0.0) == 0.0

    def test_multiplies(self):
        assert combine_scores(0.5, 0.5) == 0.25


class TestFallbackSpec:
    def test_every_token_becomes_required(self):
        spec = _fallback_spec("iPhone 13 128GB")
        assert all(f.required for f in spec.facets)
        assert score_listing("iPhone 13 128GB unlocked", spec).score == 1.0

    def test_fallback_still_rejects_wrong_item(self):
        assert score_listing("Samsung Galaxy", _fallback_spec("iPhone 13")).score == 0.0

    def test_fallback_still_applies_default_exclusions(self):
        assert score_listing("iPhone 13 for parts", _fallback_spec("iPhone 13")).score == 0.0


class TestSpecFromPayload:
    def test_parses_full_payload(self):
        spec = _spec_from_payload("PS5", {
            "facets": [{"name": "model", "value": "PS5", "weight": 3, "required": True}],
            "exclude": ["controller"],
        })
        assert spec.facets[0].required is True
        assert spec.facets[0].weight == 3.0
        assert spec.exclude == ["controller"]

    def test_skips_facets_with_empty_values(self):
        spec = _spec_from_payload("x", {"facets": [{"name": "a", "value": "  "}]})
        assert spec.facets == []

    def test_defaults_for_missing_fields(self):
        spec = _spec_from_payload("x", {"facets": [{"value": "thing"}]})
        assert spec.facets[0].name == "attr"
        assert spec.facets[0].weight == 1.0
        assert spec.facets[0].required is False

    def test_handles_missing_keys(self):
        spec = _spec_from_payload("x", {})
        assert spec.facets == [] and spec.exclude == []


class TestExclusionWordBoundaries:
    """Regression: substring exclusions fired 'locked' on 'unlocked'."""

    def test_unlocked_is_not_locked(self):
        assert excluded_by("iPhone 13 128GB unlocked", DEFAULT_EXCLUSIONS) is None

    def test_locked_still_caught(self):
        assert excluded_by("iPhone 13 iCloud locked", DEFAULT_EXCLUSIONS) == "locked"

    def test_unlocked_phone_scores_full(self):
        spec = FacetSpec(query="iPhone 13", facets=[Facet("model", "iPhone 13", 3, True)])
        assert score_listing("iPhone 13 128GB unlocked", spec).score == 1.0

    @pytest.mark.parametrize("title", [
        "Carparts delivery van",     # 'parts only' must not fire on 'carparts'
        "Brokerage desk chair",      # 'broken' must not fire inside 'brokerage'
        "Crackerjack toy set",       # 'cracked' must not fire inside 'crackerjack'
    ])
    def test_no_false_exclusions_from_word_fragments(self, title):
        assert excluded_by(title, DEFAULT_EXCLUSIONS) is None

    def test_multiword_exclusion_matches(self):
        assert excluded_by("selling for parts only", DEFAULT_EXCLUSIONS) in ("for parts", "parts only")

    def test_hyphenated_model_number_matches(self):
        assert matches("PS5", "Sony PS-5 Console")


class TestAlternativeSpellings:
    """
    Sellers write the same product many ways. Extraction returns every spelling
    in one facet's `values`; matching any one must satisfy it.
    """

    def spec(self) -> FacetSpec:
        return FacetSpec(query="PS5", facets=[
            Facet("model", ["PlayStation 5", "PS5", "PS 5"], weight=3, required=True),
        ])

    @pytest.mark.parametrize("title", [
        "Sony PS5 Console Disc Edition",
        "PlayStation 5 Slim 1TB console",
        "Sony PS 5 console boxed",
    ])
    def test_any_spelling_satisfies_the_facet(self, title):
        assert score_listing(title, self.spec()).score == 1.0

    def test_wrong_product_still_rejected(self):
        assert score_listing("Xbox Series X console", self.spec()).score == 0.0

    def test_bare_string_is_wrapped(self):
        assert Facet("model", "PS5").values == ["PS5"]

    def test_blank_alternatives_dropped(self):
        assert Facet("model", ["PS5", "  ", ""]).values == ["PS5"]

    def test_label_joins_alternatives(self):
        assert Facet("model", ["PS5", "PlayStation 5"]).label == "PS5|PlayStation 5"

    def test_payload_accepts_values_list(self):
        spec = _spec_from_payload("PS5", {"facets": [
            {"name": "model", "values": ["PlayStation 5", "PS5"], "weight": 3, "required": True}
        ]})
        assert spec.facets[0].values == ["PlayStation 5", "PS5"]
        assert score_listing("Sony PS5 console", spec).score == 1.0

    def test_payload_still_accepts_legacy_single_value(self):
        spec = _spec_from_payload("PS5", {"facets": [{"name": "model", "value": "PS5"}]})
        assert spec.facets[0].values == ["PS5"]

    def test_same_named_facets_are_alternatives_not_conjunctions(self):
        """Extraction sometimes splits spellings across duplicate names anyway."""
        spec = FacetSpec(query="PS5", facets=[
            Facet("model", ["PlayStation 5"], weight=3, required=True),
            Facet("model", ["PS5"], weight=3, required=True),
        ])
        assert score_listing("Sony PS5 Console", spec).score == 1.0
        assert score_listing("PlayStation 5 console", spec).score == 1.0


class TestSortClauses:
    """`sort` is whitelisted — it must never reach the query as raw SQL."""

    def test_unknown_sort_falls_back_to_recent(self):
        from backend.db import SORT_CLAUSES
        assert SORT_CLAUSES.get("'; DROP TABLE listings--", SORT_CLAUSES["recent"]) == SORT_CLAUSES["recent"]

    def test_documented_sorts_all_exist(self):
        from backend.db import SORT_CLAUSES
        assert set(SORT_CLAUSES) == {"final", "relevance", "deal", "price", "recent"}


class TestDescriptionScoring:
    """Reading the full body must add signal without creating false negatives."""

    def spec(self) -> FacetSpec:
        return FacetSpec(
            query="PS5",
            facets=[Facet("model", ["PlayStation 5", "PS5"], weight=3, required=True)],
            exclude=["controller", "game", "stand", "dock"],
        )

    def test_condition_term_only_in_description_is_caught(self):
        """The whole point: 'for parts' is usually not in the title."""
        result = score_listing("Sony PS5 Console", self.spec(),
                               description="Selling for parts, HDMI port is dead.")
        assert result.score == 0.0
        assert result.excluded_by == "for parts"

    def test_cracked_in_description_is_caught(self):
        result = score_listing("iPhone 13 128GB", FacetSpec(query="iPhone 13"),
                               description="Screen is cracked but works fine.")
        assert result.score == 0.0

    def test_accessory_words_in_description_do_not_reject_a_real_console(self):
        """A genuine console body mentions controllers; that must not disqualify it."""
        for body in [
            "Comes with 2 controllers and 3 games.",
            "No controller included, console only.",
            "Includes vertical stand and charging dock.",
        ]:
            result = score_listing("Sony PS5 Console Disc Edition", self.spec(), description=body)
            assert result.score == 1.0, f"rejected by body: {body!r}"

    def test_accessory_title_still_rejected_regardless_of_body(self):
        result = score_listing("PS5 Controller", self.spec(), description="Great condition, works.")
        assert result.excluded_by == "controller"

    def test_description_can_satisfy_a_facet(self):
        spec = FacetSpec(query="iPhone 13 128GB", facets=[
            Facet("model", ["iPhone 13"], weight=3, required=True),
            Facet("storage", ["128GB"], weight=1),
        ])
        titled_only = score_listing("iPhone 13 unlocked", spec)
        with_body = score_listing("iPhone 13 unlocked", spec, description="128GB, blue, boxed.")
        assert titled_only.score == 0.75
        assert with_body.score == 1.0

    def test_none_description_matches_title_only_behaviour(self):
        assert score_listing("Sony PS5 Console", self.spec(), None).score == \
               score_listing("Sony PS5 Console", self.spec()).score

    def test_empty_description_is_harmless(self):
        assert score_listing("Sony PS5 Console", self.spec(), "").score == 1.0
