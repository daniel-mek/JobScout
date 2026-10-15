"""The once-a-day digest check. No network."""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scout import run

ET = ZoneInfo("America/New_York")


def ts(y, mo, d, h, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=ET).timestamp()


class DigestDue(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "digest.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_not_before_seven(self):
        self.assertFalse(run.digest_due(ts(2026, 10, 15, 18, 59), self.path))

    def test_due_after_seven_when_not_sent(self):
        self.assertTrue(run.digest_due(ts(2026, 10, 15, 19, 17), self.path))
        self.assertTrue(run.digest_due(ts(2026, 10, 15, 23, 17), self.path), "a late run still sends it")

    def test_only_once_per_new_york_day(self):
        self.path.write_text(json.dumps({"last_sent": "2026-10-15"}))
        self.assertFalse(run.digest_due(ts(2026, 10, 15, 21, 17), self.path))
        self.assertTrue(run.digest_due(ts(2026, 10, 16, 19, 17), self.path))

    def test_after_midnight_utc_is_still_the_same_new_york_day(self):
        # 8:17 PM EDT on Oct 15 is 00:17 UTC on Oct 16; the date that counts is New York's
        self.path.write_text(json.dumps({"last_sent": "2026-10-15"}))
        self.assertFalse(run.digest_due(ts(2026, 10, 15, 20, 17), self.path))

    def test_winter_time(self):
        self.assertFalse(run.digest_due(ts(2026, 12, 1, 18, 17), self.path))
        self.assertTrue(run.digest_due(ts(2026, 12, 1, 19, 17), self.path))


if __name__ == "__main__":
    unittest.main()
