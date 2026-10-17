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

    def test_ambassador(self):
        self.assertEqual(matching.classify_role("Student Ambassador Program", T), "ambassador")
        self.assertEqual(matching.classify_role("Campus Ambassador - Marketing", T), "ambassador")
        self.assertEqual(matching.classify_role("GitHub Campus Expert", T), "ambassador")

    def test_design(self):
        self.assertEqual(matching.classify_role("UX Design Intern", T), "design")
        self.assertEqual(matching.classify_role("Product Design Intern", T), "design")

    def test_excluded(self):
        self.assertEqual(matching.classify_role("Business Intelligence Engineer Intern", T), "none")
        self.assertEqual(matching.classify_role("Data Engineer Intern", T), "none")
        self.assertEqual(matching.classify_role("Firmware Engineer Intern/Co-op", T), "none")
        self.assertEqual(matching.classify_role("Electronics Engineering Intern", T), "none")
        self.assertEqual(matching.classify_role("Consumer Electronics Software Engineer Intern", T), "swe")
        self.assertEqual(matching.classify_role("Mechanical Engineering Intern", T), "none")
        self.assertEqual(matching.classify_role("Quantitative Trading Intern", T), "none")
        self.assertEqual(matching.classify_role("Data Scientist Intern", T), "none")
        self.assertEqual(matching.classify_role("Hardware Engineer Intern", T), "none")


class EarlyCareer(unittest.TestCase):
    def test_fulltime_signals(self):
        self.assertEqual(matching.early_career("Junior Software Engineer", None, T), "weak")
        self.assertEqual(matching.early_career("Software Engineer", None, T), "none")

    def test_student_programs_receive_no_boost(self):
        for title in ("Microsoft Explore", "Google STEP", "NVIDIA Ignite", "Freshman/Sophomore Intern"):
            self.assertEqual(matching.early_career(title, "google", T), "none")


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
        item = {"active": True, "career_level": "entry_level", "terms": [], "degree_class": "bachelors", "role": "swe", "early_career": "none"}
        item.update(over)
        return item

    def test_keeps_normal(self):
        self.assertTrue(matching.passes_filters(self.base())[0])

    def test_drops(self):
        self.assertEqual(matching.passes_filters(self.base(active=False))[1], "inactive")
        self.assertEqual(matching.passes_filters(self.base(career_level="internship"))[1], "not a full-time early-career role")
        self.assertEqual(matching.passes_filters(self.base(degree_class="graduate_only"))[1], "graduate students only")
        self.assertEqual(matching.passes_filters(self.base(role="none"))[1], "not a target role")

    def test_program_does_not_rescue_unknown_role(self):
        self.assertFalse(matching.passes_filters(self.base(role="none", early_career="strong"))[0])

    def test_non_us_is_not_dropped(self):
        self.assertTrue(matching.passes_filters(self.base(location_class="other"))[0])

    def test_too_old_is_dropped(self):
        now = 1_800_000_000
        old = self.base(date_posted=now - 300 * 86400)
        self.assertEqual(matching.passes_filters(old, max_age_days=240, now=now)[1], "older than 240 days")
        recent = self.base(date_posted=now - 100 * 86400)
        self.assertTrue(matching.passes_filters(recent, max_age_days=240, now=now)[0])


class ReviewFixes(unittest.TestCase):
    """Cases from the October 2026 product review, all from real 2027 listings."""

    def kept(self, title, company="Acme", locations=("New York, NY",), url=""):
        item = matching.describe({"company": company, "title": title, "locations": list(locations), "url": url,
                                  "degrees": ["Bachelor's"], "terms": ["Summer 2027"], "active": True}, T)
        return matching.passes_filters(item)

    def test_hardware_is_out_even_inside_a_program(self):
        url = "Junior https://nvidia.wd5.myworkdayjobs.com/x/job/US-CA/NVIDIA-2027-Ignite-ships--Hardware-Engineering_JR1"
        self.assertEqual(self.kept("Junior Hardware Engineering ", "NVIDIA", url=url), (False, "not a target role"))
        url = "Junior https://nvidia.wd5.myworkdayjobs.com/x/job/US-CA/NVIDIA-2027-Ignite-ships--Software_JR2"
        self.assertTrue(self.kept("Junior Software Engineer ", "NVIDIA", url=url)[0])

    def test_software_in_the_title_beats_an_exclude_word(self):
        self.assertTrue(self.kept("Junior Privacy and Civil Liberties Software Engineer ", "Palantir")[0])
        self.assertTrue(self.kept("Junior Software Engineer , Trading Systems")[0])
        self.assertFalse(self.kept("Junior Quantitative Trading ")[0])

    def test_graduate_titles_drop_but_mixed_ones_stay(self):
        self.assertEqual(self.kept("Junior Software Engineering , Masters", "Apple")[1], "graduate students only")
        self.assertEqual(self.kept("Junior Product Owner  - MBA", "Waymo")[1], "graduate students only")
        self.assertEqual(self.kept("Junior Software Engineer  - MS/PhD", "Waymo")[1], "graduate students only")
        self.assertFalse(matching.graduate_title("Junior Scenes  (BS/MS)"))
        self.assertFalse(matching.graduate_title("Junior Software Engineer  (B.S./M.S.)"))

    def test_review_two_title_and_place_cases(self):
        self.assertFalse(self.kept("Junior Software Defined Radio Hardware ", "Astranis")[0])
        self.assertTrue(matching.graduate_title("Junior Design Engineer  - Graduate-Level"))
        self.assertTrue(matching.graduate_title("Junior Software Engineering , Master\u2019s"))
        self.assertTrue(matching.graduate_title("Junior Data Platform  - MS"))
        self.assertFalse(matching.graduate_title("Junior Microsoft Office Specialist "))
        for place in ("Indianapolis", "Arlington, VA, On-site", "Remote, Abilene"):
            self.assertFalse(matching.outside_us_only([place], T), place)
        self.assertTrue(matching.outside_us_only(["Toronto, ON"], T))
        self.assertTrue(matching.outside_us_only(["Waterloo, ON, Canada"], T))
        self.assertTrue(matching.outside_us_only(["Toronto, ON, CA"], T))
        self.assertEqual(matching.location_class(["Sunnyvale, CA"], T), "us")

    def test_electronics_design_is_not_ux(self):
        self.assertEqual(matching.classify_role("Junior Electronics Design Engineering  - Low Voltage", T), "none")
        self.assertEqual(matching.classify_role("Junior Electronic Design Engineer  - Energy Engineering", T), "none")
        self.assertEqual(matching.classify_role("Junior UI/UX Design ", T), "design")
        self.assertEqual(matching.classify_role("Junior Consumer Electronics Software Engineer ", T), "swe")

    def test_missing_role_words(self):
        self.assertEqual(matching.classify_role("Junior Application Development ", T), "swe")
        self.assertEqual(matching.classify_role("Junior Computer Science ", T), "swe")
        self.assertEqual(matching.classify_role("Junior Member of Technical Staff ", T), "swe")
        self.assertEqual(matching.classify_role("Junior IT Support Specialist", T), "it")

    def test_only_foreign_locations_drop(self):
        self.assertEqual(self.kept("Junior Software Developer ", "Amazon", locations=("London, UK", "Edinburgh, UK"))[1],
                         "outside the US")
        self.assertTrue(self.kept("Junior Software Engineer ", locations=("Toronto, ON, Canada", "Seattle, WA"))[0])
        self.assertTrue(self.kept("Junior Software Engineer ", locations=("Multiple Locations",))[0])

    def test_citizenship_only_drops_when_the_config_says_no(self):
        row = {"company": "Acme", "title": "Junior Software Engineer ", "locations": ["Arlington, VA"], "url": "",
               "degrees": [], "terms": ["Summer 2027"], "active": True, "sponsorship": "U.S. Citizenship is Required"}
        unknown = matching.describe(dict(row), dict(T, us_citizen=None))
        self.assertTrue(unknown["citizens_only"])
        self.assertTrue(matching.passes_filters(unknown)[0])
        no = matching.describe(dict(row), dict(T, us_citizen=False))
        self.assertEqual(matching.passes_filters(no), (False, "US citizens only"))
        yes = matching.describe(dict(row), dict(T, us_citizen=True))
        self.assertFalse(yes["citizens_only"])
        self.assertTrue(matching.passes_filters(yes)[0])

    def test_us_places_written_without_abbreviations(self):
        for place in ("Mountain View, California", "Georgia", "Washington, D.C.", "New Berlin, WI", "South SF", "San Jose"):
            self.assertEqual(matching.location_class([place], T), "us", place)


if __name__ == "__main__":
    unittest.main()
