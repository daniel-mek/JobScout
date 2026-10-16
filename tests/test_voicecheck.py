"""The pre-send voice check. Synthetic cases always run; the real regression case (a rejected and an approved
answer, kept in the private me/regression/ folder) runs only on the candidate's own machine."""

import unittest
from pathlib import Path

from scout import voicecheck

PERSONAL = {"taglines": ["good design should disappear"], "entities": [["LumaBooth", "Lumasoft"]]}
POSTING = "Our mission is to make design accessible to all. Launches from early career designers include Figma Draw."
REGRESSION = Path(__file__).resolve().parent.parent / "me" / "regression"


def fails(text, posting=""):
    return voicecheck.check(text, posting, PERSONAL)["fail"]


class Rules(unittest.TestCase):
    def test_clean_answer_passes(self):
        text = ("I spent 45 minutes on one button, and my mentor kept asking what the user needed to feel, "
                "which is still the best design advice I have had (and the slowest).")
        self.assertEqual(fails(text, POSTING), [])

    def test_each_rule(self):
        self.assertIn("em or en dash", fails("A pause — then a point."))
        self.assertTrue(any("instead of" in f for f in fails("Instead of a file, a canvas, instead of waiting, shipping.")))
        self.assertFalse(any("instead of" in f for f in fails("One canvas instead of a file.")))
        self.assertTrue(any("passionate" in f for f in fails("I am passionate about design.")))
        self.assertTrue(any("tagline" in f for f in fails("Good design should disappear, they say.")))
        self.assertTrue(any("dad" in f for f in fails("My dad's company was rebuilding its site.")))
        self.assertTrue(any("bracket" in f for f in fails("We grew by [add the number] users.")))
        self.assertTrue(any("2 ways" in f for f in fails("Lumasoft's site was rebuilt; LumaBooth's pages came later.")))
        self.assertTrue(any('"lumabooth"' in f for f in fails("I redesigned lumabooth's website.")))

    def test_quoting_the_posting_back(self):
        text = "Figma's mission, to make design accessible to all, is what I care about."
        self.assertTrue(any("copied from the posting" in f for f in fails(text, POSTING)))

    def test_relative_dates_warn_only(self):
        result = voicecheck.check("I spent last summer on it.", "", PERSONAL)
        self.assertEqual(result["fail"], [])
        self.assertTrue(result["warn"])

    def test_sections_skip_field_lists_and_one_word_picks(self):
        md = ("# Kit\n\nDrafts only.\n\n## Why us?\n\n" + "word " * 20 + "\n\n## First choice\n\nProduct\n\n"
              "## Standard fields\n\n- Name: X\n- Email: Y\n")
        self.assertEqual([h for h, _ in voicecheck.sections(md)], ["Why us?"])


@unittest.skipUnless((REGRESSION / "figma-pd-why-approved.md").exists(), "private regression texts are not in this checkout")
class FigmaRegression(unittest.TestCase):
    """The answer he approved must pass; the draft he rejected must fail for the reasons the post-mortem names."""

    def test_approved_passes(self):
        text = (REGRESSION / "figma-pd-why-approved.md").read_text(encoding="utf-8")
        self.assertEqual(voicecheck.check(text, POSTING, voicecheck.load_personal())["fail"], [])

    def test_rejected_fails(self):
        text = (REGRESSION / "figma-pd-why-rejected.md").read_text(encoding="utf-8")
        result = " | ".join(voicecheck.check(text, POSTING, voicecheck.load_personal())["fail"])
        for reason in ("tagline", "2 ways", "instead of", "copied from the posting", "for a living"):
            self.assertIn(reason, result)


if __name__ == "__main__":
    unittest.main()
