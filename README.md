# JobScout

The supplied ApplyOS specification is now preserved in this repository. The existing watcher/dashboard remains in place. Phase 1 adds accounts, resume upload/review, persisted onboarding and preferences in a separate Next.js/FastAPI application. Start with the [Phase 1 setup guide](docs/PHASE1.md); see [implementation status](docs/IMPLEMENTATION_STATUS.md) for verification limits.

## Phase 1 application

Run the new app using [docs/PHASE1.md](docs/PHASE1.md). It includes PostgreSQL migrations, private resume versions, conservative offline parsing, profile review, career paths and separate preferences/hard requirements. The new account dashboard does not yet connect the legacy watcher or migrate legacy application history. No fake job metrics are shown.

## Phase 2 jobs and sources

Open `/jobs` to import jobs, connect employer boards, inspect policies/health, run saved source searches, and review provenance/version history. See [Phase 2 setup and verification](docs/PHASE2.md). External ingestion stays off until policy and board review are recorded. Matching comes in Phase 3; hosting is paused.

## Product documentation

Phase 4 adds Discover filters/views, saved jobs with notes/deadlines, reversible feedback, saved filter searches, daily briefs and in-app notifications. See [Phase 4 behavior and verification](docs/PHASE4.md). Matching refreshes through the existing worker or an explicit job calculation; hosting remains paused.

Phase 3 adds explainable Resume Match/Application Priority scores, eligibility warnings, confirmed-evidence comparisons, editable scoring weights and background recalculation. See [matching setup and verification](docs/PHASE3.md). Ambiguous facts remain unknown; no application is submitted automatically.

- [Product specification](docs/PRODUCT_SPEC.md)
- [Architecture and reuse plan](docs/ARCHITECTURE.md)
- [Source policy](docs/SOURCE_POLICY.md)
- [Security and privacy](docs/SECURITY.md)
- [Implementation status](docs/IMPLEMENTATION_STATUS.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Operations](docs/OPERATIONS.md)
- [Claude Code instructions](CLAUDE.md)

## Existing application

This fork searches early-career IT and computer science jobs: junior, entry-level, and new-graduate full-time roles. It reads the public Simplify new-graduate feed and configured Greenhouse, Lever, and Ashby company boards. See [early-career setup](docs/early-career.md).

**🚧 In development.** It runs every day for a full-time early-career IT and CS search; making it work for anyone is the next step ([where this is going](#where-this-is-going)).

<img src="docs/mac-new.png" alt="Scout dashboard on a Mac: the New page with open matches and a grid of scored job cards">

<p align="center">
  <img src="docs/phone-new.png" width="30%" alt="Scout on a phone: New page with the match count and the top scored posting">
  <img src="docs/phone-about.png" width="30%" alt="Scout on a phone: the what is scout page explaining find, score, alert, prep, and track">
</p>

Scout is an early-career job radar. About every hour it reads the public new-graduate feed and the job boards of the companies you care about most, scores each posting against what you're looking for, and pushes an alert to your phone when a strong match drops. For any posting you pick, it builds a prep kit: a one-page tailored resume, a cover letter if the posting wants one, and draft answers, all from facts you've already confirmed. The public [what is scout?](https://scout-dashboard.jeremysleman.workers.dev/about) page explains it in five steps.

**You always click Submit yourself.** Scout never submits an application, never logs into a job site, never creates accounts, and never solves captchas. It finds, ranks, alerts, and preps.

It costs $0 a month: GitHub Actions (free for public repos), Cloudflare Workers and KV on the free tier, and [ntfy](https://ntfy.sh) for push notifications. The AI parts run inside a Claude Code session you start, so there are no API bills.

## How it works

```
GitHub Actions, every hour              Your Mac, on demand (Claude Code)
  fetch -> normalize -> dedupe             /triage   -> which new matches are worth a kit
  -> filter -> score (0 to 100)            /prep     -> tailored resume, letter, answers
  -> ntfy push (instant / 7 PM digest)     /status   -> move it through the tracker
  -> state saved to the "data" branch
            |
            v
Cloudflare Worker: password-protected dashboard (New, Early career, Tracker, Settings) + KV
```

- **Scoring without AI.** Every posting gets a 0 to 100 score from plain rules in `config/scoring.yaml`: role, company tier, early-career title signals, degree, location, and freshness. Every card shows its math.
- **Posting availability.** Scout checks supported posting pages and labels closed jobs. Personal eligibility stays unknown until you review the requirements.
- **Full-time early-career search.** Internship feeds, freshman programs, and student-program watches are disabled.
- **Prep kits with a second pair of eyes.** A drafter writes from your master profile only; a separate reviewer pass checks every claim against it, plus the posting's must-haves, and lists what you don't have instead of faking it.

## Tech

- **Python 3.12** watcher: `scout/` (listings, matching, scoring, dedupe, eligibility, page watchers, alerts, sync). Standard library plus PyYAML.
- **GitHub Actions** cron and tests (`.github/workflows/`), state committed to a separate `data` branch so `main` holds only code.
- **Cloudflare Worker + KV** dashboard: `worker/src/index.js`, server-rendered pages, HMAC-signed login cookie, every color and size in `worker/src/tokens.css`.
- **HTML + WeasyPrint** for one-page, ATS-checked resume and letter PDFs.
- **Claude Code** for `/triage`, `/prep`, `/interview`, and `/status` (`.claude/commands/`).
- **Tests:** about 150 unit tests on saved fixtures, no network. `python -m unittest discover -s tests -t .`

## Where this is going

The plan is for Scout to work for anyone looking for an internship or a job, whatever their major or career. Already general: scoring and filtering are driven by `config/targets.yaml` and `config/scoring.yaml`, the prep kit works from any master profile, and the dashboard and alerts don't care what the postings are. Current sources: the Simplify new-graduate list and Greenhouse, Lever, and Ashby boards. Next: sources for more fields (starting with the Greenhouse, Lever, and Ashby board APIs, which cover companies in every industry), then a setup command that asks what you're looking for and writes the config for you.

## Make it yours

1. Clone, create a Python 3.12 venv, `pip install -r requirements.txt` (add `requirements-resume.txt` for PDFs).
2. Edit `config/targets.yaml`: roles and the words that identify them, companies by tier, locations, keywords, graduation year, and `us_citizen`.
3. Copy `me.example/` to `me/` (gitignored) and fill in your master profile, then run `/interview` in Claude Code to build your resumes.
4. Set the repo secrets (`NTFY_TOPIC`; plus `SCOUT_URL` and `SCOUT_INGEST_SECRET` if you deploy the dashboard) and enable the workflow.

How every piece runs, with commands: [docs/OPERATIONS.md](docs/OPERATIONS.md). Design decisions and why: [docs/decisions.md](docs/decisions.md). Code borrowed from MIT and Apache projects is listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

I built it with help from Claude Code. MIT license.

