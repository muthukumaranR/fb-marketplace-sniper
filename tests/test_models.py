import pytest
from pydantic import ValidationError

from backend.models import DealQuality, WatchItemCreate


class TestWatchItemCreate:
    def test_valid(self):
        item = WatchItemCreate(name="PS5", max_price=300.0, location="NYC", radius=25)
        assert item.name == "PS5"
        assert item.max_price == 300.0

    def test_minimal(self):
        item = WatchItemCreate(name="PS5")
        assert item.max_price is None
        assert item.location is None
        assert item.radius is None

    def test_empty_name_fails(self):
        with pytest.raises(ValidationError):
            WatchItemCreate(name="")

    def test_long_name_fails(self):
        with pytest.raises(ValidationError):
            WatchItemCreate(name="x" * 201)


class TestDealQuality:
    def test_values(self):
        assert DealQuality.great.value == "great"
        assert DealQuality.good.value == "good"
        assert DealQuality.fair.value == "fair"
        assert DealQuality.none.value == "none"
