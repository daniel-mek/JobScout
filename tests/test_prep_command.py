"""The /prep instructions, checked for the rules the October 16 review asked for. No network."""

import re
import unittest
from pathlib import Path

PREP = (Path(__file__).parent.parent / ".claude" / "commands" / "prep.md").read_text(encoding="utf-8")


class Prep(unittest.TestCase):
    def test_prepped_is_what_hides_a_queued_posting(self):
        self.assertIn("the tracker state `Prepped` set in Step 6 is what hides a queued posting", PREP)
        self.assertNotIn("remove it from the queue", PREP, "nothing removes queue entries; do not promise it")

    def test_resume_json_goes_to_the_reviewer_verbatim(self):
        self.assertIn("`resume.json` as the raw JSON file", PREP)
        self.assertIn("verbatim", PREP)

    def test_says_what_to_do_when_the_reviewer_fails(self):
        self.assertIn("If the reviewer errors or times out, resume it once", PREP)
        self.assertIn("run checks A to D yourself", PREP)

    def test_mentions_the_html_next_to_the_pdf(self):
        self.assertIn("also writes an `.html` file next to the PDF", PREP)

    def test_no_em_or_en_dashes(self):
        self.assertIsNone(re.search("[\u2013\u2014]", PREP))


if __name__ == "__main__":
    unittest.main()
