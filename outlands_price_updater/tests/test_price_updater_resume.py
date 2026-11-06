import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from core import collector
from core.checkpoint import load_checkpoint, save_checkpoint
from core.price_logic import VendorListing
from core.search_catalog import SearchSpec
from core.site_search import SearchReadError, SiteAccessStopped


class FakePage:
    def wait_for_timeout(self, _ms):
        pass


def listings(price):
    return [VendorListing(price=price, listed_at=None)], 0


class RunCollectionResumeTests(unittest.TestCase):
    def setUp(self):
        self.names = ["A", "B", "C"]
        self.specs = {name: SearchSpec(name.lower(), name.lower()) for name in self.names}

    def collect(self, side_effects, **kwargs):
        with mock.patch.object(collector, "check_challenge"), mock.patch.object(
            collector, "read_item_prices", side_effect=side_effects
        ), mock.patch.object(
            collector, "estimate_price", side_effect=lambda l: mock.Mock(
                price=l[0].price, eligible_count=1, ignored_old_count=0,
                used_count=1, method="latest",
            ),
        ):
            return collector.run_collection(
                FakePage(), self.names, self.specs, [], log=lambda _m: None, **kwargs
            )

    def test_retry_same_item_after_failure(self):
        reopened = []
        prices = self.collect(
            [listings(1), SearchReadError("boom"), listings(2), listings(3)],
            ask_retry=lambda _name: True,
            reopen_page=lambda: reopened.append(True),
        )
        self.assertEqual(prices, {"A": 1, "B": 2, "C": 3})
        self.assertEqual(reopened, [True])

    def test_declined_retry_raises_and_keeps_progress(self):
        saved = []
        with self.assertRaises(SearchReadError):
            self.collect(
                [listings(1), SearchReadError("boom")],
                ask_retry=lambda _name: False,
                save_progress=lambda p: saved.append(dict(p)),
            )
        self.assertEqual(saved, [{"A": 1}])

    def test_site_block_is_never_retried(self):
        asked = []
        with self.assertRaises(SiteAccessStopped):
            self.collect(
                [listings(1), SiteAccessStopped("429")],
                ask_retry=lambda name: asked.append(name) or True,
            )
        self.assertEqual(asked, [])

    def test_resume_skips_collected_items(self):
        prices = self.collect([listings(3)], prices_by_variable={"A": 1, "B": 2})
        self.assertEqual(prices, {"A": 1, "B": 2, "C": 3})


class CheckpointTests(unittest.TestCase):
    def test_round_trip_and_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "out.razor.progress.json"
            save_checkpoint(path, {"A": 5})
            self.assertEqual(load_checkpoint(path, ["A", "B"]), {"A": 5})
            with self.assertRaises(ValueError):
                load_checkpoint(path, ["B"])
            path.write_text("not json", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_checkpoint(path, ["A"])

    def test_creation_time_kept_and_age_limit_enforced(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "out.razor.progress.json"
            save_checkpoint(path, {"A": 5})
            created = json.loads(path.read_text(encoding="utf-8"))["created_at"]
            save_checkpoint(path, {"A": 5, "B": 6})
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8"))["created_at"], created
            )
            created_at = datetime.fromisoformat(created)
            fresh = created_at + timedelta(days=6, hours=23)
            self.assertEqual(
                load_checkpoint(path, ["A", "B"], now=fresh),
                {"A": 5, "B": 6},
            )
            with self.assertRaises(ValueError):
                load_checkpoint(
                    path, ["A", "B"], now=created_at + timedelta(days=7, minutes=1)
                )

    def test_checkpoint_without_creation_time_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "old.progress.json"
            path.write_text('{"prices": {"A": 5}}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_checkpoint(path, ["A"])


if __name__ == "__main__":
    unittest.main()
