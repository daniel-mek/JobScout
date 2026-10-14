"""The whole watcher on fixtures, offline. Checks the properties that must always hold."""

import unittest
from pathlib import Path

from scout import listings, matching, scoring, watch

FIXTURES = Path(__file__).parent / "fixtures"


class Pipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = {"simplify": listings.load_json(FIXTURES / "simplify.json"),
               "vanshb03": listings.load_json(FIXTURES / "vanshb03.json")}
        cls.matches, cls.counts = watch.run(raw, matching.load_targets(), scoring.load_weights(),
                                            check_pages=5, allow_network=False, now=1_800_000_000)

    def test_something_survives(self):
        self.assertGreater(len(self.matches), 0)
        self.assertEqual(self.counts["kept"], len(self.matches))

    def test_no_graduate_only_or_inactive_or_wrong_year(self):
        for m in self.matches:
            self.assertNotEqual(m["degree_class"], "graduate_only", m["title"])
            self.assertTrue(m["active"])
            self.assertTrue(any("2027" in t for t in m["terms"]), m["title"])

    def test_no_hardware_or_quant_without_a_program(self):
        for m in self.matches:
            if m["role"] == "none":
                self.assertEqual(m["early_career"], "strong", m["title"])

    def test_sorted_by_score_then_date(self):
        keys = [(m["score"], m["date_posted"]) for m in self.matches]
        self.assertEqual(keys, sorted(keys, reverse=True))

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
