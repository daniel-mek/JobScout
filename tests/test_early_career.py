"""Early-career ingestion through scoring, entirely offline."""

import unittest
from unittest import mock

from scout import boards, career, eligibility, listings, matching, scoring, watch


class EarlyCareer(unittest.TestCase):
    def test_title_levels(self):
        for title in ("Junior Software Developer", "Entry-Level IT Support Specialist", "New Grad Software Engineer",
                      "Security Analyst I", "Network Technician 1", "Associate Software Engineer"):
            self.assertEqual(career.level(title), "entry_level", title)
        for title in ("Senior Software Engineer", "Sr. IT Support Specialist", "Staff Software Engineer",
                      "Junior Software Engineer II", "Head of Early Career Recruiting"):
            self.assertEqual(career.level(title), "experienced", title)
        self.assertEqual(career.level("Software Engineer"), "unknown")
        self.assertEqual(career.level("Member of Technical Staff Intern"), "internship")

    def test_boards_collect_fulltime_without_fake_summer_term(self):
        gh = {"jobs": [{"id": 1, "title": "Junior IT Support Specialist", "absolute_url": "https://boards.greenhouse.io/acme/jobs/1"}]}
        ash = {"jobs": [{"id": "a", "title": "New Grad Software Engineer", "isListed": True},
                        {"id": "hidden", "title": "Junior Developer", "isListed": False}]}
        lev = [{"id": "l", "text": "Entry-Level Security Analyst", "hostedUrl": "https://jobs.lever.co/acme/l"}]
        rows = (boards.greenhouse("acme", "Acme", fetch=lambda _: gh) +
                boards.ashby("acme", "Acme", fetch=lambda _: ash) +
                boards.lever("acme", "Acme", fetch=lambda _: lev))
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertEqual(row["career_level"], "entry_level")
            self.assertEqual(row["terms"], [])
            self.assertTrue(matching.passes_filters(matching.describe(row, matching.load_targets()))[0])

    def test_newgrad_feed_and_role_scope_in_pipeline(self):
        titles = ["Software Engineer", "Junior IT Support Specialist", "Entry Level Accountant", "Senior Software Engineer"]
        raw = {"simplify_newgrad": [dict(id=str(i), company_name="Acme", title=t, active=True,
                url=f"https://example.com/jobs/{i}", locations=["New York, NY"]) for i, t in enumerate(titles)]}
        matches, _ = watch.run(raw, matching.load_targets(), scoring.load_weights(), allow_network=False, save=False)
        self.assertEqual({m["title"] for m in matches}, set(titles[:2]))
        self.assertTrue(all(m["source"] == "simplify_newgrad" for m in matches))

    def test_fulltime_still_respects_inactive_and_stale_filters(self):
        row = listings.normalize_newgrad(dict(company_name="Acme", title="Software Engineer", active=False))
        row = matching.describe(row, matching.load_targets())
        self.assertEqual(matching.passes_filters(row)[1], "inactive")
        row.update(active=True, date_posted=1)
        self.assertFalse(matching.passes_filters(row, max_age_days=90, now=10000000)[0])

    def test_one_source_failure_keeps_other_results(self):
        def fetch(url):
            if url == "bad":
                raise listings.SourceError("unavailable")
            return [{"company_name": "Acme"}]
        with mock.patch.object(listings, "fetch_json", side_effect=fetch):
            raw, errors = listings.fetch_all({"simplify": "bad", "simplify_newgrad": "good"}, with_boards=False)
        self.assertEqual(list(raw), ["simplify_newgrad"])
        self.assertEqual(len(errors), 1)

    def test_fulltime_is_not_rejected_using_internship_graduation_rules(self):
        item = {"url": "https://example.com/job", "career_level": "entry_level"}
        with mock.patch.object(eligibility, "is_readable_board", return_value=True), \
             mock.patch.object(eligibility, "fetch_text", return_value="Graduating in 2027. Open to juniors and seniors."):
            eligibility.check(item, {})
        self.assertEqual(item["eligibility"], "unknown")

    def test_closed_fulltime_is_still_detected(self):
        item = {"url": "https://example.com/job", "career_level": "entry_level"}
        with mock.patch.object(eligibility, "is_readable_board", return_value=True), \
             mock.patch.object(eligibility, "fetch_text", return_value=eligibility.CLOSED):
            eligibility.check(item, {})
        self.assertEqual(item["eligibility"], "closed")

    def test_only_fulltime_sources_enabled(self):
        self.assertEqual(set(listings.SOURCES), {"simplify_newgrad"})

    def test_internships_in_newgrad_feed_are_rejected(self):
        titles = ["Junior Software Engineer Intern", "IT Co-op", "IT Co op", "Software Engineering Fellowship", "Freshman Software Engineer Program"]
        raw = {"simplify_newgrad": [dict(company_name="Acme", title=t, active=True,
               url=f"https://example.com/{i}") for i, t in enumerate(titles)]}
        matches, counts = watch.run(raw, matching.load_targets(), scoring.load_weights(), allow_network=False, save=False)
        self.assertEqual(matches, [])
        self.assertEqual(counts["dropped: not a full-time early-career role"], len(titles))
