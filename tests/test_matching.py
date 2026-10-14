"""Unit tests for matching.py: tier, role, early-career, location, degrees. No network."""

import unittest

from scout import matching

T = matching.load_targets()


class CompanyTier(unittest.TestCase):
    def test_tier1_aliases(self):
        self.assertEqual(matching.company_tier("Google LLC", T), (1, "google"))
        self.assertEqual(matching.company_tier("Google DeepMind", T), (1, "google"))
        self.assertEqual(matching.company_tier("Amazon Web Services", T), (1, "amazon"))
        self.assertEqual(matching.company_tier("NVIDIA", T), (1, "nvidia"))

    def test_tier2(self):
        self.assertEqual(matching.company_tier("Snap Inc.", T), (2, "snap"))
        self.assertEqual(matching.company_tier("Bloomberg L.P.", T), (2, "bloomberg"))

    def test_whole_name_only(self):
        self.assertEqual(matching.company_tier("Metagenomics Corp", T)[0], 3)
        self.assertEqual(matching.company_tier("Snapple", T)[0], 3)
        self.assertEqual(matching.company_tier("Pineapple Labs", T)[0], 3)
        self.assertEqual(matching.company_tier("Apple Bank", T)[0], 3)
        self.assertEqual(matching.company_tier("Meta Marketing Group", T)[0], 3)

    def test_corporate_suffixes_ignored(self):
        self.assertEqual(matching.company_tier("Apple Inc.", T), (1, "apple"))
        self.assertEqual(matching.company_tier("NVIDIA Corporation", T), (1, "nvidia"))
        self.assertEqual(matching.company_tier("Meta Platforms, Inc.", T), (1, "meta"))

    def test_unknown_company_is_tier3(self):
        self.assertEqual(matching.company_tier("Some Startup", T), (3, None))


class Role(unittest.TestCase):
    def test_swe(self):
        self.assertEqual(matching.classify_role("Software Engineering Intern, Summer 2027", T), "swe")
        self.assertEqual(matching.classify_role("SWE Intern", T), "swe")
        self.assertEqual(matching.classify_role("iOS Developer Intern", T), "swe")

    def test_pm(self):
        self.assertEqual(matching.classify_role("Product Management Intern", T), "pm")
        self.assertEqual(matching.classify_role("APM Intern", T), "pm")

    def test_it(self):
        self.assertEqual(matching.classify_role("IT Intern - Summer 2027", T), "it")
        self.assertEqual(matching.classify_role("Information Technology Intern", T), "it")

    def test_it_does_not_match_inside_words(self):
        # "Pittsburgh" and "Security" contain "it" but are not IT jobs on their own
        self.assertNotEqual(matching.classify_role("Marketing Intern (Pittsburgh)", T), "it")

    def test_design(self):
        self.assertEqual(matching.classify_role("UX Design Intern", T), "design")
        self.assertEqual(matching.classify_role("Product Design Intern", T), "design")

    def test_excluded(self):
        self.assertEqual(matching.classify_role("Business Intelligence Engineer Intern", T), "none")
        self.assertEqual(matching.classify_role("Data Engineer Intern", T), "none")
        self.assertEqual(matching.classify_role("Firmware Engineer Intern/Co-op", T), "none")
        self.assertEqual(matching.classify_role("Mechanical Engineering Intern", T), "none")
        self.assertEqual(matching.classify_role("Quantitative Trading Intern", T), "none")
        self.assertEqual(matching.classify_role("Data Scientist Intern", T), "none")
        self.assertEqual(matching.classify_role("Hardware Engineer Intern", T), "none")


class EarlyCareer(unittest.TestCase):
    def test_strong_words(self):
        self.assertEqual(matching.early_career("Software Engineering Intern (Freshman/Sophomore)", None, T), "strong")
        self.assertEqual(matching.early_career("Early Insights Program", None, T), "strong")

    def test_named_programs(self):
        self.assertEqual(matching.early_career("Explore Internship", "microsoft", T), "strong")
        self.assertEqual(matching.early_career("2027 Ignite Internships, Software Engineering", "nvidia", T), "strong")
        self.assertEqual(matching.early_career("STEP Intern", "google", T), "strong")

    def test_program_word_in_url(self):
        url = "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/US-CA-Santa-Clara/NVIDIA-2027-Ignite-Internships--Software-Engineering_JR2026958"
        self.assertEqual(matching.early_career("Software Engineer Intern", "nvidia", T, url), "strong")
        self.assertEqual(matching.early_career("Software Engineer Intern", "nvidia", T, "https://nvidia.wd5.myworkdayjobs.com/x/Software-Engineering_JR1"), "none")

    def test_weak(self):
        self.assertEqual(matching.early_career("Early Career Intern - Technology", "invesco", T), "weak")

    def test_none(self):
        self.assertEqual(matching.early_career("Software Engineer Intern", None, T), "none")


class Location(unittest.TestCase):
    def test_priority(self):
        self.assertEqual(matching.location_class(["Newark, NJ"], T), "priority")
        self.assertEqual(matching.location_class(["NYC"], T), "priority")
        self.assertEqual(matching.location_class(["New York, NY"], T), "priority")
        self.assertEqual(matching.location_class(["Remote in USA"], T), "priority")
        self.assertEqual(matching.location_class(["Remote"], T), "priority")

    def test_us(self):
        self.assertEqual(matching.location_class(["San Jose, CA"], T), "us")
        self.assertEqual(matching.location_class(["SF"], T), "us")
        self.assertEqual(matching.location_class(["United States"], T), "us")

    def test_other(self):
        self.assertEqual(matching.location_class(["London, UK"], T), "other")
        self.assertEqual(matching.location_class(["Toronto, ON, Canada"], T), "other")
        self.assertEqual(matching.location_class(["Remote in Canada"], T), "other")

    def test_best_of_many(self):
        self.assertEqual(matching.location_class(["London, UK", "Austin, TX", "NYC"], T), "priority")
        self.assertEqual(matching.location_class(["London, UK", "Austin, TX"], T), "us")

    def test_unknown(self):
        self.assertEqual(matching.location_class([], T), "unknown")


class Degrees(unittest.TestCase):
    def test_graduate_only(self):
        self.assertEqual(matching.degree_class(["Master's", "PhD"], T), "graduate_only")
        self.assertEqual(matching.degree_class(["PhD"], T), "graduate_only")

    def test_bachelors(self):
        self.assertEqual(matching.degree_class(["Bachelor's", "Master's"], T), "bachelors")
        self.assertEqual(matching.degree_class(["Bachelor's"], T), "bachelors")

    def test_unknown(self):
        self.assertEqual(matching.degree_class([], T), "unknown")


class Filters(unittest.TestCase):
    def base(self, **over):
        item = {"active": True, "terms": ["Summer 2027"], "degree_class": "bachelors", "role": "swe", "early_career": "none"}
        item.update(over)
        return item

    def test_keeps_normal(self):
        self.assertTrue(matching.passes_filters(self.base())[0])

    def test_drops(self):
        self.assertEqual(matching.passes_filters(self.base(active=False))[1], "inactive")
        self.assertEqual(matching.passes_filters(self.base(terms=["Summer 2026"]))[1], "not a 2027 term")
        self.assertEqual(matching.passes_filters(self.base(degree_class="graduate_only"))[1], "graduate students only")
        self.assertEqual(matching.passes_filters(self.base(role="none"))[1], "not a target role")

    def test_program_rescues_unknown_role(self):
        self.assertTrue(matching.passes_filters(self.base(role="none", early_career="strong"))[0])

    def test_non_us_is_not_dropped(self):
        self.assertTrue(matching.passes_filters(self.base(location_class="other"))[0])

    def test_too_old_is_dropped(self):
        now = 1_800_000_000
        old = self.base(date_posted=now - 300 * 86400)
        self.assertEqual(matching.passes_filters(old, max_age_days=240, now=now)[1], "older than 240 days")
        recent = self.base(date_posted=now - 100 * 86400)
        self.assertTrue(matching.passes_filters(recent, max_age_days=240, now=now)[0])


if __name__ == "__main__":
    unittest.main()
