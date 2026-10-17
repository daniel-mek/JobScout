# Early-career IT and CS search

This fork collects job postings from public JSON feeds. It does not log into LinkedIn,
Indeed, or other protected job sites.

## Sources and matching

- `simplify_newgrad`: https://github.com/SimplifyJobs/New-Grad-Positions, using
  `dev/.github/scripts/listings.json`. Normalized using the existing Simplify schema.
  This curated feed can identify a graduate job even when its title only says Software Engineer.
- Internship feeds and student-program page watches are disabled.
- Greenhouse, Lever, and Ashby boards in `config/targets.yaml` now collect explicit junior,
  entry-level, associate, new-graduate, and level-I titles. Add employer slugs
  to the existing `boards` mappings to expand coverage.

`search_roles: [it, swe]` restricts matches to IT and CS role families. IT includes support,
networking, systems, cloud, and cybersecurity roles; CS includes software and application
development. IT and software receive equal role points. The existing role exclusions still
apply, including hardware, quantitative trading, and pure data-science roles.

Senior, staff, principal, lead, management, and level-II-or-higher titles are excluded.
Titles are signals, not proof of eligibility: descriptions may require more experience.
Unlabeled company-board jobs are omitted unless they come from the curated new-grad feed.
Only full-time entry-level jobs are retained. Internships, co-ops, fellowships, and student programs are excluded, including ones appearing in the graduate feed. No internship season or cycle year is assigned. Inactive, stale, foreign-only, and
graduate-student-only filters remain in place. One failed source reports an error while
other sources continue; the existing URL deduplication and application tracker still apply.

## Personalize and run

1. Graduation-year and class-standing checks have been removed. Closed posting checks still run.
   An available page is labeled unknown eligibility: review its skills, experience, and work authorization requirements.
   Old cached graduation verdicts are invalidated.
2. Set `us_citizen` to `true` or `false` after confirming it. `null` keeps citizenship-restricted
   jobs with a label. Location preferences currently favor New Jersey, NYC, and US remote.
3. Install dependencies: `python -m pip install -r requirements.txt`.
4. Preview collection: `python -m scout.watch --no-pages --top 30 --out /tmp/jobscout-matches.json`.
5. Run offline tests: `python -m unittest discover -s tests -t .`.
6. Enable GitHub Actions on the fork. The existing `scout` workflow runs hourly and can be
   started with **Actions > scout > Run workflow**. It now initializes the missing `data`
   branch on a fresh fork. Set `NTFY_TOPIC` for the normal persisted watcher; without it,
   `scout.run` retains the existing dry-run behavior. `SCOUT_URL` and `SCOUT_INGEST_SECRET`
   are needed only for dashboard sync. See [operations](operations.md).

No API keys are needed for these job feeds. Source availability and schemas can change;
source failures appear in the watcher output. Live collection requires outbound network access.
