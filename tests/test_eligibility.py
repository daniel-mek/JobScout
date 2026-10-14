"""The graduation-year reader, on HTML snippets. No network."""

import unittest

from scout import eligibility

GRAD = 2030


class Verdicts(unittest.TestCase):
    def test_range_that_excludes_him(self):
        text = "<p>Candidates must be graduating between December 2027 and June 2028.</p>"
        verdict, note = eligibility.verdict_from_text(eligibility._TAGS.sub(" ", text), GRAD)
        self.assertEqual(verdict, "ineligible")
        self.assertIn("2027", note)

    def test_class_of_that_includes_him(self):
        text = "Open to students in the Class of 2029 or 2030."
        self.assertEqual(eligibility.verdict_from_text(text, GRAD)[0], "ok")

    def test_single_year_that_excludes_him(self):
        text = "Expected graduation date: May 2028."
        self.assertEqual(eligibility.verdict_from_text(text, GRAD)[0], "ineligible")

    def test_underclass_words_win(self):
        text = "This program is for freshmen and sophomores. Graduating 2029 or later preferred."
        self.assertEqual(eligibility.verdict_from_text(text, GRAD)[0], "ok")

    def test_silence_is_unknown(self):
        text = "We are looking for a motivated intern who loves to code."
        self.assertEqual(eligibility.verdict_from_text(text, GRAD)[0], "unknown")

    def test_years_mentioned(self):
        self.assertEqual(eligibility.years_mentioned("graduating in 2027 or 2028 from an accredited program"), [2027, 2028])
        self.assertEqual(eligibility.years_mentioned("2028 graduates welcome"), [2028])
        self.assertEqual(eligibility.years_mentioned("Expected graduation dates of December 2028, May 2029, December 2029, or May 2030."),
                         [2028, 2029, 2030])
        self.assertEqual(eligibility.years_mentioned("Founded in 2021. We hire great people."), [])

    def test_lowes_style_list_includes_him(self):
        text = "Expected graduation dates of December 2028, May 2029, December 2029, or May 2030. 3.0 cumulative GPA or higher."
        verdict, note = eligibility.verdict_from_text(text, GRAD)
        self.assertEqual(verdict, "ok")
        self.assertIn("2030", note)

    def test_readable_boards(self):
        self.assertTrue(eligibility.is_readable_board("https://boards.greenhouse.io/acme/jobs/1"))
        self.assertTrue(eligibility.is_readable_board("https://jobs.lever.co/acme/abc"))
        self.assertTrue(eligibility.is_readable_board("https://jobs.ashbyhq.com/acme/abc"))
        self.assertTrue(eligibility.is_readable_board("https://acme.wd5.myworkdayjobs.com/en-US/Careers/job/NYC/SWE-Intern_R1"))
        self.assertTrue(eligibility.is_readable_board("https://www.google.com/about/careers/applications/jobs/results/123"))
        self.assertFalse(eligibility.is_readable_board("https://evil-greenhouse.io/x"))
        self.assertFalse(eligibility.is_readable_board("https://www.amazon.jobs/en/jobs/1"))

    def test_upperclass_phrases_are_ineligible(self):
        text = "This internship is intended for students in their penultimate academic year, pursuing a Bachelor's degree."
        verdict, note = eligibility.verdict_from_text(text, GRAD)
        self.assertEqual(verdict, "ineligible")
        self.assertIn("penultimate", note)
        self.assertEqual(eligibility.verdict_from_text("Open to rising juniors and seniors.", GRAD)[0], "ineligible")

    def test_explicit_years_beat_upperclass_words(self):
        text = "Expected graduation dates of December 2028, May 2029, December 2029, or May 2030. Final year students welcome."
        self.assertEqual(eligibility.verdict_from_text(text, GRAD)[0], "ok")

    def test_network_off_gives_unknown_without_fetching(self):
        item = {"url": "https://boards.greenhouse.io/acme/jobs/1"}
        eligibility.check(item, GRAD, cache={}, allow_network=False)
        self.assertEqual(item["eligibility"], "unknown")


if __name__ == "__main__":
    unittest.main()
