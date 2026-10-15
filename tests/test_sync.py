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


if __name__ == "__main__":
    unittest.main()
