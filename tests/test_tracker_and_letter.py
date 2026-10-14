"""Tracker state changes and cover-letter parsing. No network, no PDF rendering."""

import unittest

from scout import build_letter, tracker


class Tracker(unittest.TestCase):
    def test_new_row_from_match_and_history(self):
        t = {}
        match = {"company": "Acme", "title": "SWE Intern", "url": "https://x", "score": 70}
        row = tracker.set_state(t, "acme_swe-intern", "Prepped", note="kit built", match=match, today="2026-10-15")
        self.assertEqual(row["state"], "Prepped")
        self.assertEqual(row["company"], "Acme")
        self.assertEqual(row["history"], [{"date": "2026-10-15", "state": "Prepped"}])
        self.assertEqual(row["notes"], ["2026-10-15: kit built"])

    def test_applied_date_is_set_once(self):
        t = {}
        tracker.set_state(t, "k", "Applied", today="2026-10-15")
        tracker.set_state(t, "k", "OA", today="2026-10-20")
        tracker.set_state(t, "k", "Applied", today="2026-10-25")
        self.assertEqual(t["k"]["applied"], "2026-10-15")
        self.assertEqual(len(t["k"]["history"]), 3)

    def test_unknown_state_rejected(self):
        with self.assertRaises(ValueError):
            tracker.set_state({}, "k", "Ghosted")


class Letter(unittest.TestCase):
    def test_parse(self):
        text = ("name: Jane Doe\ncontact: (555) 123-4567 | jane@example.com\ndate: October 15, 2026\n"
                "to: Hiring Team, Acme\n---\nFirst paragraph\nstill first.\n\nSecond paragraph.\n")
        data = build_letter.parse_letter(text)
        self.assertEqual(data["name"], "Jane Doe")
        self.assertEqual(data["contact"], ["(555) 123-4567", "jane@example.com"])
        self.assertEqual(data["paragraphs"], ["First paragraph still first.", "Second paragraph."])
        self.assertEqual(data["closing"], "Sincerely")

    def test_dash_check_regex(self):
        self.assertTrue(build_letter.DASHES.search("a — b"))
        self.assertFalse(build_letter.DASHES.search("a - b"))


if __name__ == "__main__":
    unittest.main()
