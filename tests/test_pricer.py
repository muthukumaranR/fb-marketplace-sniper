import pytest

from backend.pricer import _extract_price_json, evaluate_deal


class TestEvaluateDeal:
    def test_great_deal(self):
        # 50% of fair price → great deal
        quality, discount = evaluate_deal(50.0, 100.0)
        assert quality == "great"
        assert discount == 50.0

    def test_good_deal(self):
        # 70% of fair price → good deal
        quality, discount = evaluate_deal(70.0, 100.0)
        assert quality == "good"
        assert discount == 30.0

    def test_fair_deal(self):
        # 90% of fair price → fair
        quality, discount = evaluate_deal(90.0, 100.0)
        assert quality == "fair"
        assert discount == 10.0

    def test_no_deal(self):
        # 110% of fair price → none
        quality, discount = evaluate_deal(110.0, 100.0)
        assert quality == "none"
        assert discount == -10.0

    def test_zero_fair_price(self):
        quality, discount = evaluate_deal(50.0, 0.0)
        assert quality == "none"
        assert discount == 0.0

    def test_free_listing(self):
        quality, discount = evaluate_deal(0.0, 100.0)
        assert quality == "great"
        assert discount == 100.0

    def test_exact_threshold_great(self):
        # Exactly at 60% threshold
        quality, _ = evaluate_deal(60.0, 100.0)
        assert quality == "great"

    def test_exact_threshold_good(self):
        # Exactly at 75% threshold
        quality, _ = evaluate_deal(75.0, 100.0)
        assert quality == "good"


class TestExtractPriceJson:
    def test_bare_json(self):
        assert _extract_price_json('{"low": 200, "median": 275, "high": 350}') == {
            "low": 200, "median": 275, "high": 350
        }

    def test_fenced_json(self):
        text = 'Here you go:\n```json\n{"low": 200, "median": 275, "high": 350}\n```'
        assert _extract_price_json(text)["median"] == 275

    def test_fenced_without_language_tag(self):
        assert _extract_price_json('```\n{"median": 99}\n```')["median"] == 99

    def test_reasoning_prefix_stripped(self):
        """Blablador reasoning aliases emit chain-of-thought before the answer."""
        text = (
            'The user wants a used iPhone price. Let me think about this.<|close|>'
            '{"low": 260, "median": 335, "high": 420}'
        )
        assert _extract_price_json(text) == {"low": 260, "median": 335, "high": 420}

    def test_skips_leading_non_price_object(self):
        text = '{"thought": "considering {nested} braces"} then {"median": 42}'
        assert _extract_price_json(text) == {"median": 42}

    def test_trailing_prose_after_json(self):
        assert _extract_price_json('{"median": 42} — hope that helps!')["median"] == 42

    def test_no_json_raises(self):
        with pytest.raises(ValueError, match="No price JSON"):
            _extract_price_json("I cannot determine a price for that item.")

    def test_json_without_median_raises(self):
        with pytest.raises(ValueError, match="No price JSON"):
            _extract_price_json('{"low": 10, "high": 20}')


class TestExtractPriceJsonRobustness:
    """Regression tests for extractor bugs found by adversarial review."""

    def test_fence_does_not_discard_json_outside_it(self):
        text = 'I could write ```python code``` but the answer is {"median": 42}'
        assert _extract_price_json(text)["median"] == 42

    def test_json_in_second_fence_is_found(self):
        text = 'First ```notes``` then ```json\n{"median": 42}\n```'
        assert _extract_price_json(text)["median"] == 42

    def test_unterminated_fence(self):
        assert _extract_price_json('Here: ```json\n{"median": 42}')["median"] == 42

    def test_braces_inside_string_values(self):
        assert _extract_price_json('{"note": "a {b} c", "median": 42}')["median"] == 42

    def test_null_median_rejected(self):
        with pytest.raises(ValueError, match="No price JSON"):
            _extract_price_json('{"low": 1, "median": null, "high": 3}')

    def test_string_median_rejected(self):
        with pytest.raises(ValueError, match="No price JSON"):
            _extract_price_json('{"median": "about 300"}')

    def test_negative_median_rejected(self):
        """A negative fair price would make every listing look like a deal."""
        with pytest.raises(ValueError, match="No price JSON"):
            _extract_price_json('{"low": -5, "median": -100, "high": 0}')

    def test_bool_median_rejected(self):
        """bool is an int subclass — must not slip through as a price."""
        with pytest.raises(ValueError, match="No price JSON"):
            _extract_price_json('{"median": true}')

    def test_skips_unusable_object_and_takes_the_next(self):
        assert _extract_price_json('{"median": null} then {"median": 42}')["median"] == 42
