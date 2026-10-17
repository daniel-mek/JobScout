"""Instant vs digest selection, the seen list, and message shapes. Nothing is sent. No network."""

import unittest

from scout import alerts, notify, scoring

W = scoring.load_weights()
NOW = 1_800_000_000


def match(key, **over):
    m = {"key": key, "company": "Acme", "title": "Software Engineer Intern", "url": f"https://x.com/{key}",
         "locations": ["Newark, NJ"], "score": 50, "tier": 3, "early_career": "none", "role": "swe",
         "eligibility": "unknown", "eligibility_note": "", "date_posted": NOW - 86400 * 2}
    m.update(over)
    return m


class Selection(unittest.TestCase):
    def test_instant_rules(self):
        self.assertTrue(alerts.is_instant(match("a", tier=1, score=65), W))
        self.assertFalse(alerts.is_instant(match("b", tier=1, score=40), W))
        self.assertFalse(alerts.is_instant(match("c", tier=3, score=90), W))
        self.assertFalse(alerts.is_instant(match("d", tier=3, score=40, early_career="strong"), W))
        self.assertFalse(alerts.is_instant(match("e", tier=3, role="ambassador"), W))
        self.assertFalse(alerts.is_instant(match("f", tier=1, score=90, eligibility="ineligible"), W))

    def test_seen_blocks_repeat_alerts(self):
        seen = {}
        ms = [match("a", tier=1, score=70), match("b", tier=1, score=70)]
        first = alerts.select_instant(ms, seen, W)
        alerts.mark_seen(seen, first, "instant", NOW)
        self.assertEqual(len(first), 2)
        self.assertEqual(alerts.select_instant(ms, seen, W), [])
        self.assertEqual(seen["a"]["via"], "instant")

    def test_digest_excludes_instant_and_low_scores(self):
        ms = [match("inst", tier=1, score=70), match("low", score=10)] + [match(f"d{i}", score=60 - i) for i in range(15)]
        chosen = alerts.select_digest(ms, {}, W)
        keys = [m["key"] for m in chosen]
        self.assertNotIn("inst", keys)
        self.assertNotIn("low", keys)
        self.assertEqual(len(chosen), W["digest_size"])


class Reposts(unittest.TestCase):
    def test_same_title_new_url_posted_later_alerts_again(self):
        seen = {}
        first = match("k", tier=1, score=80)
        first.update(urls=["https://x.com/1"], latest_posted=NOW - 86400 * 30)
        alerts.mark_seen(seen, [first], "instant", NOW - 86400 * 20)
        self.assertFalse(alerts.is_new(first, seen))
        repost = dict(first, urls=["https://x.com/2"], latest_posted=NOW - 86400)
        self.assertTrue(alerts.is_new(repost, seen))
        old_twin = dict(first, urls=["https://x.com/3"], latest_posted=NOW - 86400 * 40)
        self.assertFalse(alerts.is_new(old_twin, seen))


class Messages(unittest.TestCase):
    def test_match_push_has_no_personal_data_and_a_link(self):
        push = notify.match_push(match("a", tier=1, score=75, early_career="strong", eligibility="ok",
                                       eligibility_note="profile eligibility confirmed"), NOW)
        self.assertEqual(push["click"], "https://x.com/a")
        self.assertIn("Acme", push["title"])
        self.assertIn("Score 75", push["message"])
        self.assertNotIn("freshman", push["message"])
        self.assertEqual(push["priority"], 4)

    def test_unread_eligibility_pushes_quietly(self):
        push = notify.match_push(match("a", tier=1, score=90, early_career="strong"), NOW)
        self.assertEqual(push["priority"], 3)
        self.assertIn("review the posting requirements", push["message"])

    def test_digest_push(self):
        push = notify.digest_push([match("a", score=61), match("b", score=55)], NOW)
        self.assertIn("2 new matches", push["title"])
        self.assertIn("https://x.com/b", push["message"])
        self.assertEqual(notify.digest_push([], NOW)["title"], "Scout digest: nothing new today")

    def test_ntfy_payload_shape(self):
        captured = []
        n = notify.Ntfy("topic-abc", sender=lambda payload: captured.append(payload) or True)
        self.assertTrue(n.send("Title", "Body", click="https://x.com", priority=4, tags=["eyes"]))
        self.assertEqual(captured[0]["topic"], "topic-abc")
        self.assertEqual(captured[0]["click"], "https://x.com")
        self.assertEqual(captured[0]["tags"], ["eyes"])

    def test_send_failure_is_false_not_an_exception(self):
        def boom(payload):
            raise OSError("no network")
        self.assertFalse(notify.Ntfy("t", sender=boom).send("a", "b"))

    def test_et_hour(self):
        # 2026-10-14 23:00 UTC is 7:00 PM EDT
        self.assertEqual(notify.et_hour(1792018800), 19)


if __name__ == "__main__":
    unittest.main()
