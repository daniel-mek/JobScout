# Implementation status

Phase 2 update (2026-10-22): implementation and local verification are present; native PostgreSQL/browser CI is pending. `/jobs` supports manual import, employer sources, approved/scoped ingestion, source health, saved source searches, provenance, deduplication, versions and complete-cycle archival. Four ATS adapters plus optional USAJOBS/Adzuna are implemented. No external policy is approved; Remotive is disabled and unreviewed company feeds/JSON-LD stay manual. See [PHASE2.md](PHASE2.md) for exact boundaries. Local checks: 55 API tests, Ruff/mypy, frontend lint/typecheck/build and legacy 163 cases (161 pass/two existing skips). Hosting is paused; Phase 3 has not started.

Hosting work (2026-10-22): IN_PROGRESS. Vercel project and private Blob store exist; free Neon database is connected to Production. Initial database inspection found zero public tables. Schema initialization awaits explicit approval of SQL-editor write mode after automatic approval review rejected that action. Added private Blob adapter, Marketplace PostgreSQL driver normalization, Vercel Services configuration, configurable upload ceiling, and macOS-compatible extraction resource limits (Linux production memory limits remain enforced). Local validation: 25 API tests, Ruff/mypy, frontend lint/typecheck/build, production npm audit (zero known vulnerabilities), and legacy 163-test suite (161 pass, two existing skips). Remote build, new CI, database initialization, real Blob round-trip, and hosted end-to-end verification are not yet complete. No live deployment or production readiness is claimed.

Initial assessment: 2026-10-17, baseline 366005b18d8f28a866ce9f17ba1cd249cca39c38. Phase 1 is verified locally and in CI. Subsequent Phase 2 and hosting updates above supersede the original assessment where stated.

Status vocabulary: NOT_STARTED, IN_PROGRESS, COMPLETE, PARTIAL, BLOCKED. COMPLETE applies only to the stated scope and verified behavior. At the final product audit, map NOT_STARTED to NOT_IMPLEMENTED and externally blocked items to BLOCKED_EXTERNALLY; do not treat this baseline as that final audit.

## Readiness

Ready to begin Phase 1 implementation: YES. No live AI, ATS, Gmail or Calendar credentials are required for local foundation work with deterministic parsing and fixtures. Phase 1 implementation and scoped verification: COMPLETE. Native PostgreSQL, API and web/browser CI passed in run 39042290806. Production ready: NO. A separate buildable Next.js/FastAPI application now exists.

| Phase | Status against target spec | Existing behavior / remaining gap |
| --- | --- | --- |
| Preparation | COMPLETE | Full supplied spec preserved; architecture, source policy, security, operations, deployment and gap assessment documented; baseline verified |
| 1 Foundation/onboarding | COMPLETE | Accounts/sessions/ownership, relational profile records, migrations, PDF/DOCX extraction and review, private resume versions, career preferences/hard requirements, persisted onboarding, and protected dashboard implemented. Local API/browser/static/build checks and hosted API/PostgreSQL/web/browser CI all pass |
| 2 Sources/ingestion | IN_PROGRESS | Authenticated registry/policy/board gating, four ATS adapters, optional USAJOBS/Adzuna, normalized relational jobs, provenance, dedupe/version/archive lifecycle, secure manual/URL import, persisted health and run history implemented; PostgreSQL/browser CI pending. External approvals/live calls and employer-specific feeds remain unverified/unconfigured |
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

## Preparation baseline checks (before Phase 1)

- Python unit/regression suite: 163 run, 161 passed, 2 skipped because private Figma regression texts are absent. No failures. External services are mocked.
- Python compilation: passed for scout/ and tests/.
- Dashboard JavaScript syntax: node --check passed on the current Linux environment.
- Existing dashboard rendering was checked during the previous cleanup; no browser end-to-end check of the target product was possible because it does not exist.
- Next.js lint, TypeScript, FastAPI integration, database migrations, Playwright and full dependency/security audit: not configured/not run.
- Live ingestion, deployed Worker, dashboard secrets, workflow execution, account isolation and production storage: not verified.

## Conflicts and blockers

1. The target Phase 1 architecture now runs beside the working legacy code. No legacy private-data migration or new-account job discovery integration is included.
2. Current discovery is full-time IT/CS only by user instruction. Preserve that default; do not restore internship targeting while importing the broader taxonomy.
3. Phase 2 enforces SourcePolicy in the new application. Legacy generic/Workday/Eightfold fetchers remain separate and must not be exposed through account routes.
4. Current matching is title-based and cannot resolve entry-level titles demanding five years from the description. This is a Phase 3 gap.
5. worker/wrangler.toml still references the upstream repository and inherited namespace. Verify/replace before any deployment.
6. Current deployments, provider credentials, backups and restores have not been checked. Optional credentialed integrations are not prerequisites for Phase 1.
7. The user authorized Phases 1 and 2 sequentially. Phase 3 onward remains outside this change; no legacy private application data has been migrated.

## Phase 1 implementation evidence

- Next.js 16.4.2, React 19.3.1, strict TypeScript, Tailwind and native accessible controls; root npm workspace with locked dependencies.
- FastAPI/SQLAlchemy/Pydantic API, initial Alembic migration with persisted role taxonomy, PostgreSQL target and local SQLite fallback. Relational education, experience, projects, certifications and skill/evidence records; JSON is used for immutable version snapshots and bounded preference data.
- Argon2id passwords, hashed revocable opaque sessions, rotation/expiry/logout, origin/session-bound CSRF checks, persistent login throttles and owner-scoped read/write/download/history.
- Bounded PDF/DOCX uploads, isolated extraction, deterministic review-required parsing, conservative aliases/evidence, editable profile confirmation, optimistic revision checks and immutable first-confirmed resume snapshots. S3 adapter contract tested with a fake provider.
- 22 API/unit/integration tests passed on SQLite, including migration upgrade/check/downgrade/upgrade, ownership, session expiry/revocation, CSRF/origin, upload safety, PDF/DOCX success/failure, parser validation, evidence, preferences, version history and storage.
- 3 Chromium end-to-end tests passed: signup through reviewed profile/preferences to dashboard; refresh persistence, download, replacement-resume review/history and logout; mobile invalid-upload/error/overflow; protected routes and unauthorized writes.
- Dashboard automated WCAG A/AA checks passed. Desktop and mobile screenshots inspected internally. This is a scoped automated check, not a full accessibility certification.
- Frontend ESLint, TypeScript, production build; Python Ruff/format and mypy; legacy dashboard syntax and original regression suite passed (163 run, 161 passed, 2 unchanged private-fixture skips).
- npm production dependency audit reported zero known vulnerabilities at validation time. This does not replace future dependency/security reviews.
- Phase 1 CI is configured for native PostgreSQL plus SQLite integration and browser checks. This sandbox cannot switch to the non-root OS user PostgreSQL requires; local native PostgreSQL and Docker execution were unavailable. Both hosted jobs passed, including native PostgreSQL integration and the complete browser suite, in [run 39042290806](https://github.com/daniel-mek/JobScout/actions/runs/39042290806). No live deployment is claimed.
- Browser archive download failed; compatible Chromium from an alternate local package was used for actual browser verification. No browser fallback runtime is added as a production application dependency.

## Boundary and next work

Phase 1 is COMPLETE for the specified foundation/onboarding scope; local and hosted checks passed. No Phase 2 ingestion, scoring, contact, Gmail/Calendar, or interview features were added. Keep the legacy watcher and application data separate until an explicit migration/integration phase. See [PHASE1.md](PHASE1.md) for local setup and host configuration.
