"""Unit tests for scoring.py. The breakdown must always add up to the score. No network."""

import unittest

from scout import scoring

W = scoring.load_weights()
NOW = 1_800_000_000  # a fixed "now" so freshness is deterministic


def described(**over):
    item = {"role": "swe", "tier": 3, "early_career": "none", "degree_class": "unknown",
            "location_class": "other", "date_posted": NOW - 30 * 86400, "keyword_hits": []}
    item.update(over)
    return item


class Score(unittest.TestCase):
    def test_breakdown_sums_to_score(self):
        item = scoring.score(described(tier=1, location_class="priority", degree_class="bachelors"), W, NOW)
        self.assertEqual(item["score"], sum(item["breakdown"].values()))

    def test_capped_at_100(self):
        item = scoring.score(described(tier=1, early_career="strong", degree_class="bachelors",
                                       location_class="priority", date_posted=NOW - 60,
                                       keyword_hits=["ai", "ios", "cloud", "design"]), W, NOW)
        self.assertEqual(item["score"], 100)
        self.assertGreater(sum(item["breakdown"].values()), 100)

    def test_role_order(self):
        swe = scoring.score(described(role="swe"), W, NOW)["score"]
        amb = scoring.score(described(role="ambassador"), W, NOW)["score"]
        pm = scoring.score(described(role="pm"), W, NOW)["score"]
        it = scoring.score(described(role="it"), W, NOW)["score"]
        design = scoring.score(described(role="design"), W, NOW)["score"]
        self.assertTrue(swe > amb > pm > it > design)

    def test_program_beats_plain_tier1_swe(self):
        # A freshman program at an unknown company with no role word in the title must outrank
        # a plain Tier 1 SWE posting, because those programs are the point for a freshman.
        program = scoring.score(described(role="none", early_career="strong", tier=3, location_class="us"), W, NOW)
        plain = scoring.score(described(role="swe", tier=1, degree_class="bachelors", location_class="us"), W, NOW)
        self.assertEqual(program["role"], "program")
        self.assertGreater(program["score"], plain["score"])

    def test_freshness(self):
        self.assertEqual(scoring.freshness_class(NOW - 3600, NOW), "under_24h")
        self.assertEqual(scoring.freshness_class(NOW - 3 * 86400, NOW), "under_7d")
        self.assertEqual(scoring.freshness_class(NOW - 30 * 86400, NOW), "older")
        self.assertEqual(scoring.freshness_class(NOW - 120 * 86400, NOW), "over_90d")
        self.assertEqual(scoring.freshness_class(0, NOW), "older")

    def test_old_postings_lose_points(self):
        fresh = scoring.score(described(date_posted=NOW - 30 * 86400), W, NOW)["score"]
        stale = scoring.score(described(date_posted=NOW - 120 * 86400), W, NOW)["score"]
        self.assertLess(stale, fresh)

    def test_keywords_capped(self):
        item = scoring.score(described(keyword_hits=["a", "b", "c", "d", "e"]), W, NOW)
        self.assertEqual(item["breakdown"]["keywords"], W["keywords"]["max"])

    def test_explain_mentions_total(self):
        item = scoring.score(described(), W, NOW)
        self.assertTrue(scoring.explain(item).endswith(f"= {item['score']}"))


if __name__ == "__main__":
    unittest.main()
