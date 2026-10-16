"""The dashboard sync payloads, on temp folders. No network."""

import json
import tempfile
import unittest
from pathlib import Path

from scout import sync


class Push(unittest.TestCase):
    def test_payload_carries_first_seen_and_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            d, c = Path(tmp) / "data", Path(tmp) / "config"
            d.mkdir(); c.mkdir()
            (d / "matches.json").write_text(json.dumps({"generated_at": "2026-10-14T23:00:00+00:00", "counts": {"kept": 1},
                                                        "matches": [{"key": "a", "company": "Acme", "score": 70}]}))
            (d / "seen.json").write_text(json.dumps({"a": {"at": "2026-10-14T22:00:00+00:00", "via": "instant"}}))
            (d / "tracker.json").write_text(json.dumps({"a": {"state": "Prepped", "updated": "2026-10-14"}}))
            (c / "targets.yaml").write_text("tier1: {}\n")
            payload = sync.build_push_payload(d, c)
            self.assertEqual(payload["matches"][0]["first_seen"], "2026-10-14T22:00:00+00:00")
            self.assertEqual(payload["tracker"]["a"]["state"], "Prepped")
            self.assertEqual(payload["config_text"]["targets"], "tier1: {}\n")
            self.assertEqual(payload["config_text"]["scoring"], "")
            self.assertEqual(payload["total_matches"], 1, "falls back to the rows sent when the file has no total")

    def test_payload_carries_the_real_total(self):
        with tempfile.TemporaryDirectory() as tmp:
            d, c = Path(tmp) / "data", Path(tmp) / "config"
            d.mkdir(); c.mkdir()
            (d / "matches.json").write_text(json.dumps({"total_matches": 1197,
                                                        "matches": [{"key": f"k{i}", "company": "Acme"} for i in range(300)]}))
            payload = sync.build_push_payload(d, c)
            self.assertEqual(payload["total_matches"], 1197)
            self.assertEqual(len(payload["matches"]), 300)

    def test_the_dashboard_counts_from_the_total(self):
        worker = (Path(__file__).parent.parent / "worker" / "src" / "index.js").read_text()
        self.assertIn("total_matches: Number.isInteger(body.total_matches)", worker, "ingest keeps the total")
        self.assertIn('id="open-count">${openCount}', worker, "the big number is the real count")
        self.assertIn("ranked from the top ${data.matches.length} by score", worker)


class Pull(unittest.TestCase):
    def test_writes_tracker_queue_passed(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            summary = sync.apply_pull({"tracker": {"a": {"state": "Applied"}}, "queue": [{"key": "b"}], "passed": {"c": "2026-10-14"}}, d)
            self.assertEqual(summary, {"tracker": 1, "queue": 1, "passed": 1})
            self.assertEqual(json.loads((d / "queue.json").read_text())[0]["key"], "b")


class Settings(unittest.TestCase):
    def test_missing_settings_mean_skip(self):
        import os
        saved = {k: os.environ.pop(k, None) for k in ("SCOUT_URL", "SCOUT_INGEST_SECRET")}
        try:
            if not sync.ENV_FILE.exists():
                self.assertIsNone(sync.settings())
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v


class TrackerOnly(unittest.TestCase):
    def test_sends_only_the_tracker_to_its_own_route(self):
        from unittest import mock
        calls = []
        with mock.patch.object(sync, "settings", return_value=("https://dash.example", "s")), \
             mock.patch.object(sync, "_load", return_value={"k": {"state": "Prepped", "updated": "2026-10-16"}}), \
             mock.patch.object(sync, "_call", side_effect=lambda url, secret, method="GET", body=None: calls.append((url, body)) or {"tracker": 1}), \
             mock.patch("sys.argv", ["scout.sync", "push", "--tracker-only"]):
            self.assertEqual(sync.main(), 0)
        self.assertEqual(calls, [("https://dash.example/api/ingest-tracker", {"tracker": {"k": {"state": "Prepped", "updated": "2026-10-16"}}})])


if __name__ == "__main__":
    unittest.main()
