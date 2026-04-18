from backend.pricer import evaluate_deal


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
