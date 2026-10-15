# Scout

**🚧 In development.** It runs for me every day, but it is built around one person's targets so far. See the [milestones](#milestones) and [where this is going](#where-this-is-going).

<img src="docs/mac-new.png" alt="Scout dashboard on a Mac: the New page with 299 open matches and a grid of scored internship cards">

<p align="center">
  <img src="docs/phone-new.png" width="30%" alt="Scout on a phone: New page with the match count and the top scored posting">
  <img src="docs/phone-programs.png" width="30%" alt="Scout on a phone: Programs page listing the watched freshman program pages">
  <img src="docs/phone-about.png" width="30%" alt="Scout on a phone: the what is scout page explaining find, score, alert, prep, and track">
</p>

Scout is a personal internship radar. The dashboard's public [what is scout?](https://scout-dashboard.jeremysleman.workers.dev/about) page explains it in five steps. Every few hours it reads the public internship lists, scores each posting against what I'm looking for, and pushes an alert to my phone when a strong match drops. For any posting I pick, it builds a prep kit: a one-page tailored resume, a cover letter if the posting wants one, and draft answers to the usual questions, all in my own voice and all from facts in my master resume.

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
  scout/               the Python code: build_resume.py now, the watcher in M2
  scout/templates/     resume.html, the one-column ATS-safe layout (no personal data)
  tests/               unit tests on saved fixture JSON, no network
  data/                matches.json, seen.json, tracker.json (committed by the cron)
  me/                  master resume, voice rules, answers bank   (gitignored)
  applications/        one folder per prep kit                     (gitignored)
  docs/                reference notes and reports
  .claude/commands/    /interview, /triage, /prep, /status
```

`me/` and `applications/` never reach git. Secrets (the ntfy topic, the dashboard password) live only in GitHub Actions secrets and Wrangler secrets.

## Cost

$0. The repo is public, and GitHub Actions minutes are free and unlimited for public repos. The watcher runs about 22 times a day and each run takes about a minute. If the repo ever goes private again, that is roughly 660 minutes a month, still inside the 2,000 free minutes a private repo gets. Cloudflare Workers and KV run on the free tier (100,000 requests a day), and ntfy is free.

Cloudflare Workers free tier: 100,000 requests a day. ntfy: free. If any of this starts costing money, it gets turned off.

## Milestones

| Milestone | Status | What it delivers |
|---|---|---|
| M0: setup | Done | Repo, folder structure, .gitignore, README, reference research ([report](docs/reference-report.md)) |
| M1: master resume | In progress | `me/master_profile.md` is ground truth, `me/voice.md` holds the voice rules, `me/answer_bank.md` the approved answers. `scout/build_resume.py` turns one JSON file per variant into a one-page PDF and checks the text layer. Three variants built (SWE, PM, IT); a few dates still to confirm |
| M2: watcher | Done | `python -m scout.watch` fetches both lists, normalizes, dedupes, filters, scores, and writes `data/matches.json`. Every match prints its score breakdown. Freshman/sophomore programs and ambassador roles rank highest |
| M3: alerts | Done | `python -m scout.run` sends instant ntfy pushes, the 7:00 PM ET digest, and page-change alerts for nine program pages (`config/watch-pages.yaml`). `.github/workflows/scout.yml` runs it every hour and commits `data/` back |
| M4: prep kit | Done | `/prep <key>` reads the posting (`scout/posting.py`: Workday, Google Careers, Greenhouse, Lever, Ashby), checks eligibility, drafts a tailored resume, cover letter, answers, and notes from the master profile, runs a reviewer agent that checks every claim, builds the PDFs, and logs the tracker. `/triage` picks the postings worth a kit. `/status` moves the tracker. 86 tests |
| M5: dashboard + tracker | Done | `worker/` is one Cloudflare Worker with one KV namespace: New (matches with score breakdowns, "Prep this" and "Pass"), Programs (watched pages and early-career finds), Tracker (state and next action, editable from the phone), Settings (read-only config). Password login with a signed cookie. The cron pushes each run up and pulls phone changes down (`scout/sync.py`) |
| M6: optional | Not started | Greenhouse, Lever, Ashby boards for Tier 2 companies |

## Where this is going

The plan is for Scout to work for anyone looking for jobs or internships, whatever their major or career, not just a CS student looking at tech. The pieces that are already general: the scoring is driven entirely by `config/targets.yaml` and `config/scoring.yaml` (roles, companies, locations, keywords, weights, all editable without code), the prep kit works from any master profile, and the dashboard and alerts don't care what the postings are. The pieces that are still tech-specific: the two data sources are tech internship lists, and the posting reader knows a handful of job boards. The next step is adding sources per field (and the Greenhouse, Lever, and Ashby board APIs, which cover companies in every industry), then a setup command that asks what you're looking for and writes the config for you.

## Make it yours (today)

1. Fork or clone, create a venv, `pip install -r requirements.txt`.
2. Edit `config/targets.yaml`: your target roles and the words that identify them, your companies by tier, your locations, your keywords, your graduation year.
3. Put your own facts in `me/master_profile.md` (the folder is gitignored; see `me/README.md` for the layout) and run `/interview` in Claude Code to build your resumes.
4. Set the secrets (`NTFY_TOPIC` for alerts; `SCOUT_URL` and `SCOUT_INGEST_SECRET` if you deploy the dashboard) and enable the workflow.

## Borrowed code

Scout borrows small, readable pieces from MIT and Apache licensed projects rather than pulling in frameworks. Every borrowed file is listed with its license in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Running the watcher

```bash
.venv/bin/python -m scout.watch                      # fetch both lists, print the top 20, write data/matches.json
.venv/bin/python -m scout.watch --top 50 --no-pages  # more rows, skip the graduation-year page check
.venv/bin/python -m scout.watch --offline tests/fixtures   # saved copies only, no network
.venv/bin/python -m unittest discover -s tests -t .  # the tests
```

Pipeline, in order: `scout/listings.py` fetches the Simplify and vanshb03 JSON files and turns every row into one shape; `scout/matching.py` reads `config/targets.yaml` to decide company tier, role, location, freshman-friendliness, and degree requirement; hard drops are inactive rows, non-2027 terms, graduate-only degrees, non-target roles, and postings older than 240 days; `scout/dedupe.py` collapses the same posting across both lists; `scout/scoring.py` applies `config/scoring.yaml` and keeps the breakdown; `scout/eligibility.py` fetches the top 40 posting pages on Greenhouse, Lever, and Ashby and reads them for a graduation-year requirement (cached 14 days in `data/eligibility_cache.json`). Nothing is hidden for location; it only changes the score.

Each match looks like this on the command line:

```
 1. [ 75] Google  |  Forward Deployed Engineer Intern
      NYC, Sunnyvale, CA  |  posted 2d  |  unknown: not checked (not a plain-HTML board)
      role swe 30 + tier 1 20 + early none 0 + deg 5 + loc priority 15 + fresh 5 + kw 0 = 75
      https://www.google.com/about/careers/applications/jobs/results/...
```

## Alerts and the cron

```bash
export NTFY_TOPIC="$(cat me/ntfy-topic.txt)"          # the secret topic; also stored as a GitHub Actions secret
.venv/bin/python -m scout.run --mode test             # one test push
.venv/bin/python -m scout.run --mode watch --dry-run  # what a run would push, without sending
.venv/bin/python -m scout.run --mode watch --seed     # first run only: mark today's matches as seen
.venv/bin/python -m scout.run --mode digest --force   # send the digest now instead of at 7:00 PM
```

- **Instant push:** a Tier 1 or Tier 2 posting scoring at least 60, any freshman/sophomore program, any ambassador program, or a watched page that changed. Priority is higher for programs.
- **Daily digest at 7:00 PM ET:** the top 10 new matches that did not push instantly, with links.
- **Page watchers:** each page in `config/watch-pages.yaml` is fetched, stripped to text with volatile tokens removed, and hashed. A change pushes the first new lines. A page that can't be read two runs in a row, or that serves no text, pushes a warning once. Baselines live in `data/pages/`.
- **Nothing twice:** `data/seen.json` holds every key that was ever pushed or digested.
- **Failing loudly:** if a source list can't be fetched, one push says so.
- **Schedule:** every hour at :17, except the two hours around the 6:45 AM Morning Brief. GitHub runs scheduled jobs late or skips them when it is busy, so the schedule is hourly and the digest is not a schedule of its own: every run checks whether it is after 7:00 PM in New York and today's digest has not gone out yet (`data/digest.json`).
- **Rotating content is ignored:** program pages that show a carousel of the latest job postings (Microsoft's do) have those cards stripped before comparing, so a page only counts as changed when its own text changes.

## Prep kits

Inside Claude Code: `/triage` reads the newest matches and recommends three or four; `/prep <key>` builds `applications/<company>-<role>/` with `resume.json` and its PDF, `cover-letter.md` and its PDF when the posting wants one, `answers.md`, `notes.md`, `posting.txt`, and `match.json`. A drafter writes from `me/master_profile.md` only; a separate reviewer agent then checks every claim against the profile, the voice rules, and the posting's must-haves, and its flags go into `notes.md`. `/status <key> Applied` logs the submission, which I always do by hand.

```bash
.venv/bin/python -m scout.posting "<url>"                 # read a posting as text (Workday included)
.venv/bin/python scout/build_letter.py applications/<folder>/cover-letter.md
.venv/bin/python -m scout.tracker list
```

## Dashboard

```
GitHub Actions run ──push──▶  scout-dashboard Worker + KV  ◀──taps── phone (New, Programs, Tracker, Settings)
GitHub Actions run ◀──pull──  tracker, prep queue, passed keys  ──▶  data/tracker.json, data/queue.json, data/passed.json
```

- `worker/src/index.js` is the whole app: routing, the password login (HMAC-signed cookie, 30 days), the four pages rendered on the server, and a few JSON endpoints for the buttons. `worker/src/tokens.css` holds every color and size, so a redesign touches one file.
- `scout/sync.py push` sends `data/matches.json` (with each match's first-seen time), `data/pages.json`, `data/tracker.json`, and the config files to `/api/ingest` with a secret header. `scout/sync.py pull` fetches `/api/export` and writes the tracker, queue, and passed keys into `data/`. The cron does pull, run, push, commit.
- "Prep this" adds a posting to a queue that `/prep` (with no arguments) reads next time I open Claude Code. "Pass" hides it from New. Tracker edits from the phone win over older repo edits by date.
- Worker secrets: `DASH_PASSWORD`, `SESSION_SECRET`, `INGEST_SECRET`. Repo secrets: `SCOUT_URL`, `SCOUT_INGEST_SECRET`. Locally they live in `me/dashboard.env` (gitignored).

```bash
cd worker && npm install && npx wrangler deploy        # deploy
.venv/bin/python -m scout.sync push                   # send the latest run to the dashboard by hand
```

## Building the resume PDFs

```bash
brew install pango poppler                      # text layout for WeasyPrint, and pdftotext for checks
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-resume.txt
.venv/bin/python scout/build_resume.py me/resumes/swe.json me/resumes/pm.json me/resumes/it.json
```

Each JSON file in `me/resumes/` holds the facts for one variant (all gitignored). The builder renders `scout/templates/resume.html`, writes the PDF next to the JSON, refuses anything longer than one page, and reads the text layer back to confirm the name, contact line, and section headings survive in order, which is what an ATS parser sees.

## Built with

Python 3.12, GitHub Actions, ntfy, Cloudflare Workers and KV, HTML + WeasyPrint for PDFs, and Claude Code as the pair programmer for the parts that need AI.
