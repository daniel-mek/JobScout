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


class RowCount(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "health.json"

    def tearDown(self):
        self.tmp.cleanup()

    def sender(self):
        sender = run.Sender(topic="t", dry_run=False)
        sender.pushes = []
        sender.send = lambda push: sender.pushes.append(push) or True
        return sender

    def test_half_the_rows_gone_warns(self):
        self.path.write_text(json.dumps({"rows": 17000}))
        sender = self.sender()
        run.check_row_count(sender, 6000, self.path)
        self.assertEqual(len(sender.pushes), 1)
        self.assertIn("6000", sender.pushes[0]["message"])
        self.assertEqual(json.loads(self.path.read_text())["rows"], 6000)

    def test_normal_change_and_first_run_stay_quiet(self):
        sender = self.sender()
        run.check_row_count(sender, 17000, self.path)
        run.check_row_count(sender, 16500, self.path)
        self.assertEqual(sender.pushes, [])


if __name__ == "__main__":
    unittest.main()
