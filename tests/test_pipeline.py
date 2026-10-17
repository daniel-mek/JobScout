"""The whole watcher on fixtures, offline. Checks the properties that must always hold."""

import unittest
from pathlib import Path

from scout import listings, matching, scoring, watch

FIXTURES = Path(__file__).parent / "fixtures"


class Pipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = {"simplify_newgrad": listings.load_json(FIXTURES / "simplify_newgrad.json")}
        cls.matches, cls.counts = watch.run(raw, matching.load_targets(), scoring.load_weights(),
                                            check_pages=5, allow_network=False, now=1_800_000_000)

    def test_something_survives(self):
        self.assertGreater(len(self.matches), 0)
        self.assertEqual(self.counts["kept"], len(self.matches))

    def test_every_row_that_could_push_gets_its_page_checked(self):
        for m in self.matches[5:]:
            if watch.could_push(m):
                self.assertNotEqual(m["eligibility_note"], "not checked (below top rows)", m["title"])

    def test_only_active_fulltime_early_career_roles(self):
        for m in self.matches:
            self.assertNotEqual(m["degree_class"], "graduate_only", m["title"])
            self.assertTrue(m["active"])
            self.assertEqual(m["career_level"], "entry_level")

    def test_only_target_roles(self):
        for m in self.matches:
            self.assertIn(m["role"], ("it", "swe"))

    def test_sorted_eligible_first_then_score_then_date(self):
        keys = [(m["eligibility"] != "ineligible", m["score"], m["date_posted"]) for m in self.matches]
        self.assertEqual(keys, sorted(keys, reverse=True))

    def test_ineligible_sinks_below_eligible(self):
        from scout import eligibility
        raw = {"simplify_newgrad": listings.load_json(FIXTURES / "simplify_newgrad.json")}
        original = eligibility.check
        def fake_check(item, cache, allow_network=True):
            item["eligibility"], item["eligibility_note"] = ("ineligible", "test") if item is first[0] else ("unknown", "")
            return item
        first = []
        try:
            eligibility.check = lambda item, *a, **k: (first.append(item) if not first else None, fake_check(item, *a, **k))[1]
            matches, _ = watch.run(raw, matching.load_targets(), scoring.load_weights(), check_pages=5, allow_network=False, now=1_800_000_000)
        finally:
            eligibility.check = original
        self.assertEqual(matches[-1]["eligibility"], "ineligible")

    def test_every_match_explains_itself(self):
        for m in self.matches:
            self.assertEqual(m["score"], min(100, sum(m["breakdown"].values())))
            self.assertIn(m["eligibility"], ("ok", "ineligible", "unknown"))
            self.assertIn("key", m)

    def test_drop_counts_are_reported(self):
        self.assertIn("dropped: graduate students only", self.counts)
        self.assertIn("dropped: not a target role", self.counts)
        self.assertIn("dropped: inactive", self.counts)


if __name__ == "__main__":
    unittest.main()
