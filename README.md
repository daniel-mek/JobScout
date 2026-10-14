# Scout

**Status: M0, setup.** Nothing runs yet. See the [milestones](#milestones).

Scout is a personal internship radar. Every few hours it reads the public internship lists, scores each posting against what I'm looking for, and pushes an alert to my phone when a strong match drops. For any posting I pick, it builds a prep kit: a one-page tailored resume, a cover letter if the posting wants one, and draft answers to the usual questions, all in my own voice and all from facts in my master resume.

**I always click Submit myself.** Scout never submits an application, never logs into a job site, never creates accounts, and never solves captchas. It finds, ranks, alerts, and preps. That's it.

It is built for one person (me) and costs $0 a month: GitHub Actions, Cloudflare Workers and KV on the free tier, and [ntfy](https://ntfy.sh) for push notifications. Anything that needs AI runs inside a Claude Code session that I start, so there are no API bills.

## How it works

```
GitHub Actions (cron, free)          My Mac (Claude Code, on demand)
  fetch -> normalize -> dedupe          /prep <id>    -> prep kit
  -> filter -> score -> data/*.json     /triage       -> AI read of new matches
  -> ntfy push (instant / digest)       /interview    -> build or update master resume
  -> commit data/                       /status <id> <state>
            |
            v
Cloudflare Worker (free): password-protected dashboard + KV for tracker updates from my phone
```

- **Watcher (Python 3.12, no AI):** pulls the [Simplify + Pitt CSC list](https://github.com/SimplifyJobs/Summer2027-Internships) and other free sources, normalizes them into one shape, drops anything already seen, filters out roles I'm not eligible for, and scores the rest 0 to 100. Weights live in `config/scoring.yaml` with a comment on each one, and every match shows its score breakdown so I can see why.
- **Alerts (ntfy):** Tier 1 and Tier 2 companies, early-career programs, and watched program pages push instantly. Everything else goes into one daily digest at 7:00 PM ET. Messages carry company, role, location, score, and link. Nothing personal.
- **Prep kit (Claude Code):** a drafter writes, then a reviewer pass checks every claim against the master resume, the voice rules, and the posting's must-haves. I see the reviewer's flags before anything is final.
- **Tracker and dashboard (Cloudflare Worker + KV):** Found, Saved, Prepped, Applied, OA, Interview, Offer or Rejected or Withdrawn. Updatable from my phone.

## Folder layout

```
scout/
  CLAUDE.md            the brief and the rules Claude Code works from
  config/              targets.yaml, scoring.yaml, watch-pages.yaml (edit these, not code)
  scout/               the Python watcher
  tests/               unit tests on saved fixture JSON, no network
  data/                matches.json, seen.json, tracker.json (committed by the cron)
  me/                  master resume, voice rules, answers bank   (gitignored)
  applications/        one folder per prep kit                     (gitignored)
  docs/                reference notes and reports
  .claude/commands/    /interview, /triage, /prep, /status
```

`me/` and `applications/` never reach git. Secrets (the ntfy topic, the dashboard password) live only in GitHub Actions secrets and Wrangler secrets.

## Cost

GitHub gives a private repo 2,000 free Actions minutes a month. The watcher runs every 3 hours plus one digest run a day, and each run should finish in about a minute (checkout, Python setup, fetch one JSON file, score, commit).

| Job | Runs per month | Minutes per run | Minutes per month |
|---|---|---|---|
| Watcher (every 3 hours) | 240 | about 1 | about 240 |
| Daily digest (7:00 PM ET) | 30 | about 1 | about 30 |
| **Total** | | | **about 270 of 2,000** |

Cloudflare Workers free tier: 100,000 requests a day. ntfy: free. If any of this starts costing money, it gets turned off.

## Milestones

| Milestone | Status | What it delivers |
|---|---|---|
| M0: setup | In progress | Repo, folder structure, .gitignore, README, reference research ([report](docs/reference-report.md)) |
| M1: master resume | Not started | `/interview` builds `me/master-resume.md`, voice rules, answers bank, then three one-page PDFs (SWE, PM, IT) |
| M2: watcher | Not started | Fetch, normalize, dedupe, filter, score. Top 20 with breakdowns, tuned by hand. Tests on fixtures |
| M3: alerts | Not started | ntfy instant push and 7:00 PM digest, program page watchers, GitHub Actions cron |
| M4: prep kit | Not started | `/prep`, `/triage`, drafter then reviewer, PDFs via HTML + WeasyPrint |
| M5: dashboard + tracker | Not started | Cloudflare Worker, KV, password, mobile layout, prep queue |
| M6: optional | Not started | Greenhouse, Lever, Ashby boards for Tier 2 companies |

## Borrowed code

Scout borrows small, readable pieces from MIT and Apache licensed projects rather than pulling in frameworks. Every borrowed file is listed with its license in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Built with

Python 3.12, GitHub Actions, ntfy, Cloudflare Workers and KV, HTML + WeasyPrint for PDFs, and Claude Code as the pair programmer for the parts that need AI.
