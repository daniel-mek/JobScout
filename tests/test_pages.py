"""Page watcher on fake pages. No network."""

import tempfile
import unittest
from pathlib import Path

from scout import pages

FILLER = "<p>" + " ".join(f"Paragraph {i} describes the program, who it is for, and how the summer is structured." for i in range(12)) + "</p>"
PAGE_V1 = ("<html><head><title>Explore</title><script>var x='abc';</script></head><body><h1>Explore Program</h1>"
           "<p>Applications open in September.</p><span>nonce 9f8e7d6c5b4a39281716</span><p>id 1234567</p>" + FILLER + "</body></html>")
PAGE_V2 = PAGE_V1.replace("Applications open in September.", "Applications are now open. Apply by October 31.")


class TextExtraction(unittest.TestCase):
    def test_strips_tags_scripts_and_noise(self):
        text = pages.html_to_text(PAGE_V1)
        self.assertIn("Explore Program", text)
        self.assertIn("Applications open in September.", text)
        self.assertNotIn("var x", text)
        self.assertNotIn("9f8e7d6c5b4a39281716", text)   # hex nonce removed
        self.assertNotIn("1234567", text)                # long number removed

    def test_noise_does_not_change_hash(self):
        a = pages.html_to_text(PAGE_V1)
        b = pages.html_to_text(PAGE_V1.replace("9f8e7d6c5b4a39281716", "00112233445566778899").replace("1234567", "7654321"))
        self.assertEqual(pages.text_hash(a), pages.text_hash(b))


class Carousel(unittest.TestCase):
    def test_rotating_job_cards_are_removed(self):
        lines = ["Explore Microsoft", "Applications open in September.",
                 "Applied Sciences Intern", "2026-10-15", "United Kingdom, London", "3 days / week in-office",
                 "<b>Overview</b> long description", "See details",
                 "Customer Success Account Manager", "2026-10-14", "India", "See details",
                 "Who should apply"]
        self.assertEqual(pages.drop_job_carousels(lines),
                         ["Explore Microsoft", "Applications open in September.", "Who should apply"])

    def test_a_date_without_see_details_is_kept(self):
        lines = ["Deadline", "2026-11-01", "Apply now"]
        self.assertEqual(pages.drop_job_carousels(lines), lines)


class Watching(unittest.TestCase):
    def run_once(self, state, html, tmp):
        return pages.check_pages([{"name": "Explore", "url": "https://example.com/explore"}], state,
                                 fetch=lambda url: pages.html_to_text(html) if html is not None else None,
                                 text_dir=Path(tmp), now=1_800_000_000)

    def test_first_run_is_baseline_then_change_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = {}
            first = self.run_once(state, PAGE_V1, tmp)
            self.assertEqual([e["kind"] for e in first], ["baseline"])
            same = self.run_once(state, PAGE_V1, tmp)
            self.assertEqual(same, [])
            changed = self.run_once(state, PAGE_V2, tmp)
            self.assertEqual([e["kind"] for e in changed], ["changed"])
            self.assertIn("Apply by October 31", changed[0]["summary"])

    def test_region_token_and_removals_do_not_alert(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = {}
            self.run_once(state, PAGE_V1 + "<p>served from us-east-1</p>", tmp)
            # the same page from another server: region differs, nothing new was written
            events = self.run_once(state, PAGE_V1 + "<p>served from us-west-2</p>", tmp)
            self.assertEqual(events, [], "a region string must not count as a change")
            # a line removed is recorded but not alerted
            events = self.run_once(state, PAGE_V1.replace("<p>Applications open in September.</p>", ""), tmp)
            self.assertEqual([e["kind"] for e in events], ["shuffled"])

    def test_only_real_changes_mark_the_page_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = {}
            self.run_once(state, PAGE_V1, tmp)
            self.run_once(state, PAGE_V1.replace("<p>Applications open in September.</p>", ""), tmp)
            record = state["https://example.com/explore"]
            self.assertEqual(record["changed_at"], 0, "a removal is not a change worth showing")
            self.run_once(state, PAGE_V2, tmp)
            self.assertGreater(record["changed_at"], 0)
            self.assertIn("Apply by October 31", record["last_change"])

    def test_page_text_is_never_stored(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.run_once({}, PAGE_V1, tmp)
            stored = "".join(f.read_text() for f in Path(tmp).iterdir())
            self.assertNotIn("Applications open in September", stored)
            self.assertEqual([f.suffix for f in Path(tmp).iterdir()], [".prints"])

    def test_old_saved_text_is_read_once_then_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = {}
            self.run_once(state, PAGE_V1, tmp)
            prints = next(Path(tmp).glob("*.prints"))
            prints.rename(prints.with_suffix(".txt"))  # what an older run left behind
            prints.with_suffix(".txt").write_text(pages.html_to_text(PAGE_V1))
            changed = self.run_once(state, PAGE_V2, tmp)
            self.assertEqual([e["kind"] for e in changed], ["changed"])
            self.assertEqual([f.suffix for f in Path(tmp).iterdir()], [".prints"])

    def test_unreadable_alerts_after_two_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = {}
            self.run_once(state, PAGE_V1, tmp)
            self.assertEqual(self.run_once(state, None, tmp), [])
            events = self.run_once(state, None, tmp)
            self.assertEqual([e["kind"] for e in events], ["unreadable"])
            self.assertEqual(self.run_once(state, None, tmp), [])  # alerted once, not every run

    def test_thin_page_alerts_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = {}
            events = self.run_once(state, "<html><body><div id='app'></div></body></html>", tmp)
            self.assertEqual(sorted(e["kind"] for e in events), ["baseline", "thin"])
            self.assertEqual(self.run_once(state, "<html><body><div id='app'></div></body></html>", tmp), [])

    def test_config_loads(self):
        loaded = pages.load_pages()
        self.assertGreaterEqual(len(loaded), 5)
        for p in loaded:
            self.assertTrue(p["url"].startswith("https://"))
            self.assertTrue(p.get("name"))


if __name__ == "__main__":
    unittest.main()
