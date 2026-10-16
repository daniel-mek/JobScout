"""Prep kits for the Review page, and phone edits written back. Temp folders only, no network."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scout import kits

ANSWERS = """# Acme, Software Engineer Intern: application answers

Drafts only.

## Why Acme?

Because Acme ships.

## Tell us about a project

Command Center puts everything on one screen.

## Standard fields

- Authorized: Yes
"""


class Kits(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "me").mkdir()
        self.lessons = mock.patch.object(kits, "LESSONS", self.root / "me" / "voice-lessons.md")
        self.lessons.start()
        self.addCleanup(self.lessons.stop)
        self.kit = self.root / "acme-software-engineer-intern"
        self.kit.mkdir()
        (self.kit / "answers.md").write_text(ANSWERS)
        (self.kit / "match.json").write_text(json.dumps({"key": "acme_swe", "company": "Acme", "title": "SWE Intern", "url": "https://x.com"}))
        (self.kit / "Jeremiah-Sleman-Resume-Acme.pdf").write_bytes(b"%PDF-1.4 fake")

    def tearDown(self):
        self.tmp.cleanup()

    def test_split_and_join_round_trip(self):
        intro, sections = kits.split_answers(ANSWERS)
        self.assertEqual(intro, "Drafts only.")
        self.assertEqual([s["q"] for s in sections], ["Why Acme?", "Tell us about a project", "Standard fields"])
        self.assertEqual(kits.join_answers("Acme, Software Engineer Intern: application answers", intro, sections), ANSWERS)

    def test_pack_carries_the_tracker_key_and_files(self):
        kit = kits.pack_all(self.root)[0]
        self.assertEqual((kit["slug"], kit["key"], kit["company"]), ("acme-software-engineer-intern", "acme_swe", "Acme"))
        self.assertTrue(kit["resume_pdf"])
        self.assertEqual(kit["letter"], "")

    def test_phone_edits_go_back_under_the_same_heading(self):
        edits = {"acme-software-engineer-intern": {"answers": [{"q": "Why Acme?", "a": "Because Acme ships, and I want in.", "edited": True}]}}
        self.assertEqual(kits.apply_edits(edits, self.root), 1)
        text = (self.kit / "answers.md").read_text()
        self.assertIn("## Why Acme?\n\nBecause Acme ships, and I want in.\n", text)
        self.assertIn("Command Center puts everything on one screen.", text)
        self.assertEqual(kits.apply_edits(edits, self.root), 0, "a second pull changes nothing")
        log = (self.root / "me" / "voice-lessons.md").read_text()
        self.assertIn("### [new]", log)
        self.assertIn("> Because Acme ships.", log)
        self.assertIn("> Because Acme ships, and I want in.", log)
        self.assertEqual(log.count("### [new]"), 1, "only real changes are logged")

    def test_a_renamed_question_and_unknown_kits_are_left_alone(self):
        edits = {"acme-software-engineer-intern": {"answers": [{"q": "Old heading", "a": "x", "edited": True}]},
                 "../escape": {"answers": [{"q": "Why Acme?", "a": "x", "edited": True}]}}
        self.assertEqual(kits.apply_edits(edits, self.root), 0)
        self.assertEqual((self.kit / "answers.md").read_text(), ANSWERS)

    def test_letter_edit_rewrites_the_body_and_rebuilds(self):
        (self.kit / "cover-letter.md").write_text("name: Jeremiah Sleman\nclosing: Sincerely\n---\nOld body.\n")
        with mock.patch("subprocess.run") as run:
            self.assertEqual(kits.apply_edits({"acme-software-engineer-intern": {"answers": [], "letter": "New body."}}, self.root), 1)
        self.assertEqual((self.kit / "cover-letter.md").read_text(), "name: Jeremiah Sleman\nclosing: Sincerely\n---\nNew body.\n")
        run.assert_called_once()


class Push(unittest.TestCase):
    def test_push_kits_goes_to_its_own_route(self):
        from scout import sync
        calls = []
        with mock.patch.object(sync, "settings", return_value=("https://dash.example", "s")), \
             mock.patch.object(kits, "pack_all", return_value=[{"slug": "a"}]), \
             mock.patch.object(sync, "_call", side_effect=lambda url, secret, method="GET", body=None: calls.append((url, body)) or {"kits": 1}), \
             mock.patch("sys.argv", ["scout.sync", "push", "--kits"]):
            self.assertEqual(sync.main(), 0)
        self.assertEqual(calls, [("https://dash.example/api/ingest-kits", {"kits": [{"slug": "a"}]})])


if __name__ == "__main__":
    unittest.main()
