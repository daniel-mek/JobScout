# Implementation status

Assessed 2026-10-17. Code baseline: 366005b18d8f28a866ce9f17ba1cd249cca39c38. Scope: preparation/readiness only; Phase 1 has not started.

Status vocabulary: NOT_STARTED, IN_PROGRESS, COMPLETE, PARTIAL, BLOCKED. COMPLETE applies only to the stated scope and verified behavior. At the final product audit, map NOT_STARTED to NOT_IMPLEMENTED and externally blocked items to BLOCKED_EXTERNALLY; do not treat this baseline as that final audit.

## Readiness

Ready to begin Phase 1 implementation: YES. No live AI, ATS, Gmail or Calendar credentials are required for local foundation work with deterministic parsing and fixtures. Phase 1 complete: NO. Production ready: NO. The repository is not a deployable Next.js/FastAPI application yet.

| Phase | Status against target spec | Existing behavior / remaining gap |
| --- | --- | --- |
| Preparation | COMPLETE | Full supplied spec preserved; architecture, source policy, security, operations, deployment and gap assessment documented; baseline verified |
| 1 Foundation/onboarding | PARTIAL | Shared-password dashboard and private Markdown/JSON profile examples exist; accounts, owner scope, API/database, upload/parsing/review, persistent onboarding and preference UI missing |
| 2 Sources/ingestion | PARTIAL | Greenhouse/Lever/Ashby readers, new-grad feed, normalized dictionaries and URL dedupe; registry enforcement, SmartRecruiters, formal provenance/versions, secure import and persisted source health missing |
| 3 Matching/eligibility | PARTIAL | Title-based level classifier, filters, one explainable score and availability checks; description-based requirements, confirmed-evidence match, hard-requirement engine, two scores and contradiction caps missing |
| 4 Discovery/saving | PARTIAL | Ranked New page, Saved/Passed, prep queue and ntfy digest; rich filters, saved searches, in-app notifications and score-based briefs missing |
| 5 Applications | PARTIAL | CLI/dashboard states, dated history, notes and next action; canonical relational application, precise transition events, immutable job snapshot, Kanban, deadlines and CSV missing |
| 6 Resumes/packets | PARTIAL | Local JSON variants, resume/letter PDF builders, Claude instructions and kit review; uploads/version lineage, evidence validator, approved diffs and versioned AIArtifact workflow missing |
| 7 Companies/contacts/schedules | PARTIAL | Repository-wide cron/concurrency only; contacts, referrals, follow graph, reminders and durable per-search schedules missing |
| 8 Intelligence/learning | NOT_STARTED | No target analytics, skill gaps or bounded learning |
| 9 Gmail/Calendar | NOT_STARTED | No OAuth or provider sync; optional external configuration required later |
| 10 Interview Mode | NOT_STARTED | No application-linked interview workflow or mock session persistence |
| 11 Hardening/privacy/quality | PARTIAL | Basic cookies, escaping, secrets and error paths; full security/privacy/source compliance, quality assessment, accessibility and observability audits missing |
| 12 Final verification | NOT_STARTED | Existing offline regression suite/CI only; full specified journey and release audits not run |

## Reuse decisions

| Existing capability | Evidence | Treatment |
| --- | --- | --- |
| Three public ATS list readers | scout/boards.py; tests/test_boards.py | Reuse adapters/fixtures; add policy and richer metadata |
| Source-failure isolation | listings.fetch_all, boards.fetch_boards; tests/test_early_career.py | Preserve behavior; add typed health and run metrics |
| Deduplication | scout/dedupe.py; tests/test_listings_and_dedupe.py | Preserve canonical-URL logic; review title-based merging before target model adoption |
| Ranking and explanations | matching.py, scoring.py; test_matching/test_scoring | Reuse deterministic primitives; single current score is not Resume Match |
| Tracker history | tracker.set_state and Worker setTracker; tracker tests | Preserve dates/history; existing events lack previous state, precise timestamp and source |
| Local preparation/review | .claude/commands, build_resume.py, build_letter.py, kits.py | Preserve; prompt grounding is not programmatic claim validation |
| Notifications/scheduling | alerts.py, notify.py, run.py; scout workflow | Preserve legacy path; no per-user in-app notification/saved-search guarantees |
| Authentication | Worker login/validCookie | Single-user only; do not reuse shared identity as multi-user auth |

## Baseline checks

- Python unit/regression suite: 163 run, 161 passed, 2 skipped because private Figma regression texts are absent. No failures. External services are mocked.
- Python compilation: passed for scout/ and tests/.
- Dashboard JavaScript syntax: node --check passed on the current Linux environment.
- Existing dashboard rendering was checked during the previous cleanup; no browser end-to-end check of the target product was possible because it does not exist.
- Next.js lint, TypeScript, FastAPI integration, database migrations, Playwright and full dependency/security audit: not configured/not run.
- Live ingestion, deployed Worker, dashboard secrets, workflow execution, account isolation and production storage: not verified.

## Conflicts and blockers

1. Target architecture is substantially different. Introduce it beside the working code, then migrate deliberately; do not call the legacy app complete for the new spec.
2. Current discovery is full-time IT/CS only by user instruction. Preserve that default; do not restore internship targeting while importing the broader taxonomy.
3. SourcePolicy is documented but not runtime-enforced. Legacy generic/Workday/Eightfold fetchers need policy review and SSRF work before exposure through the new product.
4. Current matching is title-based and cannot resolve entry-level titles demanding five years from the description. This is a Phase 3 gap.
5. worker/wrangler.toml still references the upstream repository and inherited namespace. Verify/replace before any deployment.
6. Current deployments, provider credentials, backups and restores have not been checked. Optional credentialed integrations are not prerequisites for Phase 1.
7. The specification explicitly limits the immediate task to preparation/readiness and says not to begin later phases until instructed. No future phase implementation is included here.

## Next authorized implementation boundary

When Phase 1 is requested: scaffold web/API and PostgreSQL migrations; implement account/session/ownership controls; secure PDF/DOCX extraction with deterministic demo parsing; reviewed versioned profiles; configurable career preferences and hard requirements; persisted onboarding and a protected dashboard shell. Add .env.example, appropriate lint/static/typecheck tools and CI. Test two-user isolation and onboarding end to end before marking Phase 1 complete.

