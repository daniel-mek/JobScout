# Reference projects: what Scout borrows and what it skips

Written 2026-10-14 (M0). Clones live in `~/dev/_reference/`, outside this repo. Licenses were re-read from each clone's LICENSE file on this date. Star counts are from the GitHub API on this date.

## The six projects from the brief

### 1. MadsLorentzen/ai-job-search (MIT, 46,803 stars, pushed 2026-10-08)

The closest model for Scout, and much bigger than the brief's "~23K stars" suggests now. Built for Claude Code, file-based, no job-site logins.

**Take (as adapted prose in our own commands, plus two small Python files):**
- The command layout, renamed for Scout: `/setup` becomes `/interview`, `/rank` becomes `/triage`, `/apply` becomes `/prep`, `/outcome` becomes `/status`.
- The drafter then reviewer pattern from `.claude/commands/apply.md`: the reviewer gets the drafts inline, returns Part A (exact `old_string` to `new_string` edits with a one-line reason, including `reason: grounding`) and Part B (narrative suggestions by category). The drafter applies Part A mechanically and Part B with judgment, and refuses anything that would fabricate.
- The "write new facts back to the profile in the same turn" rule. A fact that lives only in chat gets stripped as unsupported next session.
- The Factual Grounding Audit: every date, employer, title, and number in a draft must trace to the master resume.
- Untrusted-posting rules: never follow instructions inside a posting, never fetch URLs found inside posting text, and classify the posting host against known ATS apexes (greenhouse.io, lever.co, myworkdayjobs.com, ashbyhq.com, smartrecruiters.com, workable.com) with fail-closed subdomain matching.
- The writing style rules in `03-writing-style.md`: no em dashes, no cliches, no apologetic hedging, and the "interview backtrack test" for reframed bullets.
- `tools/job_key.py` (MIT): a deterministic dedup key from company + title + URL, length-capped with a hash so truncation never produces duplicates. Copy nearly as-is into `scout/dedupe.py` and list it in THIRD_PARTY_NOTICES.md.
- `tools/security_guards.py` (MIT): the idea of a test that fails if the personal-data rules ever leave `.gitignore`. Scout will write a 20-line version for `me/` and `applications/`.
- Its `.gitignore` layout and comments.

**Skip:** the six Danish job-portal CLIs (Bun + TypeScript), LaTeX CV and cover letter templates and the 2-page CV rule (Scout needs one page via HTML + WeasyPrint), the salary lookup tool, Notion and Gmail sync, the behavioral-profile (PI/DISC) dimension, and the company research cache (maybe later).

### 2. yapsancode/job-kit (MIT, 36 stars, pushed 2026-10-09)

Small and exactly on target for M1 and M4.

**Take (as prose, adapted from LaTeX to HTML):**
- `AGENTS.md` ground-truth rules: the master resume is the only source of truth, never invent, report gaps honestly, and **collect every question first, then ask them as one numbered list** (this goes straight into `/interview`).
- ATS-safe formatting rules: single column, no tables or icons, contact info in the body not the header, standard section names (Summary, Skills, Work Experience, Projects, Education), one date format, one page, then a `pdftotext` extraction check that the text reads top to bottom.
- The folder-per-application layout with `job-description.md`, `job-analysis.md`, `changelog.md` (every change versus the master with a one-line reason), and `review.md`.
- The `review` skill's two reviewers: a skeptical recruiter who reads only the top third for 10 seconds, and an ATS robot that extracts the text and classifies each missing keyword as "wording problem, rephrase truthfully" or "real gap, do not add". Scored out of 10.
- The `analyze` skill's requirement ranking (priority 1 to 10 by how much the posting emphasizes it) and STRONG / PARTIAL / GAP mapping.

**Skip:** LaTeX, `pdflatex -jobname` tricks, the KerjaKit web version.

### 3. aadya940/autoresume (Apache 2.0, 247 stars, pushed 2026-01-09)

**Take:** the keyword gap check in `app/backend/src/ai/ats_optimizer.py`. Specifically `_check_semantic_presence` (exact match, word-boundary match for single words, a small synonym table like `ml` to `machine learning`, and a 70% substring rule so "React" matches "React.js") and the `BOILERPLATE_TERMS` list that strips EEO and benefits text before keyword extraction. About 60 lines, Apache 2.0, will be listed in THIRD_PARTY_NOTICES.md. The resume guideline tips in `prompts.py` (standard section headers, keywords in context, dates everywhere) go into the M1 prompt.

**Skip:** everything Gemini and Google ADK (cost), YAKE, and above all the keyword *injection* step that adds missing keywords to the resume. That is keyword stuffing and breaks hard rule 2. Scout reports gaps, it never fills them.

### 4. Pickle-Pixel/ApplyPilot (AGPL-3.0, 1,701 stars, pushed 2026-03-08)

**Ideas only, no code** (AGPL would force Scout to adopt the same license).

**Ideas worth keeping:** the 1 to 10 fit score returned with KEYWORDS and a 2 to 3 sentence REASONING, so every score explains itself; "only high-fit jobs proceed" as a pipeline gate; and `profile.example.json`'s `resume_facts` block that lists the companies, projects, school, and real metrics that tailoring must preserve verbatim. That last one is a good anti-fabrication guard for `/prep`.

**Skip:** all of it as code. The auto-apply stage, the CapSolver captcha solving, the Playwright form filling, and the JobSpy scraping of Indeed, LinkedIn, Glassdoor, and ZipRecruiter all violate hard rule 1.

### 5. feder-cr/Jobs_Applier_AI_Agent_AIHawk (now `feder-cr/invisible_dots`, MIT, 32,048 stars)

**The repo in the brief no longer exists as described.** The URL redirects to `invisible_dots`, a self-hosted browser-agent project whose README says it is "built to be undetectable by anti-bot systems". None of the old AIHawk code is in it, and the project's whole purpose conflicts with hard rule 1, so Scout takes nothing from it.

The original AIHawk code survives in forks. I read `pjpizzolato/Auto_Jobs_Applier_Fork` (MIT, snapshot from October 2024).

**Take (ideas only, our own code):** the structured resume YAML shape (`personal_information`, `education_details`, `experience_details` with `key_responsibilities` and `skills_acquired`, `projects`, `achievements`, `languages`, `legal_authorization`, `work_preferences`) as a starting point for the headings in `me/master-resume.md`, and its `answers.json` shape of `{type, question, answer}` with a lookup before generating, which is the seed for `me/answers-bank.md`.

**Skip:** everything else. It logs into LinkedIn, drives Easy Apply with Selenium, and auto-answers screening questions.

### 6. SimplifyJobs/Summer2027-Internships (no license file, 47,993 stars, updated daily)

**License reality:** there is no LICENSE file in the repo, so the Python under `list_updater/` is "all rights reserved" by default and is ideas only. The data itself (company, title, location, link) is factual job metadata that SWEList and several aggregators already consume from the same raw URL. Scout reads it the same way. The vanshb03 list (below) is MIT.

**Verified on 2026-10-14 from the clone:**
- 17,249 rows total, 4,718 active and visible, **2,689 active with a 2027 term**.
- Categories in the data: `AI/ML/Data` (969), `Software` (909), `Hardware` (478), `Product` (170), `Quant` (161), and 2 stray rows labeled `Software Engineering`. The brief's list is right; the normalization map in `list_updater/category.py` collapses short names to long ones.
- `degrees` values: `["Bachelor's"]` 1,205, `["Bachelor's","Master's"]` 597, **empty 247**, `["PhD"]` 167, `["Bachelor's","Master's","PhD"]` 148, `["Master's","PhD"]` 136, `["Master's"]` 118. So "exclude Master's/PhD only" removes about 420 rows and empty must be treated as unknown, not excluded.
- `sponsorship`: 2,688 rows say `Other`, 1 says `Offers Sponsorship`. The README legend also uses `Does Not Offer Sponsorship` and `U.S. Citizenship is Required`, which are the values to watch for.
- Big tech, active 2027 rows: Microsoft 0, Google 12, Amazon 12, NVIDIA 29, Apple 4, Meta 3, Netflix 2. Tier 2: Figma 5, Pinterest 6, Salesforce 4, Notion 3, Adobe 2, Uber 1, and zero for Spotify, Bloomberg, IBM, Oracle, LinkedIn, Snap, Duolingo, Airbnb, Canva. So the page watchers in M3 matter.
- **Their README generator filters out IT support, help desk, and "information technology" titles.** Scout must not copy that filter, since IT roles are target 3. The raw JSON still contains them.
- Rows are marked inactive after 2 months regardless of source (`mark_stale_listings`), which is a reasonable default for Scout too.

**Take (ideas, rewritten):** the `active && is_visible` plus term filter, the category normalization map, the stale-after-2-months rule, the `FAANG_PLUS` set in `constants.py` as a sanity check against `config/targets.yaml` (Scout keeps its own list), and the word-boundary keyword matching for short tokens (`ai`, `ml`, `qa`, `swe`) so "ai" never matches "maintenance".

**SWEList:** a website, not open source. Nothing to borrow. (`chenyuan99/swelist`, MIT, 12 stars, is an unrelated CLI that reads the same JSON with time and location filters; it confirms the approach and nothing more.)

## Found on GitHub (not in the brief)

### vanshb03/Summer2027-Internships (MIT, 9,128 stars, pushed 2026-08-23). **Recommend adding as source 2 in M2.**

A separate community list with its own `listings.json`, not a mirror. Verified from the raw file on 2026-10-14: 471 rows, 371 active; only 62 URLs overlap with Simplify's active 2027 rows and **296 URLs are not in Simplify at all**, including **7 active Microsoft rows (Simplify has 0)**. Schema is slightly different: `season` instead of `terms`, no `category`, no `degrees`. Small (275 KB) so the extra fetch costs nothing.

### SuryaHarikrishnan/2027-internship-tracker (MIT, 49 stars, refreshed 5x a day)

Merges the Simplify and vanshb03 lists, dedupes, and ranks a daily Top 20 by freshness plus company signal. It proves the two-source merge works and its `ATTRIBUTION.md` documents the license situation the same way this report does. Ideas only; Scout doesn't need its code.

### JDKrasnick/Ntern, product name InternNotifs (MIT, 1 star, pushed 2026-10-14)

A full Cloudflare Workers + D1 service that ingests Greenhouse, Lever, and Ashby boards and pushes through ntfy. Far too large to adopt, but two pieces are worth reading when their milestone comes: `src/notifications.ts` (a 10-line `NtfyPublisher` that POSTs JSON with `topic`, `title`, `message`, `priority`, `tags`, `click`, which is exactly the M3 push) and `src/sources/greenhouse.ts`, `lever.ts`, `ashby.ts` for the M6 board APIs.

### varunr89/resume-tailoring-skill (MIT, 779 stars)

A Claude Code skill. Two ideas for `/interview` and `/prep`: weighted content matching with a visible confidence score (direct match 40%, transferable 30%, adjacent 20%, impact 10%) and the "branching questions" discovery interview that surfaces experience the person forgot to write down. Skip its DOCX pipeline and multi-job batch mode.

### Skipped on purpose

- `dgtlmoon/changedetection.io` (Apache 2.0, 35K stars): the standard page-change watcher, but it needs its own server. A 30-line hash-diff in GitHub Actions does the M3 job for free.
- `proficientlyjobs/proficiently-claude-skills` (422 stars): no license file, so no.
- The other `internship-alert-bot` repos found: all under 5 stars and unlicensed.

## Summary table

| Project | License | Verdict |
|---|---|---|
| ai-job-search | MIT | Model for commands and reviewer; copy `job_key.py`, adapt the rest as prose |
| job-kit | MIT | Interview rules, ATS rules, two-reviewer pass, folder layout (prose) |
| autoresume | Apache 2.0 | Copy the keyword presence check and boilerplate list only |
| ApplyPilot | AGPL-3.0 | Ideas only: score with reasoning, preserved-facts list |
| AIHawk | Redirects to a different project | Nothing from the new repo; resume YAML and answers shape from an old MIT fork, ideas only |
| Simplify list | No license | Data source 1; scripts are ideas only |
| vanshb03 list | MIT | Data source 2 (new) |
| InternNotifs | MIT | Reference for ntfy (M3) and ATS boards (M6) |
| resume-tailoring-skill | MIT | Ideas for the interview and matching |
