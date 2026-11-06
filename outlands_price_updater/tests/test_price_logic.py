import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from core.price_logic import VendorListing, estimate_price, parse_listed_at, parse_price

NOW = datetime(2025, 1, 31, 12, 0, tzinfo=timezone.utc)


def listing(price: int, days_ago: int) -> VendorListing:
    return VendorListing(Decimal(price), NOW - timedelta(days=days_ago))


class ParsePriceTests(unittest.TestCase):
    def test_strips_commas_and_symbols(self):
        self.assertEqual(parse_price(" $1,250 "), Decimal("1250"))

    def test_rejects_non_numeric(self):
        with self.assertRaises(ValueError):
            parse_price("free")


class ParseListedAtTests(unittest.TestCase):
    def test_relative_days(self):
        self.assertEqual(parse_listed_at("3 days ago", now=NOW), NOW - timedelta(days=3))

    def test_yesterday(self):
        self.assertEqual(parse_listed_at("yesterday", now=NOW), NOW - timedelta(days=1))

    def test_rejects_future_date(self):
        with self.assertRaises(ValueError):
            parse_listed_at("2099-01-01", now=NOW)


class EstimatePriceTests(unittest.TestCase):
    def test_ignores_listings_sixty_days_or_older(self):
        estimate = estimate_price(
            [listing(100, 1), listing(9999, 60), listing(200, 2)], now=NOW
        )
        self.assertEqual(estimate.price, 100)
        self.assertEqual(estimate.ignored_old_count, 1)

    def test_uses_latest_when_five_or_fewer_recent(self):
        estimate = estimate_price(
            [listing(500, 10), listing(300, 1), listing(400, 5)], now=NOW
        )
        self.assertEqual(estimate.price, 300)
        self.assertEqual(estimate.method, "latest listing")

    def test_only_first_ten_listings_are_considered(self):
        listings = [listing(100, 1)] * 10 + [listing(1_000_000, 1)]
        self.assertEqual(estimate_price(listings, now=NOW).price, 100)

    def test_averages_when_spread_is_small(self):
        listings = [listing(p, 1) for p in (100, 110, 120, 130, 140, 150)]
        self.assertEqual(estimate_price(listings, now=NOW).price, 125)

    def test_even_count_median_outlier_filter(self):
        listings = [listing(p, 1) for p in (100, 100, 100, 100, 100, 100, 1000)]
        estimate = estimate_price(listings, now=NOW)
        self.assertEqual(estimate.price, 100)
        self.assertEqual(estimate.used_count, 6)

    def test_floors_fractional_result(self):
        listings = [listing(p, 1) for p in (101, 102, 103, 104, 105, 106)]
        self.assertEqual(estimate_price(listings, now=NOW).price, 103)

    def test_empty_listings_raise(self):
        with self.assertRaises(ValueError):
            estimate_price([], now=NOW)

    def test_all_old_listings_raise(self):
        with self.assertRaises(ValueError):
            estimate_price([listing(100, 90)], now=NOW)


if __name__ == "__main__":
    unittest.main()
