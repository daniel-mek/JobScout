# Running Scout

The commands and moving parts behind the README. Everything below assumes a Python 3.12 venv at `.venv/`.

## Folder layout

```
config/              targets.yaml, scoring.yaml, watch-pages.yaml (edit these, not code)
scout/               the Python code
scout/templates/     resume.html and letter.html, one-column ATS-safe layouts
tests/               unit tests on saved fixture JSON, no network
worker/              the Cloudflare Worker dashboard
docs/                screenshots, this file, design decisions, the reference report
.claude/commands/    /interview, /triage, /prep, /status for Claude Code
me/                  your master profile, voice rules, answer bank, resume variants   (gitignored; template in me.example/)
applications/        one folder per prep kit                                          (gitignored)
data/                runtime state; in GitHub Actions it is the "data" branch          (gitignored on main)
```

## The watcher

```bash
.venv/bin/python -m scout.watch                           # fetch both lists, print the top 20, write data/matches.json
.venv/bin/python -m scout.watch --top 50 --no-pages       # more rows, skip the page checks
.venv/bin/python -m scout.watch --offline tests/fixtures  # saved copies only, no network
.venv/bin/python -m unittest discover -s tests -t .       # the tests
```

Pipeline, in order: `listings.py` fetches the Simplify and vanshb03 JSON files and normalizes every row; `matching.py` decides company tier, role, location, freshman-friendliness, and degree from `config/targets.yaml`; hard drops are inactive rows, non-2027 terms, graduate-only degrees, non-target roles, and postings older than 240 days; `dedupe.py` collapses the same posting across both lists; `scoring.py` applies `config/scoring.yaml` and keeps the breakdown; `eligibility.py` reads the top 40 posting pages for graduation-year and class-year requirements (cached 14 days), and anything the posting rules out sinks to the bottom, still labeled. Nothing is hidden for location; it only changes the score.

```
 1. [100] NVIDIA  |  Software Engineer Intern
      Santa Clara, CA  |  posted 10d  |  eligible: page mentions freshman/sophomore/underclassmen
      role swe 30 + tier 1 20 + early strong 45 + deg 5 + loc us 6 + fresh 0 + kw 0 = 100   (106, capped at 100)
```

## Alerts and the schedule

```bash
export NTFY_TOPIC=...                                  # the private topic; also a GitHub Actions secret
.venv/bin/python -m scout.run --mode test              # one test push
.venv/bin/python -m scout.run --mode watch --dry-run   # what a run would push, without sending
.venv/bin/python -m scout.run --mode watch --seed      # first run only: mark today's matches as seen
.venv/bin/python -m scout.run --mode digest --force    # send the digest now
```

- **Instant push:** a Tier 1 or Tier 2 posting scoring 60 or more, any freshman/sophomore program, any ambassador role, or a watched page that gained new text.
- **Daily digest:** the top 10 new matches that did not push instantly, once a day after 7:00 PM New York time.
- **Page watchers:** each page in `config/watch-pages.yaml` is fetched, stripped to text with volatile tokens (hashes, cloud region names, rotating job-carousel cards) removed, and hashed. Only new lines count as a change. Scout stores a fingerprint of each line, never the page text, so the repo does not republish anyone's page. A page that can't be read twice in a row, or serves no text, warns once.
- **Nothing twice:** `seen.json` holds every key ever pushed or digested.
- **Failing loudly:** if a source list can't be fetched, one push says so.
- **Schedule:** hourly at :17 except two early-morning hours. GitHub delays and skips scheduled runs when busy, so the digest is a once-a-day check inside every run rather than its own schedule.
- **State:** the workflow checks out the `data` branch into `data/`, runs, and commits back to `data`, so `main` stays code only.

## Prep kits (Claude Code)

`/triage` reads the newest matches and recommends three or four. `/prep <key>` builds `applications/<company>-<role>/` with `resume.json` and its PDF, `cover-letter.md` and its PDF when the posting wants one, `answers.md`, `notes.md`, `posting.txt`, and `match.json`. A drafter writes from `me/master_profile.md` only; a separate reviewer agent checks every claim against the profile, the voice rules, and the posting's must-haves, and its flags go into `notes.md`. `/status <key> Applied` logs a submission, which is always done by hand.

```bash
.venv/bin/python -m scout.posting "<url>"                      # read a posting as text (Workday included)
.venv/bin/python scout/build_resume.py me/resumes/swe.json     # one-page PDF with an ATS text-layer check
.venv/bin/python scout/build_letter.py applications/<folder>/cover-letter.md
.venv/bin/python -m scout.tracker list
```

PDFs need `brew install pango poppler` and `pip install -r requirements-resume.txt`.

## Dashboard

```
GitHub Actions run --push-->  Worker + KV  <--taps--  phone (New, Programs, Tracker, Settings)
GitHub Actions run <--pull--  tracker, prep queue, passed keys
```

- `worker/src/index.js` is the whole app: routing, the password login (HMAC-signed cookie, 30 days), server-rendered pages, and small JSON endpoints for the buttons. `worker/src/tokens.css` holds every color and size.
- `scout/sync.py push` sends matches (with first-seen times), page state, the tracker, and the config text to `/api/ingest` with a secret header. `scout/sync.py pull` fetches `/api/export` and writes the tracker, queue, and passed keys into `data/` (never committed).
- "Prep this" queues a posting for `/prep`; "Pass" hides it (with undo). Tracker edits from the phone win over older ones by date.
- Worker secrets: `DASH_PASSWORD`, `SESSION_SECRET`, `INGEST_SECRET`. Repo secrets: `NTFY_TOPIC`, `SCOUT_URL`, `SCOUT_INGEST_SECRET`.

```bash
cd worker && npm install && npx wrangler deploy
cp .dev.vars.example .dev.vars && npx wrangler dev     # local copy with test values
```

## Cost

$0. Public repos get unlimited Actions minutes; each run takes about a minute, about 22 a day (roughly 660 minutes a month, inside the 2,000 free minutes even if the repo goes private). Cloudflare Workers and KV free tier: 100,000 requests a day. ntfy is free.
